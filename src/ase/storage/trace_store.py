"""Persistent local storage for ASE traces."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import structlog

from ase.errors import TraceSerializationError
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
                framework TEXT,
                certification_level TEXT,
                started_at_ms REAL,
                trace_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS baselines (
                scenario_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                status TEXT NOT NULL,
                run_result TEXT NOT NULL,
                evaluation_status TEXT,
                framework TEXT,
                ase_score REAL,
                created_at_ms REAL NOT NULL
            )
            """
        )
        self._ensure_trace_columns()
        self._ensure_baseline_columns()
        self._backfill_trace_runtime_columns()
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
                ase_score, runtime_mode, framework, certification_level, started_at_ms, trace_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored.trace_id,
                stored.scenario_id,
                stored.scenario_name,
                stored.status.value,
                evaluation_status,
                score_value,
                stored.runtime_provenance.mode if stored.runtime_provenance else None,
                stored.runtime_provenance.framework if stored.runtime_provenance else None,
                stored.certification_level.value if stored.certification_level else None,
                stored.started_at_ms,
                serialize(stored),
            ),
        )
        conn.commit()
        log.debug("trace_saved", trace_id=stored.trace_id)

    async def set_baseline(self, scenario_id: str, trace_id: str) -> dict[str, Any]:
        """Pin one stored trace as the baseline for a scenario."""
        conn = _require_conn(self._conn)
        trace = await self.get_trace(trace_id)
        if trace is None:
            raise TraceSerializationError(f"baseline trace not found: {trace_id}")
        if trace.scenario_id != scenario_id:
            raise TraceSerializationError(
                f"baseline scenario mismatch: expected {scenario_id}, got {trace.scenario_id}"
            )
        created_at_ms = time.time() * 1000
        evaluation_status = None
        if trace.evaluation is not None:
            evaluation_status = "passed" if trace.evaluation.passed else "failed"
        run_result = (
            "passed"
            if trace.status.value == "passed" and evaluation_status != "failed"
            else "failed"
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO baselines (
                scenario_id, trace_id, scenario_name, status, run_result,
                evaluation_status, framework, ase_score, created_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                trace.trace_id,
                trace.scenario_name,
                trace.status.value,
                run_result,
                evaluation_status,
                trace.runtime_provenance.framework if trace.runtime_provenance else None,
                trace.evaluation.ase_score if trace.evaluation is not None else None,
                created_at_ms,
            ),
        )
        conn.commit()
        row = await self.get_baseline(scenario_id)
        assert row is not None
        return row

    async def get_baseline(self, scenario_id: str) -> dict[str, Any] | None:
        """Return one pinned baseline row for a scenario."""
        conn = _require_conn(self._conn)
        row = conn.execute(
            "SELECT * FROM baselines WHERE scenario_id = ?",
            (scenario_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    async def list_baselines(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent pinned baselines."""
        conn = _require_conn(self._conn)
        rows = conn.execute(
            "SELECT * FROM baselines ORDER BY created_at_ms DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    async def clear_baselines(self, scenario_id: str | None = None) -> int:
        """Remove one pinned baseline or all of them."""
        conn = _require_conn(self._conn)
        if scenario_id:
            cursor = conn.execute("DELETE FROM baselines WHERE scenario_id = ?", (scenario_id,))
        else:
            cursor = conn.execute("DELETE FROM baselines")
        conn.commit()
        return cursor.rowcount

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

    def _ensure_trace_columns(self) -> None:
        """Upgrade older trace tables with any missing columns."""
        conn = _require_conn(self._conn)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(traces)").fetchall()
            if row["name"]
        }
        if "framework" not in columns:
            conn.execute("ALTER TABLE traces ADD COLUMN framework TEXT")

    def _ensure_baseline_columns(self) -> None:
        """Upgrade older baseline tables with any missing columns."""
        conn = _require_conn(self._conn)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(baselines)").fetchall()
            if row["name"]
        }
        if "evaluation_status" not in columns:
            conn.execute("ALTER TABLE baselines ADD COLUMN evaluation_status TEXT")

    def _backfill_trace_runtime_columns(self) -> None:
        """Populate new runtime columns on older rows when possible."""
        conn = _require_conn(self._conn)
        rows = conn.execute(
            "SELECT trace_id, trace_json, runtime_mode, framework FROM traces"
        ).fetchall()
        for row in rows:
            trace_id = row["trace_id"]
            runtime_mode = row["runtime_mode"]
            framework = row["framework"]
            if runtime_mode is not None and framework is not None:
                continue
            try:
                trace = deserialize(row["trace_json"])
            except Exception as exc:  # noqa: BLE001
                log.debug("trace_backfill_skipped", trace_id=trace_id, error=str(exc))
                continue
            runtime = trace.runtime_provenance
            if runtime is None:
                continue
            conn.execute(
                "UPDATE traces SET runtime_mode = ?, framework = ? WHERE trace_id = ?",
                (runtime.mode, runtime.framework, trace_id),
            )


def sanitize_trace_for_storage(trace: Trace) -> Trace:
    """Copy a trace into a storage-safe form without mutating the caller."""
    payload = json.loads(trace.model_dump_json())
    return Trace.model_validate(payload)


def _require_conn(conn: sqlite3.Connection | None) -> sqlite3.Connection:
    """Ensure the trace store is initialized before use."""
    if conn is None:
        raise RuntimeError("trace store is not initialized")
    return conn
