"""The tracker: a Google Sheet (or a folder of CSVs for local testing) with four tabs."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

TABS: dict[str, list[str]] = {
    # One row per course deliverable. status: not_started | in_progress | blocked | done
    "Deliverables": ["id", "deliverable", "owner", "due_date", "status", "last_update", "notes", "depends_on"],
    # Everyone the agent may contact. contact_via is the key of whoever receives reminders
    # for this person's deliverables (themselves, or e.g. their FSS assistant).
    # role: coordinator | prof | assistant. channels: "email", "slack" or "email,slack".
    "People": ["key", "name", "role", "email", "slack_email", "contact_via", "channels"],
    # Every message the agent sent or queued. status: pending | approved | rejected | sent | failed
    "Messages": ["id", "created_at", "deliverable_ids", "recipient_key", "channel", "subject", "body", "status", "sent_at"],
    # Bookkeeping between runs (e.g. where Slack reading left off).
    "State": ["key", "value"],
}


class Store:
    def read(self, tab: str) -> list[dict[str, str]]:
        raise NotImplementedError

    def append(self, tab: str, row: dict[str, str]) -> None:
        raise NotImplementedError

    def update(self, tab: str, key_col: str, key: str, changes: dict[str, str]) -> bool:
        """Update the first row whose key_col equals key. Returns False if there is none."""
        raise NotImplementedError

    def get_state(self, key: str, default: str = "") -> str:
        for row in self.read("State"):
            if row["key"] == key:
                return row["value"]
        return default

    def set_state(self, key: str, value: str) -> None:
        if not self.update("State", "key", key, {"value": value}):
            self.append("State", {"key": key, "value": value})


class LocalStore(Store):
    """CSV files named after the tabs. Handy for trying the agent without Google setup."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        for tab, headers in TABS.items():
            path = self._path(tab)
            if not path.exists():
                self._write(tab, [], headers)

    def _path(self, tab: str) -> Path:
        return self.dir / f"{tab.lower()}.csv"

    def _write(self, tab: str, rows: list[dict[str, str]], headers: list[str] | None = None) -> None:
        with self._path(tab).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers or TABS[tab])
            writer.writeheader()
            writer.writerows(rows)

    def read(self, tab: str) -> list[dict[str, str]]:
        with self._path(tab).open(newline="") as f:
            return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(f)]

    def append(self, tab: str, row: dict[str, str]) -> None:
        rows = self.read(tab)
        rows.append({h: row.get(h, "") for h in TABS[tab]})
        self._write(tab, rows)

    def update(self, tab: str, key_col: str, key: str, changes: dict[str, str]) -> bool:
        rows = self.read(tab)
        for row in rows:
            if row[key_col] == key:
                row.update(changes)
                self._write(tab, rows)
                return True
        return False


class SheetStore(Store):
    """A Google Sheet shared (as Editor) with a service account."""

    def __init__(self, sheet_id: str, service_account_info: dict):
        import gspread

        self.sheet = gspread.service_account_from_dict(service_account_info).open_by_key(sheet_id)
        self._cache: dict[str, list[dict[str, str]]] = {}

    def init_tabs(self) -> None:
        """Create any missing tabs with their header rows."""
        existing = {ws.title for ws in self.sheet.worksheets()}
        for tab, headers in TABS.items():
            if tab not in existing:
                ws = self.sheet.add_worksheet(title=tab, rows=200, cols=len(headers))
                ws.update([headers], "A1")

    def read(self, tab: str) -> list[dict[str, str]]:
        if tab not in self._cache:
            records = self.sheet.worksheet(tab).get_all_records(numericise_ignore=["all"])
            self._cache[tab] = [{k: str(v) for k, v in r.items()} for r in records]
        return [dict(r) for r in self._cache[tab]]

    def append(self, tab: str, row: dict[str, str]) -> None:
        self.sheet.worksheet(tab).append_row([row.get(h, "") for h in TABS[tab]], value_input_option="RAW")
        self._cache.pop(tab, None)

    def update(self, tab: str, key_col: str, key: str, changes: dict[str, str]) -> bool:
        ws = self.sheet.worksheet(tab)
        headers = ws.row_values(1)
        for i, row in enumerate(self.read(tab)):
            if row.get(key_col) == key:
                for col, value in changes.items():
                    ws.update_cell(i + 2, headers.index(col) + 1, value)
                self._cache.pop(tab, None)
                return True
        return False


def open_store(config: dict, base_dir: Path) -> Store:
    store_cfg = config["store"]
    if store_cfg["backend"] == "local":
        return LocalStore(base_dir / store_cfg["local_dir"])
    return SheetStore(os.environ["SHEET_ID"], json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]))
