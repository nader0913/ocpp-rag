#!/usr/bin/env python3
"""Download freely available EV charging specification documents.

Downloads OCPP 1.6 specs and the OCA Plug & Charge whitepaper into
the source_docs/ tree expected by the rest of the ocpp-rag pipeline.

Usage:
    python scripts/download_docs.py
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DOCS_DIR = ROOT_DIR / "source_docs"

DOWNLOADS: list[dict[str, str]] = [
    # --- OCPP 1.6 specs ---
    {
        "url": "https://raw.githubusercontent.com/mobilityhouse/ocpp/master/docs/v16/ocpp-1.6.pdf",
        "dest": "ocpp-1.6/ocpp-1.6.pdf",
    },
    {
        "url": "https://raw.githubusercontent.com/mobilityhouse/ocpp/master/docs/v16/ocpp-j-1.6-specification.pdf",
        "dest": "ocpp-1.6/ocpp-j-1.6-specification.pdf",
    },
    # --- OCA Plug & Charge whitepaper ---
    {
        "url": "https://openchargealliance.org/wp-content/uploads/2023/11/ocpp_1_6_ISO_15118_v10.pdf",
        "dest": "other/ocpp_1_6_ISO_15118_v10.pdf",
    },
]

USER_AGENT = (
    "Mozilla/5.0 (compatible; ocpp-rag-downloader/1.0; "
    "+https://github.com/nader0913/ocpp-rag)"
)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def download_file(url: str, dest: Path) -> bool:
    """Download *url* to *dest* with retries. Return True on success."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            dest.write_bytes(data)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY_SECONDS * attempt
                print(f"  Attempt {attempt}/{MAX_RETRIES} failed: {exc}")
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [ERROR] Failed after {MAX_RETRIES} attempts: {exc}")
                return False
    return False  # unreachable, but keeps mypy happy


def main() -> None:
    downloaded: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for entry in DOWNLOADS:
        dest = SOURCE_DOCS_DIR / entry["dest"]
        filename = entry["dest"]

        if dest.exists():
            print(f"[SKIP] {filename}")
            skipped.append(filename)
            continue

        print(f"[DOWNLOAD] {filename}...")
        dest.parent.mkdir(parents=True, exist_ok=True)

        if download_file(entry["url"], dest):
            size_kb = dest.stat().st_size / 1024
            print(f"  Saved ({size_kb:.0f} KB)")
            downloaded.append(filename)
        else:
            failed.append(filename)

    # --- Summary ---
    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Downloaded : {len(downloaded)}")
    print(f"  Skipped    : {len(skipped)}")
    print(f"  Failed     : {len(failed)}")

    if downloaded:
        print()
        print("Downloaded files:")
        for f in downloaded:
            print(f"  + {f}")
    if skipped:
        print()
        print("Skipped (already exist):")
        for f in skipped:
            print(f"  - {f}")
    if failed:
        print()
        print("Failed downloads:")
        for f in failed:
            print(f"  ! {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
