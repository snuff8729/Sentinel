"""Bulk-import a folder of local images into the saved-image library.

Usage:
    .venv/Scripts/python.exe scripts/import_library.py "<folder>"

Walks the folder recursively, imports .png/.jpg/.jpeg/.webp files via
LibraryService.import_image. Idempotent — re-runs skip already-imported
content (dedup by sha256).

Resolves data_dir using the same precedence as the runtime: DATA_DIR env
var → DB Setting `data_dir` → fallback `'data'`. This keeps imports landing
where the FastAPI `/data` static mount serves from."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.engine import create_engine_and_tables, get_session
from app.db.repository import get_setting
from app.saved.library import LibraryService

EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _resolve_data_dir(engine) -> str:
    env = os.environ.get("DATA_DIR")
    if env:
        return env
    with get_session(engine) as session:
        setting = get_setting(session, "data_dir")
    return setting or "data"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: import_library.py <folder>", file=sys.stderr)
        return 1
    folder = Path(sys.argv[1])
    if not folder.is_dir():
        print(f"not a directory: {folder}", file=sys.stderr)
        return 1

    engine = create_engine_and_tables()
    data_dir = _resolve_data_dir(engine)
    print(f"data_dir: {data_dir}")
    service = LibraryService(engine=engine, data_dir=data_dir)

    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXTS]
    total = len(files)
    print(f"found {total} files in {folder}")
    if total == 0:
        return 0

    imported = already = skipped = errors = 0
    for i, path in enumerate(files, 1):
        try:
            result = service.import_image(path)
            status = result.get("status")
            if status == "imported":
                imported += 1
            elif status == "already_imported":
                already += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  error on {path.name}: {e}", file=sys.stderr)
        if i % 50 == 0 or i == total:
            print(f"[{i}/{total}] imported={imported} already={already} skipped={skipped} errors={errors}")

    print(f"done: imported={imported} already={already} skipped={skipped} errors={errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
