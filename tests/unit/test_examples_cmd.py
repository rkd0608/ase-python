from __future__ import annotations

from typer.testing import CliRunner

from ase.cli.examples_cmd import app


def test_examples_run_renders_cli_error_without_traceback(monkeypatch) -> None:
    def _raise(_: list[str] | None) -> list[object]:
        from ase.errors import CLIError

        raise CLIError("requires the ASE source checkout")

    monkeypatch.setattr("ase.cli.examples_cmd.run_examples", _raise)
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 1
    assert "requires the ASE source checkout" in result.stdout
    assert "Traceback" not in result.stdout
