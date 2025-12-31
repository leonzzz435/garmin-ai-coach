import importlib
import json
from unittest.mock import AsyncMock, patch

import pytest

from cli.garmin_ai_coach_cli import cache_only_from_config, run_analysis_from_config
from services.garmin.models import GarminData


@patch("cli.garmin_ai_coach_cli.run_complete_analysis_and_planning", new_callable=AsyncMock)
@patch("services.garmin.TriathlonCoachDataExtractor")
@patch("services.outside.client.OutsideApiGraphQlClient")
@pytest.mark.asyncio
async def test_cli_e2e_smoke_with_mocks(
    mock_outside_client,
    mock_extractor_class,
    mock_run_complete,
    tmp_path,
):
    """Run CLI end-to-end with HITL disabled using mocked dependencies."""

    mock_run_complete.return_value = {
        "analysis_html": "<html><body>Analysis OK</body></html>",
        "planning_html": "<html><body>Plan OK</body></html>",
        "metrics_outputs": None,
        "activity_outputs": None,
        "physiology_outputs": None,
        "season_plan": {"output": "Season OK"},
        "weekly_plan": {"output": "Weekly OK"},
        "cost_summary": {"total_cost_usd": 0.0, "total_tokens": 0},
        "execution_id": "test-exec",
        "execution_metadata": {"trace_id": "trace-1", "root_run_id": "root-1"},
    }

    mock_extractor = mock_extractor_class.return_value
    mock_extractor.extract_data.return_value = GarminData()

    mock_outside_instance = mock_outside_client.return_value
    mock_outside_instance.get_competitions.return_value = []

    output_directory = tmp_path / "out"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
athlete:
  name: "Test A"
  email: "user@example.com"

context:
  analysis: "Analysis context"
  planning: "Planning context"

extraction:
  activities_days: 7
  metrics_days: 14
  ai_mode: "development"
  hitl_enabled: false
  skip_synthesis: false

output:
  directory: "{output_directory.as_posix()}"

credentials:
  password: "dummy"
""",
        encoding="utf-8",
    )

    await run_analysis_from_config(config_path)

    analysis_path = output_directory / "analysis.html"
    planning_path = output_directory / "planning.html"
    summary_path = output_directory / "summary.json"

    assert analysis_path.exists()
    assert planning_path.exists()
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["athlete"] == "Test A"
    assert summary["total_cost_usd"] == 0.0
    assert {"analysis.html", "planning.html"}.issubset(set(summary["files_generated"]))

    kwargs = mock_run_complete.await_args.kwargs
    assert kwargs["hitl_enabled"] is False


@patch("cli.garmin_ai_coach_cli.run_complete_analysis_and_planning", new_callable=AsyncMock)
@patch("services.garmin.TriathlonCoachDataExtractor")
@patch("services.outside.client.OutsideApiGraphQlClient")
@patch("getpass.getpass", return_value="dummy")
@patch("builtins.input", side_effect=["My goal is to complete a marathon"])
@pytest.mark.asyncio
async def test_cli_e2e_with_hitl_enabled(
    mock_input,
    mock_getpass,
    mock_outside_client,
    mock_extractor_class,
    mock_run_complete,
    tmp_path,
):
    """Ensure HITL-enabled configs still run end-to-end via the streamlined workflow."""

    mock_run_complete.return_value = {
        "analysis_html": "<html><body>Analysis with HITL</body></html>",
        "planning_html": "<html><body>Plan with HITL</body></html>",
        "metrics_outputs": None,
        "activity_outputs": None,
        "physiology_outputs": None,
        "season_plan": {"output": "Season OK"},
        "weekly_plan": {"output": "Weekly OK"},
        "cost_summary": {"total_cost_usd": 0.05, "total_tokens": 1000},
        "execution_id": "test-exec-hitl",
        "execution_metadata": {"trace_id": "trace-hitl", "root_run_id": "root-hitl"},
    }

    mock_extractor = mock_extractor_class.return_value
    mock_extractor.extract_data.return_value = GarminData()

    mock_outside_instance = mock_outside_client.return_value
    mock_outside_instance.get_competitions.return_value = []

    output_directory = tmp_path / "out_hitl"
    config_path = tmp_path / "config_hitl.yaml"
    config_path.write_text(
        f"""
athlete:
  name: "Test Athlete HITL"
  email: "user@example.com"

context:
  analysis: "HITL Analysis context"
  planning: "HITL Planning context"

extraction:
  activities_days: 7
  metrics_days: 14
  ai_mode: "development"
  hitl_enabled: true

output:
  directory: "{output_directory.as_posix()}"

credentials:
  password: "dummy"
""",
        encoding="utf-8",
    )

    await run_analysis_from_config(config_path)

    analysis_path = output_directory / "analysis.html"
    planning_path = output_directory / "planning.html"
    summary_path = output_directory / "summary.json"

    assert analysis_path.exists()
    assert planning_path.exists()
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["athlete"] == "Test Athlete HITL"
    assert summary["total_cost_usd"] == 0.05
    assert summary["total_tokens"] == 1000
    assert {"analysis.html", "planning.html"}.issubset(set(summary["files_generated"]))

    kwargs = mock_run_complete.await_args.kwargs
    assert kwargs["hitl_enabled"] is True


@pytest.mark.asyncio
async def test_cli_cache_only_extraction_only(tmp_path, monkeypatch):
    class FakeAPI:
        def get_user_profile(self):
            return {"ok": True}

        def get_stats(self, day):
            return {"s": day}

        def get_sleep_data(self, day):
            return {"sl": day}

        def get_stress_data(self, day):
            return {"st": day}

        def get_hrv_data(self, day):
            return {"hrv": day}

        def get_hydration_data(self, day):
            return {"hy": day}

        def get_training_status(self, day):
            return {"ts": day}

        def get_rhr_day(self, day):
            return {"rhr": day}

        def get_user_summary(self, day):
            return {"us": day}

        def get_activities_by_date(self, start, end):
            return []

        def get_body_composition(self, start, end):
            return {"bc": [start, end]}

    class FakeGarminConnectClient:
        def __init__(self):
            self._client = FakeAPI()

        def connect(self, email, password, mfa_callback=None):
            return None

        @property
        def client(self):
            return self._client

    monkeypatch.setattr(
        importlib.import_module("services.garmin.client"),
        "GarminConnectClient",
        FakeGarminConnectClient,
        raising=True,
    )

    cache_dir = tmp_path / "cache_dir"
    monkeypatch.setenv("GARMIN_CACHE_DIR", cache_dir.as_posix())

    output_directory = tmp_path / "out_cache"
    config_path = tmp_path / "config_cache.yaml"
    config_path.write_text(
        f"""
athlete:
  name: "Cache Only A"
  email: "user@example.com"

context:
  analysis: "n/a"
  planning: "n/a"

extraction:
  activities_days: 3
  metrics_days: 7
  ai_mode: "development"
  hitl_enabled: false

output:
  directory: "{output_directory.as_posix()}"

credentials:
  password: "dummy"
""",
        encoding="utf-8",
    )

    await cache_only_from_config(config_path)

    assert not (output_directory / "analysis.html").exists()
    assert not (output_directory / "planning.html").exists()

    summary_path = output_directory / "cache_summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["athlete"] == "Cache Only A"
    assert summary["activities_days"] == 3
    assert summary["metrics_days"] == 7
    assert "cache_dir" in summary
