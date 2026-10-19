from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class Store:
    """One process, short transactions; SQLite lives in the persistent runtime volume."""

    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(root / "management.sqlite3", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS records "
            "(kind TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,id))"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS logs "
            "(sequence INTEGER PRIMARY KEY AUTOINCREMENT, execution TEXT, data TEXT NOT NULL)"
        )
        self.db.commit()

    def put(self, kind: str, identifier: str, data: dict):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO records VALUES (?,?,?) "
                "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
                (kind, identifier, json.dumps(data)),
            )

    def get(self, kind: str, identifier: str) -> dict:
        with self.lock:
            row = self.db.execute(
                "SELECT data FROM records WHERE kind=? AND id=?", (kind, identifier)
            ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return json.loads(row[0])

    def list(self, kind: str) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT data FROM records WHERE kind=? ORDER BY rowid", (kind,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def archive_agent(self, identifier: str, archive_id: str, archive: dict, projects: list[dict]):
        """Remove active membership and disable affected automation in one transaction."""
        with self.lock, self.db:
            removed = self.db.execute(
                "DELETE FROM records WHERE kind='agents' AND id=?", (identifier,)
            )
            if removed.rowcount != 1:
                raise KeyError(identifier)
            self.db.execute(
                "INSERT INTO records VALUES (?,?,?)",
                ("deleted_agents", archive_id, json.dumps(archive)),
            )
            for project in projects:
                self.db.execute(
                    "UPDATE records SET data=? WHERE kind='projects' AND id=?",
                    (json.dumps(project), project["id"]),
                )

    def log(self, execution: str, data: dict):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO logs(execution,data) VALUES (?,?)", (execution, json.dumps(data))
            )

    def logs(self, execution: str, after: int = 0) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT sequence,data FROM logs WHERE execution=? AND sequence>? "
                "ORDER BY sequence LIMIT 200",
                (execution, after),
            ).fetchall()
        return [{"sequence": row[0], **json.loads(row[1])} for row in rows]
