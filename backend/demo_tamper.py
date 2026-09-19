#!/usr/bin/env python3
"""
Deliberate tamper demo for judges.

1. Registers a small sample file as evidence (or uses an existing path)
2. Runs integrity check → should be OK
3. Changes one byte on disk
4. Runs integrity check again → hash_mismatch

Usage:
  python demo_tamper.py --case CASE-XXXX --token $TOKEN
  # or without API, pure local:
  python demo_tamper.py --local
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import urllib.request


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def api(method: str, url: str, token: str, data: dict | None = None) -> dict:
    body = None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def demo_local():
    print("=== LOCAL TAMPER DEMO (no API) ===\n")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "statement.txt"
        path.write_text("This is the original statement.\n", encoding="utf-8")
        original = sha256(path)
        print(f"1. Created file: {path.name}")
        print(f"   Fingerprint:  {original}\n")

        print("2. First check: fingerprints must match → OK")
        assert sha256(path) == original
        print("   Result: UNCHANGED\n")

        # flip one byte
        data = bytearray(path.read_bytes())
        data[0] = data[0] ^ 0x01
        path.write_bytes(data)
        altered = sha256(path)
        print("3. Changed one byte in the file (simulating tampering)")
        print(f"   New fingerprint: {altered}\n")

        print("4. Second check:")
        if altered != original:
            print("   Result: ALTERED — fingerprints no longer match.")
            print("   The system can show the file is not the same as when collected.")
        else:
            print("   ERROR: hashes still match (should not happen)")
            sys.exit(1)


def demo_api(base: str, case: str, token: str):
    print("=== API TAMPER DEMO ===\n")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "witness_note.txt"
        path.write_text("I saw the suspect leave at 14:00.\n", encoding="utf-8")
        print(f"1. Sample file at {path}")
        print(f"   Fingerprint: {sha256(path)}\n")

        print("2. Register as evidence on the case…")
        # Use evidence endpoint — adjust if your path differs
        try:
            api(
                "POST",
                f"{base}/evidence/",
                token,
                {
                    "case_number": case,
                    "file_path": str(path),
                    "collected_by": "demo",
                    "notes": "Tamper demo sample",
                },
            )
            print("   Registered.\n")
        except Exception as e:
            print(f"   Register failed: {e}")
            print("   (Case must exist. Create a case first.)")
            sys.exit(1)

        print("3. Integrity check (before tamper)…")
        before = api("POST", f"{base}/data-sources/{case}/integrity-check", token)
        print(f"   ok={before.get('ok')} warnings={before.get('warnings')}\n")

        print("4. Tampering: flip one byte on disk…")
        data = bytearray(path.read_bytes())
        data[0] ^= 0x01
        path.write_bytes(data)
        print(f"   New fingerprint: {sha256(path)}\n")

        print("5. Integrity check (after tamper)…")
        after = api("POST", f"{base}/data-sources/{case}/integrity-check", token)
        print(f"   ok={after.get('ok')} warnings={after.get('warnings')}")
        for item in after.get("items", []):
            if item.get("status") != "ok":
                print(f"   → {item.get('filename')}: {item.get('status')}")
                print(f"     {item.get('message')}")

        if after.get("warnings", 0) > 0:
            print("\nSUCCESS: System detected the change.")
        else:
            print("\nFAILED: System did not report a warning.")
            sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--local", action="store_true", help="No API, pure hash demo")
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--case", help="Case number")
    p.add_argument("--token", help="Bearer token")
    args = p.parse_args()

    if args.local:
        demo_local()
    else:
        if not args.case or not args.token:
            print("Need --case and --token (or use --local)")
            sys.exit(1)
        demo_api(args.base.rstrip("/"), args.case, args.token)


if __name__ == "__main__":
    main()
