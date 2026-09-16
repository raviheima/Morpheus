from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
from app.analysis.analyzers.virtual_disk_handler import VirtualDiskHandler
import pyewf
import pytsk3


def main():
    evidence_path = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"

    print("=== 1. Identifying main data source ===")
    identifier = DataSourceIdentifier()
    id_result = identifier.analyze(evidence_path)
    print(f"Summary: {id_result['summary']}")
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

    print("=== 2. Scanning main NTFS volume for virtual disks ===")
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
        print("No virtual disks to process.")
        return

    # Process the first (and only) VHD we found
    vhd = scan_result["virtual_disks"][0]
    print(f"=== 3. Analyzing virtual disk: {vhd['path']} ===")

    handler = VirtualDiskHandler()
    vhd_result = handler.analyze(
        img_info=img_info,
        vhd_path=vhd["path"],
        parent_offset=ntfs_volume["start_sector"] * 512
    )

    if vhd_result["errors"]:
        print("Errors while processing VHD:")
        for err in vhd_result["errors"]:
            print(f"  - {err}")
        return

    # Show identification of the VHD
    ident = vhd_result["identification"]
    print(f"VHD Image Type     : {ident.get('image_type')}")
    print(f"VHD Partition Scheme: {ident.get('partition_scheme')}")
    print(f"VHD Is OS          : {ident.get('is_operating_system')}")
    print(f"VHD Summary        : {ident.get('summary')}")
    print()

    # Show what was found inside the VHD
    print("=== Findings inside the VHD ===")
    for i, scan in enumerate(vhd_result["scans"], 1):
        print(f"\nVolume {i}: {scan['volume_name']}")
        print(f"  Files scanned     : {scan['total_files_scanned']}")
        print(f"  Virtual disks     : {len(scan['virtual_disks'])}")
        print(f"  Emails            : {len(scan['emails'])}")
        print(f"  Documents         : {len(scan['documents'])}")
        print(f"  Images            : {len(scan['images'])}")
        print(f"  Registry hives    : {len(scan['registry_hives'])}")
        print(f"  Recycle Bin items : {len(scan['recycle_bin_items'])}")

        if scan["virtual_disks"]:
            print("  Nested virtual disks:")
            for nested in scan["virtual_disks"]:
                print(f"    - {nested['path']}")


if __name__ == "__main__":
    main()
