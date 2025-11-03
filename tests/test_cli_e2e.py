import importlib
import json
import os
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from cli.garmin_ai_coach_cli import (
    cache_only_from_config,  # noqa: F401
    run_analysis_from_config,
)


@pytest.mark.asyncio
async def test_cli_e2e_smoke_with_mocks(tmp_path, monkeypatch):

    async def fake_run_complete_analysis_and_planning(
        user_id: str,
        athlete_name: str,
        garmin_data: dict,
        analysis_context: str,
        planning_context: str,
        competitions: list,
        current_date: dict,
        week_dates: list,
        plotting_enabled: bool = False,
        hitl_enabled: bool = True,
    ) -> dict:
        return {
            "analysis_html": "<html><body>Analysis OK</body></html>",
            "planning_html": "<html><body>Plan OK</body></html>",
            "metrics_result": "Metrics OK",
            "activity_result": "Activity OK",
            "physiology_result": "Physio OK",
            "season_plan": "Season OK",
            "cost_summary": {"total_cost_usd": 0.0, "total_tokens": 0},
            "execution_id": "test-exec",
            "execution_metadata": {"trace_id": "trace-1", "root_run_id": "root-1"},
        }

    monkeypatch.setattr(
        importlib.import_module("services.ai.langgraph.workflows.planning_workflow"),
        "run_complete_analysis_and_planning",
        fake_run_complete_analysis_and_planning,
        raising=True,
    )

    @dataclass
    class DummyData:
        pass

    class FakeExtractor:
        def __init__(self, email: str, password: str):
            self.email = email
            self.password = password

        def extract_data(self, extraction_config):
            return DummyData()

    monkeypatch.setattr(
        importlib.import_module("services.garmin"),
        "TriathlonCoachDataExtractor",
        FakeExtractor,
        raising=True,
    )

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

    assert "Analysis OK" in analysis_path.read_text(encoding="utf-8")
    assert "Plan OK" in planning_path.read_text(encoding="utf-8")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary.get("athlete") == "Test A"
    assert summary.get("total_cost_usd") == 0.0
    assert summary.get("total_tokens") == 0
    assert "analysis.html" in set(summary.get("files_generated", []))
    assert "planning.html" in set(summary.get("files_generated", []))

    assert os.environ.get("AI_MODE") == "development"


@pytest.mark.asyncio
async def test_cli_e2e_with_hitl_enabled(tmp_path, monkeypatch):

    async def fake_run_workflow_with_hitl(
        workflow_app,
        initial_state: dict,
        config: dict,
        prompt_callback,
        progress_callback=None,
    ) -> dict:
        question = "What is your primary training goal?"
        response = prompt_callback(question)

        assert response is not None

        return {
            "analysis_html": "<html><body>Analysis with HITL</body></html>",
            "planning_html": "<html><body>Plan with HITL</body></html>",
            "metrics_result": "Metrics OK",
            "activity_result": "Activity OK",
            "physiology_result": "Physio OK",
            "season_plan": "Season OK",
            "cost_summary": {"total_cost_usd": 0.05, "total_tokens": 1000},
            "execution_id": "test-exec-hitl",
            "execution_metadata": {"trace_id": "trace-hitl", "root_run_id": "root-hitl"},
        }

    monkeypatch.setattr(
        importlib.import_module("services.ai.langgraph.workflows.interactive_runner"),
        "run_workflow_with_hitl",
        fake_run_workflow_with_hitl,
        raising=True,
    )

    mock_workflow = AsyncMock()
    monkeypatch.setattr(
        importlib.import_module("services.ai.langgraph.workflows.planning_workflow"),
        "create_integrated_analysis_and_planning_workflow",
        lambda: mock_workflow,
        raising=True,
    )

    @dataclass
    class DummyData:
        pass

    class FakeExtractor:
        def __init__(self, email: str, password: str):
            self.email = email
            self.password = password

        def extract_data(self, extraction_config):
            return DummyData()

    monkeypatch.setattr(
        importlib.import_module("services.garmin"),
        "TriathlonCoachDataExtractor",
        FakeExtractor,
        raising=True,
    )

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

    monkeypatch.setattr("getpass.getpass", lambda prompt: "dummy")

    # Mock input() to prevent stdin interaction during testing
    user_responses = ["My goal is to complete a marathon"]
    response_index = [0]

    def mock_input(prompt):
        if response_index[0] < len(user_responses):
            response = user_responses[response_index[0]]
            response_index[0] += 1
            return response
        return "default response"

    monkeypatch.setattr("builtins.input", mock_input)

    await run_analysis_from_config(config_path)

    analysis_path = output_directory / "analysis.html"
    planning_path = output_directory / "planning.html"
    summary_path = output_directory / "summary.json"

    assert analysis_path.exists()
    assert planning_path.exists()
    assert summary_path.exists()

    assert "Analysis with HITL" in analysis_path.read_text(encoding="utf-8")
    assert "Plan with HITL" in planning_path.read_text(encoding="utf-8")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary.get("athlete") == "Test Athlete HITL"
    assert summary.get("total_cost_usd") == 0.05
    assert summary.get("total_tokens") == 1000
    assert "analysis.html" in set(summary.get("files_generated", []))
    assert "planning.html" in set(summary.get("files_generated", []))


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

    # Patch GarminConnectClient used by CLI
    monkeypatch.setattr(
        importlib.import_module("services.garmin.client"),
        "GarminConnectClient",
        FakeGarminConnectClient,
        raising=True,
    )

    # Use tmp cache dir
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

    # Should not create analysis/planning artifacts
    assert not (output_directory / "analysis.html").exists()
    assert not (output_directory / "planning.html").exists()

    # Should create cache summary
    summary_path = output_directory / "cache_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["athlete"] == "Cache Only A"
    assert summary["activities_days"] == 3
    assert summary["metrics_days"] == 7
    assert "cache_dir" in summary
