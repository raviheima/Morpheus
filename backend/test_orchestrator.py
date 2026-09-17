from app.analysis.orchestrator import AnalysisOrchestrator


def print_scan(scan, indent="  "):
    if not scan:
        return
    print(f"{indent}Files scanned     : {scan.get('total_files_scanned', 0)}")
    print(f"{indent}Deleted files     : {scan.get('total_deleted_found', 0)}")
    print(f"{indent}Suspicious files  : {len(scan.get('suspicious_files', []))}")
    print(f"{indent}Emails            : {len(scan.get('emails', []))}")
    print(f"{indent}Documents         : {len(scan.get('documents', []))}")
    print(f"{indent}Images            : {len(scan.get('images', []))}")
    print(f"{indent}Registry hives    : {len(scan.get('registry_hives', []))}")
    print(f"{indent}Event logs        : {len(scan.get('event_logs', []))}")
    print(f"{indent}Browser artifacts : {len(scan.get('browser_artifacts', []))}")
    print(f"{indent}Prefetch          : {len(scan.get('prefetch', []))}")
    print(f"{indent}LNK files         : {len(scan.get('lnk_files', []))}")
    print(f"{indent}Executables       : {len(scan.get('executables', []))}")

    suspicious = scan.get("suspicious_files", [])
    if suspicious:
        print(f"{indent}--- Sample Suspicious Files ---")
        for item in suspicious[:5]:
            reasons = ", ".join(item.get("reasons", []))
            print(f"{indent}  • {item['path']}  [{reasons}]")


def print_browser_analysis(browser, indent="  "):
    if not browser:
        return

    print(f"{indent}Browser Analysis:")
    print(f"{indent}  Chrome/Edge histories : {len(browser.get('chrome_edge', []))}")
    print(f"{indent}  Firefox artifacts     : {len(browser.get('firefox', []))}")
    print(f"{indent}  Internet Explorer     : {len(browser.get('internet_explorer', []))}")
    print(f"{indent}  Total history entries : {browser.get('total_entries', 0)}")

    # Errors & notes
    if browser.get("errors"):
        print(f"{indent}  --- Errors ---")
        for err in browser["errors"]:
            print(f"{indent}    ! {err}")

    if browser.get("notes"):
        print(f"{indent}  --- Notes ---")
        for note in browser["notes"]:
            print(f"{indent}    * {note}")

    # IE section
    ie_items = browser.get("internet_explorer", [])
    if ie_items:
        print(f"{indent}  --- IE History Files ---")
        for item in ie_items:
            src = item.get("source", "")
            typ = item.get("type", "")
            cnt = item.get("count", 0)
            note = item.get("note", "")

            print(f"{indent}    → {src}")
            print(f"{indent}      type={typ}  entries={cnt}")
            if note:
                print(f"{indent}      note: {note}")

            # Show actual history entries (up to 10)
            entries = item.get("entries", [])
            if entries and cnt > 0:
                print(f"{indent}      --- Sample entries ---")
                for entry in entries[:10]:
                    # Try every possible timestamp field
                    ts = (
                        entry.get("last_accessed")
                        or entry.get("visit_time")
                        or entry.get("last_modified")
                        or entry.get("accessed")
                        or ""
                    )
                    url = entry.get("url", "")[:90]
                    count = entry.get("access_count") or entry.get("visit_count") or ""
                    extra = f" (hits: {count})" if count else ""
                    print(f"{indent}        [{ts}]{extra} {url}")

    # Chrome/Edge
    for hist in browser.get("chrome_edge", []):
        print(f"{indent}  --- Chrome/Edge: {hist.get('source')} ---")
        print(f"{indent}      Entries: {hist.get('count', 0)}")
        for entry in hist.get("entries", [])[:5]:
            print(f"{indent}      [{entry.get('visit_time')}] {entry.get('title', '')[:60]}")
def main():
    evidence = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"

    orchestrator = AnalysisOrchestrator()
    report = orchestrator.analyze(evidence)

    print("\n" + "="*65)
    print(" FULL ANALYSIS REPORT")
    print("="*65)

    ident = report["identification"]
    print(f"\nTarget           : {report['target']}")
    print(f"Image Type       : {ident['image_type']}")
    print(f"Partition Scheme : {ident['partition_scheme']}")
    print(f"Is OS            : {ident['is_operating_system']}")

    # --- Main volumes ---
    print("\n" + "-"*65)
    print("MAIN VOLUMES")
    print("-"*65)

    for i, vol in enumerate(report["volume_scans"], 1):
        status = "SCANNED" if vol["scanned"] else "SKIPPED"
        print(f"\n{i}. {vol['description']}")
        print(f"   Filesystem : {vol['filesystem']}")
        print(f"   Size       : {vol['size_bytes']:,} bytes")
        print(f"   Status     : {status}")
        if vol.get("note"):
            print(f"   Note       : {vol['note']}")
        if vol.get("scanned") and vol.get("scan_result"):
            print_scan(vol["scan_result"], indent="   ")

        # Show browser analysis if available
        if vol.get("browser_analysis"):
            print_browser_analysis(vol["browser_analysis"], indent="   ")

    # --- Nested VHDs ---
    print("\n" + "-"*65)
    print("NESTED VIRTUAL DISKS")
    print("-"*65)

    if not report["nested_virtual_disks"]:
        print("\nNo nested virtual disks found.")
    else:
        for i, vhd in enumerate(report["nested_virtual_disks"], 1):
            print(f"\n{i}. {vhd.get('vhd_path')}")
            ident = vhd.get("identification", {})
            print(f"   Type           : {ident.get('image_type')}")
            print(f"   Partition Scheme: {ident.get('partition_scheme')}")
            print(f"   Volumes found  : {len(ident.get('volumes', []))}")

            for j, scan in enumerate(vhd.get("scans", []), 1):
                print(f"\n   Volume {j}: {scan.get('volume_name')}")
                print_scan(scan, indent="      ")

    # --- Final Summary ---
    summary = report["summary"]
    print("\n" + "="*65)
    print("FINAL SUMMARY")
    print("="*65)
    print(f"Volumes found              : {summary['total_volumes_found']}")
    print(f"Volumes scanned            : {summary['total_volumes_scanned']}")
    print(f"Nested VHDs                : {summary['nested_vhds']}")
    print(f"Total files scanned        : {summary['total_files_scanned']}")
    print(f"Emails                     : {summary['total_emails']}")
    print(f"Documents                  : {summary['total_documents']}")
    print(f"Images                     : {summary['total_images']}")
    print(f"Registry hives             : {summary['total_registry_hives']}")
    print(f"Event logs                 : {summary['total_event_logs']}")
    print(f"Browser artifacts          : {summary['total_browser_artifacts']}")
    print(f"Browser history entries    : {summary.get('total_browser_history_entries', 0)}")
    print(f"Deleted files              : {summary.get('total_deleted_found', 'N/A')}")


if __name__ == "__main__":
    main()
