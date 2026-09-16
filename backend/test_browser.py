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

    # Find main NTFS volume
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

    # Filter only History databases
    history_files = [
        f for f in browser_files
        if f["name"].lower() == "history" or "history" in f["path"].lower()
    ]

    print(f"History databases found: {len(history_files)}")
    for h in history_files:
        print(f"  → {h['path']}")

    if not history_files:
        print("No History databases to parse.")
        return

    print("\n=== 3. Parsing browser history ===")
    analyzer = BrowserAnalyzer()
    result = analyzer.analyze(
        img_info=img_info,
        offset=ntfs_volume["start_sector"] * 512,
        history_files=history_files
    )

    print(f"Total history entries extracted: {result['total_entries']}")
    print(f"Errors: {result['errors']}\n")

    for hist in result["histories"]:
        print(f"Source: {hist['source']}")
        print(f"Entries: {hist['count']}")
        print("--- Sample entries ---")
        for entry in hist["entries"][:8]:
            print(f"  [{entry['visit_time']}] {entry['title'][:60]}")
            print(f"       {entry['url'][:80]}")
        print()


if __name__ == "__main__":
    main()
