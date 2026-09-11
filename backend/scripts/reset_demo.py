"""Reset the demo: delete the SQLite DB + generated evidence files, then reseed.

Usage:
  .venv/bin/python -m scripts.reset_demo               # empty institution (your data only)
  .venv/bin/python -m scripts.reset_demo --with-demo   # full synthetic demo roster
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB = BASE / "careerdna.db"
STORAGE = BASE / "storage"


def main() -> None:
    with_demo = "--with-demo" in sys.argv
    print(f"Resetting CareerDNA demo... ({'full demo roster' if with_demo else 'empty institution'})")
    for f in (DB, Path(str(DB) + "-journal"), Path(str(DB) + "-wal"), Path(str(DB) + "-shm")):
        if f.exists():
            f.unlink()
            print(f"  removed {f.name}")
    if STORAGE.exists():
        shutil.rmtree(STORAGE)
        print("  cleared storage/")

    from app.db.session import Base, engine
    Base.metadata.create_all(engine)

    from scripts.seed_demo import main as seed_main
    seed_main(analysis=True, demo_students=with_demo)
    print("Reset complete.")


if __name__ == "__main__":
    main()
