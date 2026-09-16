from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
from app.analysis.analyzers.virtual_disk_handler import VirtualDiskHandler
import pyewf


def print_scan_summary(title: str, scan: dict):
    print(f"\n{title}")
    print(f"  Files scanned        : {scan.get('total_files_scanned', 0)}")
    print(f"  Virtual disks        : {len(scan.get('virtual_disks', []))}")
    print(f"  Emails               : {len(scan.get('emails', []))}")
    print(f"  Documents            : {len(scan.get('documents', []))}")
    print(f"  Images               : {len(scan.get('images', []))}")
    print(f"  Registry hives       : {len(scan.get('registry_hives', []))}")
    print(f"  Event logs (.evtx)   : {len(scan.get('event_logs', []))}")
    print(f"  Browser artifacts    : {len(scan.get('browser_artifacts', []))}")
    print(f"  Prefetch             : {len(scan.get('prefetch', []))}")
    print(f"  LNK files            : {len(scan.get('lnk_files', []))}")
    print(f"  Jump lists           : {len(scan.get('jump_lists', []))}")
    print(f"  Recycle Bin          : {len(scan.get('recycle_bin', []))}")
    print(f"  Executables          : {len(scan.get('executables', []))}")
    print(f"  Databases            : {len(scan.get('databases', []))}")
    print(f"  Archives             : {len(scan.get('archives', []))}")
    print(f"  Encryption related   : {len(scan.get('encryption_related', []))}")
    if scan.get("errors"):
        print(f"  Errors               : {scan['errors']}")


def main():
    evidence_path = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"

    print("=== 1. Identifying main data source ===")
    identifier = DataSourceIdentifier()
    id_result = identifier.analyze(evidence_path)
    print(f"Summary: {id_result['summary']}")

    ntfs_volume = next((v for v in id_result["volumes"] if v["filesystem"] == "NTFS"), None)
    if not ntfs_volume:
        print("No NTFS volume found.")
        return

    print("\n=== 2. Scanning main NTFS volume ===")
    filenames = pyewf.glob(evidence_path)
    ewf_handle = pyewf.handle()
    ewf_handle.open(filenames)
    img_info = EWFImgInfo(ewf_handle)

    scanner = FilesystemScanner()
    main_scan = scanner.analyze(
        img_info=img_info,
        offset=ntfs_volume["start_sector"] * 512,
        volume_name="Main NTFS Volume"
    )
    print_scan_summary("Main Volume Results", main_scan)

    if not main_scan.get("virtual_disks"):
        print("\nNo virtual disks found.")
        return

    vhd = main_scan["virtual_disks"][0]
    print(f"\n=== 3. Analyzing virtual disk: {vhd['path']} ===")

    handler = VirtualDiskHandler()
    vhd_result = handler.analyze(
        img_info=img_info,
        vhd_path=vhd["path"],
        parent_offset=ntfs_volume["start_sector"] * 512
    )

    ident = vhd_result.get("identification", {})
    print(f"VHD Summary: {ident.get('summary')}")

    print("\n=== 4. Findings inside the VHD ===")
    for i, scan in enumerate(vhd_result.get("scans", []), 1):
        print_scan_summary(f"VHD Volume {i}: {scan.get('volume_name')}", scan)


if __name__ == "__main__":
    main()
