from typing import Any, Dict, List
from pathlib import Path
import pytsk3

from app.analysis.base import BaseAnalyzer


class EWFImgInfo(pytsk3.Img_Info):
    """Adapter for E01/EWF files."""
    def __init__(self, ewf_handle):
        self._ewf_handle = ewf_handle
        super().__init__(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)

    def close(self):
        self._ewf_handle.close()

    def read(self, offset, size):
        self._ewf_handle.seek(offset)
        return self._ewf_handle.read(size)

    def get_size(self):
        return self._ewf_handle.get_media_size()


class VHDIImgInfo(pytsk3.Img_Info):
    """Adapter for VHD/VHDX files using libvhdi."""
    def __init__(self, vhdi_file):
        self._vhdi_file = vhdi_file
        super().__init__(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)

    def close(self):
        self._vhdi_file.close()

    def read(self, offset, size):
        self._vhdi_file.seek_offset(offset)
        return self._vhdi_file.read_buffer(size)

    def get_size(self):
        return self._vhdi_file.get_media_size()


class DataSourceIdentifier(BaseAnalyzer):
    name = "data_source_identifier"
    description = "Identifies image type, volumes, filesystems and OS likelihood"

    def analyze(self, target: str, **kwargs) -> Dict[str, Any]:
        path = Path(target)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {target}")

        result = {
            "file_path": str(path),
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "image_type": self._detect_image_type(path),
            "partition_scheme": None,
            "volumes": [],
            "is_operating_system": False,
            "summary": "",
        }

        try:
            img_info = self._open_image(path)

            # Try partition table first
            try:
                volume_info = pytsk3.Volume_Info(img_info)
                result["partition_scheme"] = self._get_partition_scheme(volume_info)

                for part in volume_info:
                    desc = part.desc.decode("utf-8", errors="ignore")
                    desc_lower = desc.lower()

                    if any(x in desc_lower for x in [
                        "unallocated", "primary table", "safety table",
                        "gpt header", "partition table"
                    ]):
                        continue

                    volume = {
                        "address": part.addr,
                        "description": desc,
                        "start_sector": part.start,
                        "length_sectors": part.len,
                        "size_bytes": part.len * 512,
                        "filesystem": "Unknown",
                    }

                    try:
                        fs = pytsk3.FS_Info(img_info, offset=part.start * 512)
                        volume["filesystem"] = self._fs_type_to_name(fs.info.ftype)
                    except Exception:
                        pass

                    result["volumes"].append(volume)

            except Exception:
                pass

            # Fallback: single filesystem
            if not result["volumes"]:
                try:
                    fs = pytsk3.FS_Info(img_info)
                    result["volumes"].append({
                        "address": 0,
                        "description": "Single volume (no partition table)",
                        "start_sector": 0,
                        "length_sectors": None,
                        "size_bytes": result["file_size"],
                        "filesystem": self._fs_type_to_name(fs.info.ftype),
                    })
                    result["partition_scheme"] = "None (single filesystem)"
                except Exception as e:
                    result["error"] = f"Could not open as volume or filesystem: {e}"

            result["is_operating_system"] = self._looks_like_os(result["volumes"])
            result["summary"] = self._generate_summary(result)

        except Exception as e:
            result["error"] = str(e)
            result["summary"] = f"Failed to open image: {e}"

        return result

    def _open_image(self, path: Path):
        name = path.name.lower()

        # E01 / EWF
        if name.endswith((".e01", ".ex01", ".s01")):
            import pyewf
            filenames = pyewf.glob(str(path))
            ewf_handle = pyewf.handle()
            ewf_handle.open(filenames)
            return EWFImgInfo(ewf_handle)

        # VHD / VHDX
        if name.endswith((".vhd", ".vhdx")):
            import pyvhdi
            vhdi_file = pyvhdi.file()
            vhdi_file.open(str(path))
            return VHDIImgInfo(vhdi_file)

        # Raw / dd / img
        return pytsk3.Img_Info(str(path))

    def _detect_image_type(self, path: Path) -> str:
        name = path.name.lower()
        if name.endswith((".e01", ".ex01")):
            return "E01 (Expert Witness)"
        if name.endswith(".vhd"):
            return "VHD"
        if name.endswith(".vhdx"):
            return "VHDX"
        if name.endswith((".dd", ".raw", ".img")):
            return "Raw Disk Image"
        return "Unknown"

    def _get_partition_scheme(self, volume_info) -> str:
        try:
            ptype = volume_info.info.vstype
            mapping = {
                pytsk3.TSK_VS_TYPE_DOS: "MBR (DOS)",
                pytsk3.TSK_VS_TYPE_GPT: "GPT",
                pytsk3.TSK_VS_TYPE_MAC: "Mac",
                pytsk3.TSK_VS_TYPE_BSD: "BSD",
            }
            return mapping.get(ptype, str(ptype))
        except Exception:
            return "Unknown"

    def _fs_type_to_name(self, ftype) -> str:
        fs_map = {
            pytsk3.TSK_FS_TYPE_NTFS: "NTFS",
            pytsk3.TSK_FS_TYPE_FAT12: "FAT12",
            pytsk3.TSK_FS_TYPE_FAT16: "FAT16",
            pytsk3.TSK_FS_TYPE_FAT32: "FAT32",
            pytsk3.TSK_FS_TYPE_EXFAT: "exFAT",
            pytsk3.TSK_FS_TYPE_EXT2: "EXT2",
            pytsk3.TSK_FS_TYPE_EXT3: "EXT3",
            pytsk3.TSK_FS_TYPE_EXT4: "EXT4",
            pytsk3.TSK_FS_TYPE_ISO9660: "ISO9660",
            pytsk3.TSK_FS_TYPE_HFS: "HFS",
            pytsk3.TSK_FS_TYPE_APFS: "APFS",
        }
        return fs_map.get(ftype, str(ftype))

    def _looks_like_os(self, volumes: List[Dict]) -> bool:
        for vol in volumes:
            fs = str(vol.get("filesystem", "")).lower()
            desc = vol.get("description", "").lower()
            if "ntfs" in fs or "windows" in desc or "basic data" in desc:
                return True
        return False

    def _generate_summary(self, data: Dict) -> str:
        vol_count = len(data["volumes"])
        scheme = data.get("partition_scheme") or "Unknown"
        os_text = "Operating System" if data["is_operating_system"] else "Data drive / simple filesystem"
        return f"{vol_count} volume(s) detected | Scheme: {scheme} | Type: {os_text}"
