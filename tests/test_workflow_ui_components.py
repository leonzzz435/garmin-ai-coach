import logging
from pathlib import Path

import pytest
from rich.console import Console, Group
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

wf = pytest.importorskip("cli.workflow_ui", reason="cli.workflow_ui module not available")


class _FakeLive:
    def __init__(self):
        self.updated = 0
        self.started = 0
        self.stopped = 0
        self.last = None

    def update(self, group):
        assert isinstance(group, Group)
        self.updated += 1
        self.last = group

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


def _mk_progress(console: Console) -> Progress:
    p = Progress(
        TextColumn("[bold blue]Workflow[/bold blue]"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )
    p.start()
    return p


@pytest.fixture
def console():
    return Console(record=True)


@pytest.fixture
def progress(console):
    p = _mk_progress(console)
    yield p
    p.stop()


def test_aggregator_parse_and_note_patterns(console):
    agg = wf.RichWorkflowAggregator(console, enable_general_logging=True)

    assert agg.parse_and_note(
        "services.ai.langgraph.config.langsmith_config",
        "LangSmith observability enabled for project: demo_project",
    )
    assert agg.observability_project == "demo_project"

    assert agg.parse_and_note(
        "services.ai.langgraph.workflows.planning_workflow",
        "Created integrated analysis + planning workflow v1",
    )
    assert agg.workflow_ready is True

    assert agg.parse_and_note(
        "services.ai.langgraph.nodes.metrics_expert_node",
        "Starting Metrics Expert analysis node",
    )
    assert agg.nodes_started.get("metrics expert", 0) == 1

    assert agg.parse_and_note(
        "services.ai.langgraph.nodes.activity_summarizer_node",
        "Starting activity summarizer node",
    )
    assert agg.nodes_started.get("activity summarizer", 0) == 1

    assert agg.parse_and_note(
        "services.ai.model_config",
        "Configuring LLM for role metrics_expert with model gpt-5",
    )
    assert agg.roles_model.get("metrics_expert") == "gpt-5"

    assert agg.parse_and_note(
        "services.ai.model_config",
        "Using gpt-5 for metrics_expert (responses api)",
    )
    assert agg.roles_model.get("metrics_expert") == "gpt-5"

    agg.note_general("foo.bar", "hello world")
    assert agg.general_logs and agg.general_logs[-1].endswith("hello world")

    rendered = agg.render()
    assert isinstance(rendered, Group)


def test_unified_handler_advances_progress_and_logs_general(console, progress):
    task_id = progress.add_task("analysis", total=10)
    fake_live = _FakeLive()
    agg = wf.RichWorkflowAggregator(console, enable_general_logging=True)
    handler = wf.UnifiedHandler(fake_live, progress, task_id, agg)

    lg_obs = logging.getLogger("services.ai.langgraph.config.langsmith_config")
    lg_obs.setLevel(logging.INFO)
    lg_obs.propagate = False
    lg_obs.addHandler(handler)

    lg_wf = logging.getLogger("services.ai.langgraph.workflows.planning_workflow")
    lg_wf.setLevel(logging.INFO)
    lg_wf.propagate = False
    lg_wf.addHandler(handler)

    lg_node = logging.getLogger("services.ai.langgraph.nodes.metrics_expert_node")
    lg_node.setLevel(logging.INFO)
    lg_node.propagate = False
    lg_node.addHandler(handler)

    lg_other = logging.getLogger("random.logger")
    lg_other.setLevel(logging.INFO)
    lg_other.propagate = False
    lg_other.addHandler(handler)

    before = progress.tasks[task_id].completed

    lg_obs.info("LangSmith observability enabled for project: projX")
    obs_after = progress.tasks[task_id].completed
    assert obs_after == before + 1

    lg_wf.info("Created integrated analysis + planning workflow OK")
    wf_after = progress.tasks[task_id].completed
    assert wf_after == obs_after + 1

    lg_node.info("Starting Metrics Expert analysis node")
    node_after_1 = progress.tasks[task_id].completed
    lg_node.info("Starting Metrics Expert analysis node")
    node_after_2 = progress.tasks[task_id].completed
    assert node_after_1 == wf_after + 1
    assert node_after_2 == node_after_1

    lg_other.info("misc info")
    assert agg.general_logs and any("misc info" in ln for ln in agg.general_logs)

    assert fake_live.updated > 0


def test_dashboard_session_attach_prompt_detach(console, progress, monkeypatch):
    task_id = progress.add_task("analysis", total=5)
    agg = wf.RichWorkflowAggregator(console, enable_general_logging=True)
    fake_live = _FakeLive()
    session = wf.DashboardSession(
        live=fake_live,
        progress=progress,
        task_id=task_id,
        aggregator=agg,
        console=console,
        handlers=[],
        loggers=[],
    )

    names = ["x.y", "a.b"]
    session.attach_loggers(names)

    for nm in names:
        lg = logging.getLogger(nm)
        assert any(isinstance(h, wf.UnifiedHandler) for h in lg.handlers)

    monkeypatch.setattr("builtins.input", lambda _: "My answer")
    out = session.prompt("Question?")
    assert out == "My answer"
    assert fake_live.stopped == 1 and fake_live.started == 1

    session.detach()
    assert session.handlers == [] and session.loggers == []
    for nm in names:
        lg = logging.getLogger(nm)
        assert not any(isinstance(h, wf.UnifiedHandler) for h in lg.handlers)


def test_general_log_capture_and_prelog_detach(console):
    ui = wf.WorkflowUI(console_=console)
    sess = ui.start_general_log_capture(["alpha.beta", "gamma"])

    lg1 = logging.getLogger("alpha.beta")
    lg2 = logging.getLogger("gamma")
    lg1.info("first")
    lg2.info("second")

    assert any(line.startswith("[beta] first") for line in sess.buffer)
    assert any(line.startswith("[gamma] second") for line in sess.buffer)

    sess.detach()
    for lg in sess.loggers:
        assert not any(h is sess.handler for h in lg.handlers)


def test_workflow_ui_dashboard_seeds_prelogs(console):
    ui = wf.WorkflowUI(console_=console, prelog_loggers=["prelog.test"])
    logging.getLogger("prelog.test").info("pre-seed line")

    with ui.workflow_dashboard(total_steps_estimate=2) as session:
        assert session.aggregator.enable_general_logging is True
        assert session.aggregator.general_logs
        assert ui._prelog_session is None

        session.attach_loggers(["services.ai.langgraph.config.langsmith_config"])
        logging.getLogger("services.ai.langgraph.config.langsmith_config").info(
            "LangSmith observability enabled for project: dash_proj"
        )
        assert session.aggregator.observability_project == "dash_proj"


def test_workflow_ui_headers_panels_progress_and_tables(console, tmp_path: Path):
    ui = wf.WorkflowUI(console_=console)

    ui.show_header("Athlete A", tmp_path, "standard", plotting=True, hitl=False)
    txt = console.export_text()
    assert "Athlete A" in txt and "standard" in txt

    console.clear()
    ui.show_outside_competitions(
        [
            {"source": "BIKEREG", "items": [{"date": "2026-01-01", "name": "Event1"}]},
            {"source": "RUNREG", "items": [{"date": "2026-02-02", "name": "Event2"}]},
        ]
    )
    assert "Outside Competitions" in console.export_text()

    console.clear()
    ui.banner("Hello")
    ui.error_panel("Oops")
    out = console.export_text()
    assert "Hello" in out and "Error" in out

    with ui.status("Extracting..."):
        pass

    with ui.extraction_progress(total_days=3) as advance:
        for _ in range(3):
            advance()

    console.clear()
    ui.show_extraction_summary(
        {
            "recent_activities": [1, 2],
            "recovery_indicators": [{"d": 1}],
            "training_load_history": [1, 2, 3],
            "vo2_max_history": {"running": [1], "cycling": [1, 2]},
        }
    )
    assert "Extraction Summary" in console.export_text()

    file1 = tmp_path / "a.txt"
    file1.write_text("x" * 2048, encoding="utf-8")
    console.clear()
    ui.print_files_table([file1])
    assert "a.txt" in console.export_text()

    console.clear()
    ui.print_cost_panel(1.23, 4567, {"trace_id": "t1", "root_run_id": "r1"})
    ui.print_results_saved(tmp_path)
    out = console.export_text()
    assert "Total cost" in out and "Results saved" in out
