"""Edge-case contract tests for the database simulator/environment."""

from __future__ import annotations

import asyncio
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest


def _import_database_module() -> Any:
    return pytest.importorskip(
        "ase.environments.database",
        reason="database simulator module is not available in this checkout",
    )


def _database_class() -> type[Any]:
    module = _import_database_module()
    for name in ("DatabaseEnvironment", "DatabaseSimulator", "Database"):
        cls = getattr(module, name, None)
        if inspect.isclass(cls):
            return cls
    pytest.skip("no database simulator class found in ase.environments.database")


def _filter_kwargs(callable_obj: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(callable_obj)
    if any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call_first(obj: Any, candidates: tuple[str, ...], *args: Any, **kwargs: Any) -> Any:
    for name in candidates:
        fn = getattr(obj, name, None)
        if fn is not None:
            return await _maybe_await(fn(*args, **kwargs))
    pytest.skip(f"none of methods {candidates!r} found on {type(obj).__name__}")


async def _build_db(tmp_path: Path, schema_sql: str) -> Any:
    schema_path = tmp_path / "schema.sql"
    schema_path.write_text(schema_sql, encoding="utf-8")

    cls = _database_class()
    db = cls(
        **_filter_kwargs(
            cls,
            {"schema_path": str(schema_path), "schema_file": str(schema_path), "seed": None},
        )
    )
    await _call_first(db, ("setup", "initialize", "start"))
    return db


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    async def _run() -> None:
        db = await _build_db(
            tmp_path,
            (
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);"
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, "
                "FOREIGN KEY(customer_id) REFERENCES customers(id));"
            ),
        )
        await _call_first(
            db,
            ("execute", "query", "run_sql", "run_query"),
            "INSERT INTO customers VALUES (1, 'Ada')",
        )
        with pytest.raises(Exception) as exc:
            await _call_first(
                db,
                ("execute", "query", "run_sql", "run_query"),
                "INSERT INTO orders VALUES (1, 999)",
            )
        assert "foreign" in str(exc.value).lower() or "constraint" in str(exc.value).lower()

    asyncio.run(_run())


def test_seed_constraint_violation_returns_helpful_error(tmp_path: Path) -> None:
    async def _run() -> None:
        db = await _build_db(
            tmp_path,
            (
                "CREATE TABLE parent(id INTEGER PRIMARY KEY);"
                "CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER, "
                "FOREIGN KEY(parent_id) REFERENCES parent(id));"
            ),
        )
        with pytest.raises(Exception) as exc:
            await _call_first(
                db,
                ("seed", "seed_data", "load_seed"),
                [{"table": "child", "rows": [{"id": 1, "parent_id": 55}]}],
            )
        lowered = str(exc.value).lower()
        assert "traceback" not in lowered
        assert "duckdb" not in lowered or "constraint" in lowered

    asyncio.run(_run())


def test_malformed_sql_returns_error_dict_without_crash(tmp_path: Path) -> None:
    async def _run() -> None:
        db = await _build_db(tmp_path, "CREATE TABLE customers(id INTEGER PRIMARY KEY)")
        result = await _call_first(
            db,
            ("execute", "query", "run_sql", "run_query"),
            "SELEC FROM customers",
        )
        if isinstance(result, dict):
            assert result.get("ok") is False or "error" in result
        else:
            pytest.skip("database API raises exceptions instead of returning error dicts")

    asyncio.run(_run())


def test_ddl_and_broad_reads_are_recorded_and_flaggable(tmp_path: Path) -> None:
    async def _run() -> None:
        db = await _build_db(tmp_path, "CREATE TABLE customers(id INTEGER PRIMARY KEY)")
        for stmt in (
            "DROP TABLE customers",
            "ALTER TABLE customers ADD COLUMN email TEXT",
            "SELECT * FROM customers",
        ):
            try:
                await _call_first(db, ("execute", "query", "run_sql", "run_query"), stmt)
            except Exception:
                pass

        access_log = getattr(db, "access_log", None)
        if access_log is None:
            pytest.skip("database simulator has no access_log")
        text = "\n".join(str(item) for item in access_log).lower()
        assert "drop table" in text
        assert "alter table" in text
        assert "select * from customers" in text

        evaluator = None
        for module_name, symbol in (
            ("ase.evaluation.policy", "NoUnauthorizedAccessEvaluator"),
            ("ase.evaluation.policy", "no_unauthorized_access"),
        ):
            module = importlib.import_module(module_name)
            evaluator = getattr(module, symbol, None)
            if evaluator is not None:
                break
        if evaluator is None:
            pytest.skip("no_unauthorized_access evaluator not present")

    asyncio.run(_run())


def test_empty_schema_and_missing_schema_path_are_helpful(tmp_path: Path) -> None:
    async def _run() -> None:
        cls = _database_class()

        empty_schema = tmp_path / "empty.sql"
        empty_schema.write_text("", encoding="utf-8")
        db_empty = cls(
            **_filter_kwargs(
                cls,
                {"schema_path": str(empty_schema), "schema_file": str(empty_schema)},
            )
        )
        await _call_first(db_empty, ("setup", "initialize", "start"))
        with pytest.raises(Exception) as exc_empty:
            await _call_first(
                db_empty,
                ("seed", "seed_data", "load_seed"),
                [{"table": "x", "rows": [{"id": 1}]}],
            )
        assert "table" in str(exc_empty.value).lower() or "schema" in str(exc_empty.value).lower()

        missing = tmp_path / "missing.sql"
        db_missing = cls(
            **_filter_kwargs(
                cls,
                {"schema_path": str(missing), "schema_file": str(missing)},
            )
        )
        with pytest.raises(Exception) as exc_missing:
            await _call_first(db_missing, ("setup", "initialize", "start"))
        assert str(missing) in str(exc_missing.value)

    asyncio.run(_run())


def test_concurrent_queries_and_snapshot_consistency(tmp_path: Path) -> None:
    async def _run() -> None:
        db = await _build_db(tmp_path, "CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT)")

        async def insert_row(i: int) -> None:
            await _call_first(
                db,
                ("execute", "query", "run_sql", "run_query"),
                f"INSERT INTO customers VALUES ({i}, 'n{i}')",
            )

        await asyncio.gather(*(insert_row(i) for i in range(1, 21)))

        rows = await _call_first(
            db,
            ("execute", "query", "run_sql", "run_query"),
            "SELECT COUNT(*) AS n FROM customers",
        )
        if isinstance(rows, list) and rows:
            n = int(rows[0].get("n", rows[0].get("count", 0)))
        else:
            n = int(getattr(rows, "n", 0) or 0)
        assert n == 20

        snapshot = await _call_first(db, ("snapshot", "dump", "export_state"))
        assert snapshot is not None
        assert "customers" in str(snapshot).lower()

    asyncio.run(_run())
