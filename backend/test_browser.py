from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
from app.analysis.analyzers.browser_analyzer import BrowserAnalyzer
import pyewf


def main():
    evidence_path = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"

    print("=== 1. Identifying data source ===")
    identifier = DataSourceIdentifier()
    id_result = identifier.analyze(evidence_path)
    print(f"Summary: {id_result['summary']}\n")

    ntfs_volume = next((v for v in id_result["volumes"] if v["filesystem"] == "NTFS"), None)
    if not ntfs_volume:
        print("No NTFS volume found.")
        return

    print("=== 2. Scanning for browser artifacts ===")
    filenames = pyewf.glob(evidence_path)
    ewf_handle = pyewf.handle()
    ewf_handle.open(filenames)
    img_info = EWFImgInfo(ewf_handle)

    scanner = FilesystemScanner()
    scan = scanner.analyze(
        img_info=img_info,
        offset=ntfs_volume["start_sector"] * 512,
        volume_name="Main NTFS"
    )

    browser_files = scan.get("browser_artifacts", [])
    print(f"Browser artifacts found: {len(browser_files)}")

    # Show some examples
    print("Sample browser artifacts:")
    for f in browser_files[:8]:
        print(f"  → {f['path']}")

    print("\n=== 3. Parsing browser history ===")
    analyzer = BrowserAnalyzer()
    result = analyzer.analyze(
        img_info=img_info,
        offset=ntfs_volume["start_sector"] * 512,
        history_files=browser_files
    )

    print(f"Total entries extracted : {result['total_entries']}")
    print(f"Chrome/Edge results     : {len(result['chrome_edge'])}")
    print(f"Internet Explorer items : {len(result['internet_explorer'])}")
    print(f"Errors                  : {result['errors']}\n")

    # Chrome / Edge
    if result["chrome_edge"]:
        print("--- Chrome / Edge History ---")
        for hist in result["chrome_edge"]:
            print(f"Source: {hist['source']}")
            print(f"Entries: {hist['count']}")
            for entry in hist["entries"][:5]:
                print(f"  [{entry['visit_time']}] {entry['title'][:50]}")
                print(f"       {entry['url'][:70]}")
            print()

    # Internet Explorer
    if result["internet_explorer"]:
        print("--- Internet Explorer Artifacts ---")
        for item in result["internet_explorer"]:
            print(f"  → {item['source']}")
            if item.get("note"):
                print(f"     Note: {item['note']}")


if __name__ == "__main__":
    main()
