#!/usr/bin/env python3
"""Install per-user Linux ODX MIME + thumbnailer integration.

This script is intended for development and early distribution before a full
installer exists. It installs files under ~/.local/share.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


_MIME_TYPE = "application/vnd.opendraft.odx"
_MIME_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<mime-info xmlns=\"http://www.freedesktop.org/standards/shared-mime-info\">
  <mime-type type=\"application/vnd.opendraft.odx\">
    <comment>OpenDraft Drawing</comment>
    <glob pattern=\"*.odx\"/>
  </mime-type>
</mime-info>
"""


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

    repo_root = Path(__file__).resolve().parents[1]
    thumb_script = repo_root / "scripts" / "linux_odx_thumbnailer.py"

    local_share = Path.home() / ".local" / "share"
    mime_packages = local_share / "mime" / "packages"
    thumbnailers = local_share / "thumbnailers"

    mime_packages.mkdir(parents=True, exist_ok=True)
    thumbnailers.mkdir(parents=True, exist_ok=True)

    mime_xml_path = mime_packages / "opendraft-odx.xml"
    mime_xml_path.write_text(_MIME_XML, encoding="utf-8")

    # Note: %u/%o/%s are freedesktop thumbnailer placeholders.
    thumb_entry = (
        "[Thumbnailer Entry]\n"
        "Version=1.0\n"
        "Type=X-Thumbnailer\n"
        "Name=OpenDraft ODX Thumbnailer\n"
        "TryExec=python3\n"
        f"Exec=python3 \"{thumb_script}\" %u %o %s\n"
        f"MimeType={_MIME_TYPE};\n"
    )
    thumb_entry_path = thumbnailers / "opendraft-odx.thumbnailer"
    thumb_entry_path.write_text(thumb_entry, encoding="utf-8")

    _run_if_available("update-mime-database", [str(local_share / "mime")])

    print("Installed Linux ODX thumbnailer integration:")
    print(f"  MIME XML:       {mime_xml_path}")
    print(f"  Thumbnailer:    {thumb_entry_path}")
    print("You may need to log out/in or clear thumbnail cache to see changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
