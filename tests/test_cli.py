"""Tests for the CLI entry point."""

from click.testing import CliRunner
from src.cli import main


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "evaluate" in result.output or "CAD" in result.output

    def test_dataset_generate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
        runner = CliRunner()
        result = runner.invoke(main, ["dataset", "generate"])
        assert result.exit_code == 0
        assert "Generated 20" in result.output

    def test_compare_missing_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ["compare", "/nonexistent1.dxf", "/nonexistent2.dxf"])
        assert result.exit_code != 0
