"""python -m course_agent run [--dry-run] | init-sheet"""

import argparse
import sys
import tomllib
from pathlib import Path

from .agent import Run
from .channels import Channels
from .store import SheetStore, open_store

BASE_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(prog="course_agent")
    parser.add_argument("command", choices=["run", "init-sheet"])
    parser.add_argument("--dry-run", action="store_true", help="print messages instead of sending them and don't write to the tracker")
    parser.add_argument("--config", default=str(BASE_DIR / "config.toml"))
    args = parser.parse_args()

    config = tomllib.loads(Path(args.config).read_text())
    store = open_store(config, BASE_DIR)

    if args.command == "init-sheet":
        if not isinstance(store, SheetStore):
            print("init-sheet only applies to the Google Sheet backend.")
            return 1
        store.init_tabs()
        print("Tabs ready: Deliverables, People, Messages, State.")
        return 0

    digest = Run(config, store, Channels(dry_run=args.dry_run)).execute()
    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
