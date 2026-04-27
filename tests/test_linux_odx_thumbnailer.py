from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path


def _load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location("linux_odx_thumbnailer", str(path))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_thumbnail_bytes_reads_embedded_png(tmp_path: Path) -> None:
    script_path = Path("scripts") / "linux_odx_thumbnailer.py"
    module = _load_module_from_path(script_path)

    odx_path = tmp_path / "with_thumb.odx"
    expected = b"png-data"
    with zipfile.ZipFile(odx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("document.json", "{}")
        zf.writestr("assets/thumbnail.png", expected)

    actual = module.extract_thumbnail_bytes(odx_path)
    assert actual == expected


def test_extract_thumbnail_bytes_returns_none_without_embedded_png(tmp_path: Path) -> None:
    script_path = Path("scripts") / "linux_odx_thumbnailer.py"
    module = _load_module_from_path(script_path)

    odx_path = tmp_path / "without_thumb.odx"
    with zipfile.ZipFile(odx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("document.json", "{}")

    actual = module.extract_thumbnail_bytes(odx_path)
    assert actual is None
