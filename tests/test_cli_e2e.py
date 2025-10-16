import importlib
import json
import os
from dataclasses import dataclass

import pytest

from cli.garmin_ai_coach_cli import run_analysis_from_config


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
    ):
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

    planning_mod = importlib.import_module(
        "services.ai.langgraph.workflows.planning_workflow"
    )
    monkeypatch.setattr(
        planning_mod,
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

    garmin_pkg = importlib.import_module("services.garmin")
    monkeypatch.setattr(
        garmin_pkg, "TriathlonCoachDataExtractor", FakeExtractor, raising=True
    )

    out_dir = tmp_path / "out"
    cfg_path = tmp_path / "config.yaml"
    cfg_text = f"""
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

output:
  directory: "{out_dir.as_posix()}"

credentials:
  password: "dummy"
"""
    cfg_path.write_text(cfg_text, encoding="utf-8")

    await run_analysis_from_config(cfg_path)

    analysis_path = out_dir / "analysis.html"
    planning_path = out_dir / "planning.html"
    summary_path = out_dir / "summary.json"
    assert analysis_path.exists()
    assert planning_path.exists()
    assert summary_path.exists()

    assert "Analysis OK" in analysis_path.read_text(encoding="utf-8")
    assert "Plan OK" in planning_path.read_text(encoding="utf-8")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary.get("athlete") == "Test A"
    assert summary.get("total_cost_usd") == 0.0
    assert summary.get("total_tokens") == 0
    files = set(summary.get("files_generated", []))
    assert "analysis.html" in files
    assert "planning.html" in files

    assert os.environ.get("AI_MODE") == "development"