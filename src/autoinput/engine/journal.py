"""SQLite run journal: survives crashes, powers 'retry failed rows' and error reports."""

import csv
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from autoinput.domain import RowResult, RowStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, started_at TEXT, source TEXT, profile TEXT, dry_run INTEGER
);
CREATE TABLE IF NOT EXISTS rows (
    run_id TEXT, row INTEGER, status TEXT, message TEXT, screenshot TEXT, at TEXT,
    PRIMARY KEY (run_id, row)
);
"""


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as db:
            db.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def start_run(self, run_id: str, source: str, profile: str, dry_run: bool) -> None:
        with self._conn() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    datetime.now().isoformat(timespec="seconds"),
                    source,
                    profile,
                    int(dry_run),
                ),
            )

    def record(self, run_id: str, r: RowResult) -> None:
        with self._conn() as db:
            db.execute(
                "INSERT OR REPLACE INTO rows VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    r.index,
                    r.status.value,
                    r.message,
                    r.screenshot,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def results(self, run_id: str) -> list[RowResult]:
        with self._conn() as db:
            rows = db.execute(
                "SELECT row, status, message, screenshot FROM rows WHERE run_id = ? ORDER BY row",
                (run_id,),
            ).fetchall()
        return [RowResult(i, RowStatus(s), m or "", sc) for i, s, m, sc in rows]

    def export_csv(self, run_id: str, dest: Path) -> Path:
        with dest.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel shows Vietnamese
            writer = csv.writer(f)
            writer.writerow(["row", "status", "message", "screenshot"])
            for r in self.results(run_id):
                writer.writerow([r.index, r.status.value, r.message, r.screenshot or ""])
        return dest
