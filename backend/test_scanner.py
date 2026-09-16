from pathlib import Path
from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
import pytsk3
import pyewf


def main():
    evidence_path = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"

    print("=== 1. Identifying Data Source ===")
    identifier = DataSourceIdentifier()
    id_result = identifier.analyze(evidence_path)

    print(f"Image Type     : {id_result['image_type']}")
    print(f"Partition Scheme: {id_result['partition_scheme']}")
    print(f"Is OS          : {id_result['is_operating_system']}")
    print(f"Summary        : {id_result['summary']}")
    print()

    # Find the main NTFS volume
    ntfs_volume = None
    for vol in id_result["volumes"]:
        if vol["filesystem"] == "NTFS":
            ntfs_volume = vol
            break

    if not ntfs_volume:
        print("No NTFS volume found.")
        return

    print(f"=== 2. Scanning NTFS Volume (start sector: {ntfs_volume['start_sector']}) ===")

    # Open the image again for the scanner
    filenames = pyewf.glob(evidence_path)
    ewf_handle = pyewf.handle()
    ewf_handle.open(filenames)
    img_info = EWFImgInfo(ewf_handle)

    scanner = FilesystemScanner()
    scan_result = scanner.analyze(
        img_info=img_info,
        offset=ntfs_volume["start_sector"] * 512,
        volume_name="Main NTFS Volume"
    )

    print(f"Total files scanned : {scan_result['total_files_scanned']}")
    print(f"Virtual Disks found : {len(scan_result['virtual_disks'])}")
    print(f"Emails found        : {len(scan_result['emails'])}")
    print(f"Documents found     : {len(scan_result['documents'])}")
    print(f"Images found        : {len(scan_result['images'])}")
    print(f"Registry hives      : {len(scan_result['registry_hives'])}")
    print(f"Recycle Bin items   : {len(scan_result['recycle_bin_items'])}")
    print()

    if scan_result["virtual_disks"]:
        print("=== Virtual Disks ===")
        for vd in scan_result["virtual_disks"]:
            print(f"  - {vd['path']}  ({vd['size']} bytes)")

    if scan_result["errors"]:
        print("\nErrors:")
        for err in scan_result["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
