from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table


class RichWorkflowAggregator:
    RE_OBSERVABILITY = "LangSmith observability enabled for project:"
    RE_WORKFLOW_CREATED = "Created integrated analysis + planning workflow"
    RE_NODE_START = "Starting "
    RE_LLM_CFG = "Configuring LLM for role "
    RE_LLM_USE = "Using "

    def __init__(
        self,
        console: Console,
        enable_general_logging: bool = False,
        general_log_capacity: int = 200,
    ):
        self.console = console
        self.enable_general_logging = enable_general_logging
        self.general_logs: deque[str] = deque(maxlen=general_log_capacity)

        self.observability_project: str | None = None
        self.workflow_ready: bool = False
        self.nodes_started: dict[str, int] = {}
        self.roles_model: dict[str, str] = {}

        self._seen_nodes: set[str] = set()

    def note_observability(self, project: str) -> None:
        self.observability_project = project.strip()

    def note_workflow_ready(self) -> None:
        self.workflow_ready = True

    def note_node_start(self, node: str) -> None:
        norm = node.strip().lower().replace(" analysis node", "").replace(" analysis", "")
        self.nodes_started[norm] = self.nodes_started.get(norm, 0) + 1

    def note_llm_config(self, role: str, model: str) -> None:
        self.roles_model[role] = model

    def note_general(self, producer: str, message: str) -> None:
        if not self.enable_general_logging:
            return
        short = (producer or "").split(".")[-1]
        self.general_logs.append(f"[{short}] {message}")

    def parse_and_note(self, logger_name: str, msg: str) -> bool:
        matched = False
        text = msg or ""

        if self.RE_OBSERVABILITY in text:
            try:
                project = text.split(self.RE_OBSERVABILITY, 1)[1].strip()
            except Exception:
                project = ""
            self.note_observability(project)
            matched = True

        if self.RE_WORKFLOW_CREATED in text:
            self.note_workflow_ready()
            matched = True

        if text.startswith(self.RE_NODE_START) and "node" in text.lower():
            try:
                after = text[len(self.RE_NODE_START) :].strip()
                node_name = after.replace("node", "").strip()
                self.note_node_start(node_name)
                matched = True
            except Exception:
                pass

        if self.RE_LLM_CFG in text:
            try:
                part = text.split(self.RE_LLM_CFG, 1)[1]
                role_part, model_part = part.split("with model", 1)
                role = role_part.strip()
                model = model_part.strip()
                self.note_llm_config(role, model)
                matched = True
            except Exception:
                pass

        if self.RE_LLM_USE in text and " for " in text:
            try:
                after = text.split(self.RE_LLM_USE, 1)[1]
                model, rest = after.split(" for ", 1)
                role = rest.split(" ", 1)[0].strip()
                self.note_llm_config(role, model.strip())
                matched = True
            except Exception:
                pass

        if not matched:
            self.note_general(logger_name or "logger", text)

        return matched

    def _render_summary(self) -> Panel:
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(style="bold")
        tbl.add_column()
        obs = (
            f"[green]enabled[/green] • project: [cyan]{self.observability_project}[/cyan]"
            if self.observability_project
            else "[yellow]pending[/yellow]"
        )
        tbl.add_row("Observability", obs)
        tbl.add_row(
            "Workflow",
            "[magenta]ready[/magenta]" if self.workflow_ready else "[yellow]initializing[/yellow]",
        )
        return Panel(tbl, title="Workflow Status", border_style="blue", box=box.SQUARE)

    def _render_nodes(self) -> Panel:
        tbl = Table(show_header=True, header_style="bold", box=box.SIMPLE_HEAVY)
        tbl.add_column("Node")
        tbl.add_column("Count", justify="right")
        if self.nodes_started:
            for node, cnt in sorted(self.nodes_started.items()):
                tbl.add_row(node.replace("_", " ").title(), str(cnt))
        else:
            tbl.add_row("[dim]—[/dim]", "[dim]0[/dim]")
        return Panel(tbl, title="Nodes Started", border_style="blue", box=box.SQUARE)

    def _render_llms(self) -> Panel:
        tbl = Table(show_header=True, header_style="bold", box=box.SIMPLE_HEAVY)
        tbl.add_column("Role")
        tbl.add_column("Model", style="cyan")
        if self.roles_model:
            for role, model in sorted(self.roles_model.items()):
                tbl.add_row(role, model)
        else:
            tbl.add_row("[dim]—[/dim]", "[dim]—[/dim]")
        return Panel(tbl, title="LLM Configuration", border_style="blue", box=box.SQUARE)

    def _render_general(self) -> Panel | None:
        if not self.enable_general_logging or not self.general_logs:
            return None
        txt = "\n".join(list(self.general_logs)[-8:])
        return Panel(txt, title="Recent Logs", border_style="blue", box=box.SQUARE)

    def render(self) -> Group:
        parts = [self._render_summary(), self._render_nodes(), self._render_llms()]
        gl = self._render_general()
        if gl:
            parts.append(gl)
        return Group(*parts)


class UnifiedHandler(logging.Handler):
    def __init__(
        self, live: Live, progress: Progress, task_id: int, aggregator: RichWorkflowAggregator
    ):
        super().__init__(level=logging.INFO)
        self.live = live
        self.progress = progress
        self.task_id = task_id
        self.agg = aggregator
        self._seen_nodes: set[str] = set()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            name = record.name

            self.agg.parse_and_note(name, message)

            if RichWorkflowAggregator.RE_OBSERVABILITY in message:
                self._advance_once()
            elif RichWorkflowAggregator.RE_WORKFLOW_CREATED in message:
                self._advance_once()
            elif message.startswith("Starting ") and "node" in message.lower():
                norm = (
                    message.replace("Starting ", "")
                    .replace(" analysis node", "")
                    .replace(" analysis", "")
                    .replace("node", "")
                    .strip()
                    .lower()
                )
                if norm not in self._seen_nodes:
                    self._seen_nodes.add(norm)
                    self._advance_once()

            self.live.update(Group(self.agg.render(), self.progress))
        except Exception:
            pass

    def _advance_once(self) -> None:
        try:
            self.progress.advance(self.task_id, 1)
        except Exception:
            pass


@dataclass
class DashboardSession:
    live: Live
    progress: Progress
    task_id: int
    aggregator: RichWorkflowAggregator
    console: Console
    handlers: list[logging.Handler]
    loggers: list[logging.Logger]

    def attach_loggers(self, names: Iterable[str]) -> None:
        for nm in names:
            lg = logging.getLogger(nm)
            handler = UnifiedHandler(self.live, self.progress, self.task_id, self.aggregator)
            lg.setLevel(logging.INFO)
            lg.propagate = False
            lg.addHandler(handler)
            self.handlers.append(handler)
            self.loggers.append(lg)

    def prompt(self, question: str) -> str:
        try:
            self.live.stop()
        except Exception:
            pass
        try:
            answer = input(question)
        finally:
            try:
                self.live.start()
            except Exception:
                pass
        return answer

    def detach(self) -> None:
        for lg in self.loggers:
            for h in list(lg.handlers):
                if h in self.handlers:
                    lg.removeHandler(h)
        self.handlers.clear()
        self.loggers.clear()


class WorkflowUI:
    def __init__(
        self,
        console_: Console | None = None,
        prelog_loggers: list[str] | None = None,
        enable_general_logging: bool = True,
    ):
        self.console = console_ or Console()
        self._prelog_session: _PrelogSession | None = None
        if prelog_loggers:
            self._prelog_session = self.start_general_log_capture(prelog_loggers)
        self._enable_general_logging = enable_general_logging

    def start_general_log_capture(self, logger_names: Iterable[str]) -> _PrelogSession:
        sess = _PrelogSession()
        handler = _BufferingHandler(sess.buffer)
        handler.setLevel(logging.INFO)
        sess.handler = handler
        for nm in logger_names:
            lg = logging.getLogger(nm)
            lg.setLevel(logging.INFO)
            lg.propagate = False
            lg.addHandler(handler)
            sess.loggers.append(lg)
        return sess

    def workflow_dashboard(self, total_steps_estimate: int = 10):
        progress = Progress(
            TextColumn("[bold blue]Workflow[/bold blue]"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self.console,
            transient=False,
        )
        task_id = progress.add_task("analysis", total=total_steps_estimate)

        aggregator = RichWorkflowAggregator(self.console, enable_general_logging=True)

        live = Live(
            Group(aggregator.render(), progress),
            console=self.console,
            refresh_per_second=6,
            screen=True,
        )

        class _SessionCtx:
            def __enter__(_self):
                live.start()
                if getattr(self, "_prelog_session", None) and self._prelog_session.buffer:
                    for line in self._prelog_session.buffer:
                        aggregator.note_general("prelog", line)
                    self._prelog_session.detach()
                    self._prelog_session = None
                live.update(Group(aggregator.render(), progress))
                return DashboardSession(
                    live=live,
                    progress=progress,
                    task_id=task_id,
                    aggregator=aggregator,
                    console=self.console,
                    handlers=[],
                    loggers=[],
                )

            def __exit__(_self, exc_type, exc, tb):
                try:
                    progress.stop()
                finally:
                    live.stop()

        return _SessionCtx()

    def show_header(
        self,
        athlete=None,
        output_dir=None,
        ai_mode=None,
        plotting: bool = False,
        hitl: bool = True,
        **_,
    ):
        athlete_name = athlete if athlete is not None else "Athlete"
        header = Table.grid(padding=1)
        header.add_column(justify="left", style="bold")
        header.add_column()
        header.add_row("Athlete", f"[green]{athlete_name}[/green]")
        header.add_row("Output", f"[cyan]{output_dir}[/cyan]")
        header.add_row("AI Mode", f"[magenta]{ai_mode}[/magenta]")
        header.add_row("Plotting", "enabled" if plotting else "disabled")
        header.add_row("HITL", "enabled" if hitl else "disabled")
        self.console.print(
            Panel(header, title="Garmin AI Coach - Analysis", border_style="blue", box=box.ROUNDED)
        )

    def show_outside_competitions(self, summary: list[dict]) -> None:
        counts_tbl = Table.grid()
        counts_tbl.add_column(style="bold")
        counts_tbl.add_column(justify="right")
        for entry in summary or []:
            counts_tbl.add_row(entry.get("source", "UNKNOWN") + ": ", str(len(entry.get("items", []))))
        details_tbl = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
        details_tbl.add_column("Date", style="cyan")
        details_tbl.add_column("Name", style="white")
        details_tbl.add_column("Source", style="magenta")
        for entry in summary or []:
            src = entry.get("source", "UNKNOWN")
            for item in entry.get("items", []):
                details_tbl.add_row(item.get("date", ""), item.get("name", ""), src)
        self.console.print(
            Panel(
                Group(
                    Panel(counts_tbl, title="Counts", border_style="cyan", box=box.SQUARE),
                    details_tbl,
                ),
                title="Outside Competitions",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

    def banner(self, text: str, border_style: str = "green") -> None:
        self.console.print(Panel.fit(text, title="Info", border_style=border_style))

    def error_panel(self, text: str) -> None:
        self.console.print(Panel.fit(text, title="Error", border_style="red"))

    def status(self, text: str):
        return self.console.status(f"[bold]{text}[/bold]")

    def extraction_progress(self, total_days: int):
        progress = Progress(
            TextColumn("[bold blue]Downloading daily metrics[/bold blue]"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self.console,
            transient=False,
        )
        task_id = progress.add_task(f"Caching {total_days} days", total=total_days)

        class _Ctx:
            def __enter__(_self):
                progress.start()

                def advance():
                    progress.advance(task_id, 1)

                return advance

            def __exit__(_self, exc_type, exc, tb):
                progress.stop()

        return _Ctx()

    def show_extraction_summary(self, gd: dict) -> None:
        summary_tbl = Table(title="Extraction Summary", box=box.SIMPLE_HEAVY, show_edge=False)
        summary_tbl.add_column("Dataset", style="bold")
        summary_tbl.add_column("Count", justify="right")
        summary_tbl.add_row(
            "Recent activities", str(len((gd or {}).get("recent_activities", []) or []))
        )
        summary_tbl.add_row(
            "Recovery indicators (days)", str(len((gd or {}).get("recovery_indicators", []) or []))
        )
        summary_tbl.add_row(
            "Training load points", str(len((gd or {}).get("training_load_history", []) or []))
        )
        vm = (gd or {}).get("vo2_max_history", {}) or {}
        summary_tbl.add_row("VO2max (running)", str(len(vm.get("running", []) or [])))
        summary_tbl.add_row("VO2max (cycling)", str(len(vm.get("cycling", []) or [])))
        self.console.print(summary_tbl)

    def print_files_table(self, paths: Iterable) -> None:
        files_table = Table(title="Generated Files", box=box.SIMPLE_HEAVY)
        files_table.add_column("File")
        files_table.add_column("Size (KB)", justify="right")
        files_table.add_column("Status", style="green")
        for p in paths:
            try:
                kb = round((p.stat().st_size if p.exists() else 0) / 1024, 1)
            except Exception:
                kb = 0.0
            files_table.add_row(
                p.name, f"{kb}", "[bold]saved[/bold]" if kb > 0 else "[dim]n/a[/dim]"
            )
        self.console.print(files_table)

    def print_cost_panel(self, total_cost_usd: float, total_tokens: int, meta: dict) -> None:
        panel = Panel.fit(
            f"[bold]Total cost[/bold]: ${float(total_cost_usd):.2f}\n"
            f"[bold]Tokens[/bold]: {int(total_tokens)}\n"
            f"[bold]Trace ID[/bold]: {str((meta or {}).get('trace_id',''))}\n"
            f"[bold]Root Run[/bold]: {str((meta or {}).get('root_run_id',''))}",
            title="Run Summary",
            border_style="green",
        )
        self.console.print(panel)

    def print_results_saved(self, output_dir) -> None:
        self.console.print(
            Panel.fit(f"Results saved to: [cyan]{output_dir}[/cyan]", border_style="blue")
        )


@dataclass
class _PrelogSession:
    buffer: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    handler: logging.Handler | None = None
    loggers: list[logging.Logger] = field(default_factory=list)

    def detach(self) -> None:
        if self.handler:
            for lg in self.loggers:
                try:
                    lg.removeHandler(self.handler)
                except Exception:
                    pass
        self.loggers.clear()
        self.handler = None


class _BufferingHandler(logging.Handler):
    def __init__(self, buffer: deque[str]):
        super().__init__(level=logging.INFO)
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            name = record.name or "log"
            short = name.split(".")[-1]
            self.buffer.append(f"[{short}] {msg}")
        except Exception:
            pass
