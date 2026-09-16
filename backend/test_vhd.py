from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
from app.analysis.analyzers.virtual_disk_handler import VirtualDiskHandler
import pyewf


def main():
    evidence_path = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"

    print("=== 1. Identifying main data source ===")
    identifier = DataSourceIdentifier()
    id_result = identifier.analyze(evidence_path)
    print(f"Summary: {id_result['summary']}\n")

    # Find main NTFS volume
    ntfs_volume = next((v for v in id_result["volumes"] if v["filesystem"] == "NTFS"), None)
    if not ntfs_volume:
        print("No NTFS volume found.")
        return

    print("=== 2. Scanning main volume for virtual disks ===")
    filenames = pyewf.glob(evidence_path)
    ewf_handle = pyewf.handle()
    ewf_handle.open(filenames)
    img_info = EWFImgInfo(ewf_handle)

    scanner = FilesystemScanner()
    scan_result = scanner.analyze(
        img_info=img_info,
        offset=ntfs_volume["start_sector"] * 512,
        volume_name="Main NTFS"
    )

    print(f"Virtual disks found: {len(scan_result['virtual_disks'])}")
    for vd in scan_result["virtual_disks"]:
        print(f"  → {vd['path']} ({vd['size']:,} bytes)")
    print()

    if not scan_result["virtual_disks"]:
        return

    vhd = scan_result["virtual_disks"][0]
    print(f"=== 3. Analyzing virtual disk: {vhd['path']} ===")

    handler = VirtualDiskHandler()
    vhd_result = handler.analyze(
        img_info=img_info,
        vhd_path=vhd["path"],
        parent_offset=ntfs_volume["start_sector"] * 512
    )

    if vhd_result.get("errors"):
        print("Handler errors:")
        for err in vhd_result["errors"]:
            print(f"  - {err}")
        print()

    ident = vhd_result.get("identification", {})
    print(f"VHD Image Type      : {ident.get('image_type')}")
    print(f"VHD Partition Scheme: {ident.get('partition_scheme')}")
    print(f"VHD Volumes found   : {len(ident.get('volumes', []))}")
    print(f"VHD Summary         : {ident.get('summary')}")
    print()

    print("=== Volumes inside the VHD ===")
    for i, vol in enumerate(ident.get("volumes", []), 1):
        print(f"{i}. {vol['description']}")
        print(f"   Filesystem : {vol['filesystem']}")
        print(f"   Start      : {vol['start_sector']}")
        print(f"   Size       : {vol['size_bytes']:,} bytes")
    print()

    print("=== Scan results inside the VHD ===")
    for i, scan in enumerate(vhd_result.get("scans", []), 1):
        print(f"\nVolume {i}: {scan.get('volume_name')}")
        print(f"  Files scanned : {scan.get('total_files_scanned')}")
        print(f"  Errors        : {scan.get('errors')}")
        print(f"  Virtual disks : {len(scan.get('virtual_disks', []))}")
        print(f"  Documents     : {len(scan.get('documents', []))}")
        print(f"  Emails        : {len(scan.get('emails', []))}")


if __name__ == "__main__":
    main()
