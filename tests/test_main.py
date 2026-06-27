from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.main import main, parse_args


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.config == "config/config.yaml"
    assert args.verbose is False


def test_parse_args_custom_config_and_verbose() -> None:
    args = parse_args(["--config", "config/test.yaml", "--verbose"])
    assert args.config == "config/test.yaml"
    assert args.verbose is True


def test_main_returns_error_when_config_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    assert main(["--config", str(missing)]) == 1


@patch("src.main.ScraperOrchestrator")
@patch("src.main.create_storage")
def test_main_runs_orchestrator(
    mock_create_storage,
    mock_orchestrator,
    sample_config_yaml: Path,
    tmp_storage_paths,
) -> None:
    s3_path, rds_path = tmp_storage_paths
    import yaml

    raw = yaml.safe_load(sample_config_yaml.read_text(encoding="utf-8"))
    raw["settings"]["storage"]["local_s3_path"] = str(s3_path)
    raw["settings"]["storage"]["local_rds_path"] = str(rds_path)
    sample_config_yaml.write_text(yaml.dump(raw), encoding="utf-8")

    mock_create_storage.return_value = __import__(
        "src.storage.local", fromlist=["LocalStorageBackend"]
    ).LocalStorageBackend(s3_path, rds_path)

    result = main(["--config", str(sample_config_yaml)])
    assert result == 0
    mock_orchestrator.return_value.run.assert_called_once()
