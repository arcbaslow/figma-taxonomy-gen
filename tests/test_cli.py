"""Tests for CLI behavior."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from figma_taxonomy.cli import main


FIXTURES_DIR = Path(__file__).parent / "fixtures"
TMP_ROOT = Path(__file__).parent / ".tmp"


def _tmp_dir() -> TemporaryDirectory:
    TMP_ROOT.mkdir(exist_ok=True)
    return TemporaryDirectory(dir=TMP_ROOT)


def test_extract_uses_output_formats_from_config():
    with _tmp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config_path = tmp_path / "taxonomy.config.yaml"
        config_path.write_text("output:\n  formats: [json]\n", encoding="utf-8")

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "extract",
                "--fixture",
                str(FIXTURES_DIR / "banking_app.json"),
                "--config",
                str(config_path),
                "--output",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        assert (output_dir / "taxonomy.json").exists()
        assert not (output_dir / "taxonomy.csv").exists()
        assert not (output_dir / "taxonomy.md").exists()
        assert not (output_dir / "taxonomy.xlsx").exists()


def test_extract_cli_format_overrides_config():
    with _tmp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config_path = tmp_path / "taxonomy.config.yaml"
        config_path.write_text("output:\n  formats: [json]\n", encoding="utf-8")

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "extract",
                "--fixture",
                str(FIXTURES_DIR / "banking_app.json"),
                "--config",
                str(config_path),
                "--output",
                str(output_dir),
                "--format",
                "csv",
            ],
        )

        assert result.exit_code == 0, result.output
        assert (output_dir / "taxonomy.csv").exists()
        assert not (output_dir / "taxonomy.json").exists()
        assert not (output_dir / "taxonomy.md").exists()
        assert not (output_dir / "taxonomy.xlsx").exists()


def test_extract_rejects_unknown_output_formats():
    with _tmp_dir() as tmp_dir:
        output_dir = Path(tmp_dir) / "output"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "extract",
                "--fixture",
                str(FIXTURES_DIR / "banking_app.json"),
                "--output",
                str(output_dir),
                "--format",
                "json,pdf",
            ],
        )

        assert result.exit_code != 0
        assert "Unknown output format(s): pdf." in result.output
