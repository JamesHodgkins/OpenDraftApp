#!/usr/bin/env python3
"""Extract embedded ODX thumbnails for Linux thumbnailer integrations.

Expected CLI contract (matching freedesktop thumbnailer placeholders):
  linux_odx_thumbnailer.py <input-uri-or-path> <output-png-path> [size]

The optional size argument is accepted for compatibility but currently ignored.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse


_THUMBNAIL_ENTRY = "assets/thumbnail.png"


def _to_local_path(input_value: str) -> Path:
    """Convert a URI or plain path to a local filesystem path."""
    parsed = urlparse(input_value)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        raise ValueError(f"Unsupported URI scheme: {parsed.scheme}")
    return Path(input_value)


def extract_thumbnail_bytes(odx_path: Path) -> bytes | None:
    """Return embedded thumbnail bytes from an ODX file, if present."""
    try:
        with zipfile.ZipFile(odx_path, "r") as zf:
            if _THUMBNAIL_ENTRY not in zf.namelist():
                return None
            return zf.read(_THUMBNAIL_ENTRY)
    except (zipfile.BadZipFile, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract an embedded ODX thumbnail into a PNG output path.",
    )
    parser.add_argument("input", help="Input .odx file path or file:// URI")
    parser.add_argument("output", help="Output PNG path")
    parser.add_argument("size", nargs="?", help="Requested thumbnail size (ignored)")
    args = parser.parse_args(argv)

    try:
        input_path = _to_local_path(args.input)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    thumbnail = extract_thumbnail_bytes(input_path)
    if not thumbnail:
        return 3

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(thumbnail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
