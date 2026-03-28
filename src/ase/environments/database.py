"""DuckDB-backed database simulator for ASE scenarios."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import duckdb

from ase.environments.base import EnvironmentProvider
from ase.errors import ASEError
from ase.scenario.model import DatabaseSeed


class DatabaseEnvironment(EnvironmentProvider):
    """Provide deterministic SQL state so agent mutations can be tested safely."""

    def __init__(
        self,
        seed: DatabaseSeed | None = None,
        *,
        schema_path: str | None = None,
        schema_file: str | None = None,
    ) -> None:
        self._seed = seed
        self._schema_path = schema_path or schema_file
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._lock = asyncio.Lock()
        self.access_log: list[str] = []

    async def setup(self) -> None:
        """Open the in-memory database and apply schema and seed statements."""
        self._conn = duckdb.connect(":memory:")
        await self._apply_schema()
        await self._apply_seed_statements()

    async def teardown(self) -> None:
        """Close the in-memory connection so concurrent runs stay isolated."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self.access_log.clear()

    async def execute(self, sql: str) -> list[dict[str, Any]] | dict[str, Any]:
        """Run one SQL statement and preserve enough shape for assertions."""
        async with self._lock:
            conn = self._require_conn()
            self.access_log.append(sql)
            try:
                cursor = conn.execute(sql)
            except duckdb.ParserException as exc:
                return {"ok": False, "error": str(exc)}
            if not cursor.description:
                return {"ok": True}
            columns = [str(item[0]) for item in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row, strict=False)) for row in rows]

    async def query(self, sql: str) -> list[dict[str, Any]] | dict[str, Any]:
        """Expose query as an alias so older call sites stay valid."""
        return await self.execute(sql)

    async def seed_data(self, fixtures: list[dict[str, Any]]) -> None:
        """Apply table/row fixtures with contextual errors on constraint failures."""
        async with self._lock:
            conn = self._require_conn()
            for fixture in fixtures:
                await self._insert_fixture_rows(conn, fixture)

    async def seed(self, fixtures: list[dict[str, Any]]) -> None:
        """Keep a short seed alias for tests and legacy callers."""
        await self.seed_data(fixtures)

    async def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Dump table contents so post-run diffs and assertions stay deterministic."""
        async with self._lock:
            conn = self._require_conn()
            tables = conn.execute("SHOW TABLES").fetchall()
            snapshot: dict[str, list[dict[str, Any]]] = {}
            for (table_name,) in tables:
                snapshot[str(table_name)] = await self._select_all(conn, str(table_name))
            return snapshot

    async def export_state(self) -> dict[str, list[dict[str, Any]]]:
        """Keep a second state-dump alias for compatibility with older tests."""
        return await self.snapshot()

    async def _apply_schema(self) -> None:
        """Load schema SQL from disk when a scenario requested an explicit file."""
        if self._schema_path is None:
            return
        schema_path = Path(self._schema_path)
        if not schema_path.exists():
            raise ASEError(f"database schema file not found: {schema_path}")
        sql = schema_path.read_text(encoding="utf-8")
        if not sql.strip():
            return
        self._require_conn().execute(sql)

    async def _apply_seed_statements(self) -> None:
        """Preload deterministic seed statements declared in the scenario."""
        if self._seed is None:
            return
        for statement in self._seed.statements:
            await self.execute(statement)

    async def _insert_fixture_rows(
        self,
        conn: duckdb.DuckDBPyConnection,
        fixture: dict[str, Any],
    ) -> None:
        """Insert one fixture payload with table-specific context on failure."""
        table = str(fixture.get("table", "")).strip()
        rows = fixture.get("rows", [])
        if not table or not isinstance(rows, list):
            raise ASEError("invalid database seed fixture")
        for row in rows:
            columns = list(dict(row).keys())
            placeholders = ", ".join(["?"] * len(columns))
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            self.access_log.append(sql)
            try:
                conn.execute(sql, [row[column] for column in columns])
            except duckdb.Error as exc:
                raise ASEError(f"failed to seed database table {table}: {exc}") from exc

    async def _select_all(
        self,
        conn: duckdb.DuckDBPyConnection,
        table_name: str,
    ) -> list[dict[str, Any]]:
        """Read complete table contents so snapshots stay easy to inspect."""
        cursor = conn.execute(f"SELECT * FROM {table_name}")
        columns = [str(item[0]) for item in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def _require_conn(self) -> duckdb.DuckDBPyConnection:
        """Fail early when callers use the simulator outside its lifecycle."""
        if self._conn is None:
            raise ASEError("database environment is not initialized")
        return self._conn
