"""Persistent local storage for ASE traces."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import structlog

from ase.trace.model import Trace
from ase.trace.serializer import deserialize, serialize

log = structlog.get_logger(__name__)


class TraceStore:
    """Store and query traces in a local SQLite database."""

    _DEFAULT_PATH = Path.home() / ".ase" / "traces.db"

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or self._DEFAULT_PATH
        self._conn: sqlite3.Connection | None = None

    async def setup(self) -> None:
        """Create the database and table if they do not already exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                status TEXT NOT NULL,
                evaluation_status TEXT,
                ase_score REAL,
                runtime_mode TEXT,
                certification_level TEXT,
                started_at_ms REAL,
                trace_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        log.debug("trace_store_ready", path=str(self._db_path))

    async def close(self) -> None:
        """Close the SQLite connection if it is open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    async def save_trace(self, trace: Trace, ase_score: float | None = None) -> None:
        """Persist one trace and its summary columns."""
        conn = _require_conn(self._conn)
        stored = sanitize_trace_for_storage(trace)
        evaluation_status = None
        if stored.evaluation is not None:
            evaluation_status = "passed" if stored.evaluation.passed else "failed"
        score_value = ase_score
        if score_value is None and stored.evaluation is not None:
            score_value = stored.evaluation.ase_score
        conn.execute(
            """
            INSERT OR REPLACE INTO traces (
                trace_id, scenario_id, scenario_name, status, evaluation_status,
                ase_score, runtime_mode, certification_level, started_at_ms, trace_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored.trace_id,
                stored.scenario_id,
                stored.scenario_name,
                stored.status.value,
                evaluation_status,
                score_value,
                stored.runtime_provenance.mode if stored.runtime_provenance else None,
                stored.certification_level.value if stored.certification_level else None,
                stored.started_at_ms,
                serialize(stored),
            ),
        )
        conn.commit()
        log.debug("trace_saved", trace_id=stored.trace_id)

    async def list_traces(
        self,
        scenario_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return recent trace rows for history views."""
        conn = _require_conn(self._conn)
        query = "SELECT * FROM traces"
        clauses: list[str] = []
        params: list[Any] = []
        if scenario_id:
            clauses.append("scenario_id = ?")
            params.append(scenario_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY started_at_ms DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    async def get_trace(self, trace_id: str) -> Trace | None:
        """Return one persisted trace by id."""
        conn = _require_conn(self._conn)
        row = conn.execute(
            "SELECT trace_json FROM traces WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
        if row is None:
            return None
        return deserialize(row["trace_json"])


def sanitize_trace_for_storage(trace: Trace) -> Trace:
    """Copy a trace into a storage-safe form without mutating the caller."""
    payload = json.loads(trace.model_dump_json())
    return Trace.model_validate(payload)


def _require_conn(conn: sqlite3.Connection | None) -> sqlite3.Connection:
    """Ensure the trace store is initialized before use."""
    if conn is None:
        raise RuntimeError("trace store is not initialized")
    return conn
