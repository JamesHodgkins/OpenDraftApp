#!/usr/bin/env python3
"""Uninstall per-user Linux ODX MIME + thumbnailer integration."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _run_if_available(cmd: str, args: list[str]) -> None:
    exe = shutil.which(cmd)
    if not exe:
        return
    subprocess.run([exe, *args], check=False)


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("This helper only supports Linux (freedesktop thumbnailers).")
        print(f"Detected platform: {sys.platform}")
        return 2

    local_share = Path.home() / ".local" / "share"

    mime_xml_path = local_share / "mime" / "packages" / "opendraft-odx.xml"
    thumb_entry_path = local_share / "thumbnailers" / "opendraft-odx.thumbnailer"

    if mime_xml_path.exists():
        mime_xml_path.unlink()
    if thumb_entry_path.exists():
        thumb_entry_path.unlink()

    _run_if_available("update-mime-database", [str(local_share / "mime")])

    print("Removed Linux ODX thumbnailer integration files (if present).")
    print(f"  MIME XML:    {mime_xml_path}")
    print(f"  Thumbnailer: {thumb_entry_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
