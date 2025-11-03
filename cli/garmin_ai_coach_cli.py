#!/usr/bin/env python3
import argparse
import asyncio
import getpass
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from cli.rich_workflow import WorkflowUI
from services.outside.client import OutsideApiGraphQlClient

sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ConfigParser:

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        content = self.config_path.read_text(encoding="utf-8")

        if self.config_path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(content)
        elif self.config_path.suffix == ".json":
            return json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {self.config_path.suffix}")

    def get_athlete_info(self) -> tuple[str, str]:
        if not (email := self.config.get("athlete", {}).get("email")):
            raise ValueError("Athlete email is required in config file")

        return self.config.get("athlete", {}).get("name", "Athlete"), email

    def get_contexts(self) -> tuple[str, str]:
        return (
            self.config.get("context", {}).get("analysis", "").strip(),
            self.config.get("context", {}).get("planning", "").strip(),
        )

    def get_extraction_config(self) -> dict[str, Any]:
        return {
            "activities_days": self.config.get("extraction", {}).get("activities_days", 7),
            "metrics_days": self.config.get("extraction", {}).get("metrics_days", 14),
            "ai_mode": self.config.get("extraction", {}).get("ai_mode", "development"),
            "enable_plotting": self.config.get("extraction", {}).get("enable_plotting", False),
            "hitl_enabled": self.config.get("extraction", {}).get("hitl_enabled", True),
        }

    def get_competitions(self) -> list[dict[str, Any]]:
        competitions = self.config.get("competitions", [])
        return [
            {
                "name": comp.get("name", ""),
                "date": comp.get("date", ""),
                "race_type": comp.get("race_type", ""),
                "priority": comp.get("priority", "B"),
                "target_time": comp.get("target_time", ""),
            }
            for comp in competitions
        ]

    def get_output_directory(self) -> Path:
        return Path(self.config.get("output", {}).get("directory", "./data"))

    def get_password(self) -> str:
        return self.config.get("credentials", {}).get("password", "") or getpass.getpass(
            "Enter Garmin Connect password: "
        )


def fetch_outside_competitions_from_config(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_competitions: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    def collect_for(app_type: str, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        client = OutsideApiGraphQlClient(app_type=app_type)
        comps = client.get_competitions(entries)
        all_competitions.extend(comps)
        summary.append(
            {
                "source": app_type,
                "items": [{"name": c.get("name", ""), "date": c.get("date", "")} for c in comps],
            }
        )

    outside_cfg = config.get("outside")
    if isinstance(outside_cfg, dict) and any(
        isinstance(v, list) and v for v in outside_cfg.values()
    ):
        for key, entries in outside_cfg.items():
            if not isinstance(entries, list) or not entries:
                continue
            key_upper = str(key).strip().upper()
            if key_upper in {"BIKEREG", "RUNREG", "TRIREG", "SKIREG"}:
                collect_for(key_upper, entries)

    legacy_sections = {
        "BIKEREG": config.get("bikereg", []),
        "RUNREG": config.get("runreg", []),
        "TRIREG": config.get("trireg", []),
        "SKIREG": config.get("skireg", []),
    }
    for app_type, entries in legacy_sections.items():
        if isinstance(entries, list) and entries:
            collect_for(app_type, entries)

    return all_competitions, summary


async def cache_only_from_config(
    config_path: Path, output_dir_override: Path | None = None
) -> None:
    from services.garmin.cache_client import CachedGarminClient
    from services.garmin.client import GarminConnectClient
    from services.garmin.daily_cache import GarminDailyCache

    ui = WorkflowUI()

    cfg = ConfigParser(config_path)
    athlete_name, email = cfg.get_athlete_info()
    extraction = cfg.get_extraction_config()
    activities_days = int(extraction["activities_days"])
    metrics_days = int(extraction["metrics_days"])
    output_dir = output_dir_override or cfg.get_output_directory()
    output_dir.mkdir(parents=True, exist_ok=True)

    ui.banner(
        f"Cache-only mode for [green]{athlete_name}[/green]\nOutput: [cyan]{output_dir}[/cyan]",
        border_style="blue",
    )

    password = cfg.get_password()

    garmin = GarminConnectClient()
    garmin.connect(email, password)
    cache_root = Path(os.getenv("GARMIN_CACHE_DIR", "data/cache/garmin"))
    cache_root.mkdir(parents=True, exist_ok=True)
    daily_cache = GarminDailyCache(cache_root)
    client = CachedGarminClient(garmin.client, daily_cache)

    end = date.today()
    m_start = end - timedelta(days=metrics_days)
    a_start = end - timedelta(days=activities_days)

    days: list[date] = []
    cur = m_start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)

    endpoints = [
        client.get_stats,
        client.get_sleep_data,
        client.get_stress_data,
        client.get_hrv_data,
        client.get_hydration_data,
        client.get_training_status,
        client.get_rhr_day,
        client.get_user_summary,
    ]

    with ui.extraction_progress(len(days)) as advance:
        for d in days:
            day_iso = d.isoformat()
            for fn in endpoints:
                try:
                    fn(day_iso)
                except Exception as e:
                    logger.debug(
                        "Daily endpoint %s failed for %s: %s",
                        getattr(fn, "__name__", "fn"),
                        day_iso,
                        e,
                    )
            advance()

    try:
        client.get_activities_by_date(a_start.isoformat(), end.isoformat())
    except Exception as e:
        logger.debug("Activities range fetch failed: %s", e)

    try:
        client.get_body_composition(m_start.isoformat(), end.isoformat())
    except Exception as e:
        logger.debug("Body composition range fetch failed: %s", e)

    summary = {
        "athlete": athlete_name,
        "cached_at": datetime.now().isoformat(),
        "activities_days": activities_days,
        "metrics_days": metrics_days,
        "cache_dir": cache_root.as_posix(),
        "stats": {
            "metrics_days_cached": len(days),
            "range_calls": {"activities": True, "body_comp": True},
        },
    }
    (output_dir / "cache_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    ui.banner(
        f":white_check_mark: Cache-only complete. Summary -> [cyan]{(output_dir / 'cache_summary.json')}[/cyan]",
        border_style="green",
    )


async def run_analysis_from_config(
    config_path: Path, output_dir_override: Path | None = None
) -> None:
    noisy_loggers = [
        "services.garmin",
        "garminconnect",
        "garth",
        "urllib3",
        "httpx",
    ]
    for name in noisy_loggers:
        lg = logging.getLogger(name)
        lg.setLevel(logging.WARNING)
        lg.propagate = False
        for h in list(lg.handlers):
            if isinstance(h, logging.StreamHandler):
                lg.removeHandler(h)

    ui = WorkflowUI()

    config_parser = ConfigParser(config_path)
    athlete_name, email = config_parser.get_athlete_info()
    analysis_context, planning_context = config_parser.get_contexts()
    extraction_settings = config_parser.get_extraction_config()

    competitions = config_parser.get_competitions()
    outside_competitions, outside_summary = fetch_outside_competitions_from_config(
        config_parser.config
    )
    if outside_competitions:
        competitions.extend(outside_competitions)

    output_dir = output_dir_override or config_parser.get_output_directory()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["AI_MODE"] = extraction_settings.get("ai_mode", "development")

    ui.show_header(
        athlete=athlete_name,
        output_dir=output_dir,
        ai_mode=os.environ["AI_MODE"],
        plotting=extraction_settings.get("enable_plotting", False),
        hitl=extraction_settings.get("hitl_enabled", True),
    )
    ui.show_outside_competitions(outside_summary)

    password = config_parser.get_password()

    from langsmith.run_helpers import trace

    from services.ai.langgraph.state.training_analysis_state import create_initial_state
    from services.ai.langgraph.workflows.interactive_runner import run_workflow_with_hitl
    from services.ai.langgraph.workflows.planning_workflow import (
        create_integrated_analysis_and_planning_workflow,
        run_complete_analysis_and_planning,
    )
    from services.garmin import ExtractionConfig, TriathlonCoachDataExtractor

    prefetched = False
    try:
        from services.garmin.cache_client import CachedGarminClient
        from services.garmin.client import GarminConnectClient
        from services.garmin.daily_cache import GarminDailyCache

        garmin = GarminConnectClient()
        garmin.connect(email, password)

        cache_root = Path(os.getenv("GARMIN_CACHE_DIR", "data/cache/garmin"))
        cache_root.mkdir(parents=True, exist_ok=True)
        daily_cache = GarminDailyCache(cache_root)
        client = CachedGarminClient(garmin.client, daily_cache)

        metrics_days = int(extraction_settings["metrics_days"])
        end = date.today()
        m_start = end - timedelta(days=metrics_days)

        days: list[date] = []
        cur = m_start
        while cur <= end:
            days.append(cur)
            cur += timedelta(days=1)

        endpoints = [
            client.get_stats,
            client.get_sleep_data,
            client.get_stress_data,
            client.get_hrv_data,
            client.get_hydration_data,
            client.get_training_status,
            client.get_rhr_day,
            client.get_user_summary,
        ]

        with ui.extraction_progress(len(days)) as advance:
            for d in days:
                day_iso = d.isoformat()
                for fn in endpoints:
                    try:
                        fn(day_iso)
                    except Exception:
                        pass
                advance()
            prefetched = True
    except Exception:
        prefetched = False

    try:
        with ui.status("Finalizing from cache…" if prefetched else "Finalizing data extraction…"):
            extractor = TriathlonCoachDataExtractor(email, password)
            extraction_config = ExtractionConfig(
                activities_range=extraction_settings["activities_days"],
                metrics_range=extraction_settings["metrics_days"],
                include_detailed_activities=True,
                include_metrics=True,
            )
            garmin_data = extractor.extract_data(extraction_config)

        try:
            gd = asdict(garmin_data)
        except Exception:
            gd = {}

        ui.show_extraction_summary(gd)

        now = datetime.now()
        plotting_enabled = extraction_settings.get("enable_plotting", False)
        hitl_enabled = extraction_settings.get("hitl_enabled", True)
        current_date = {"date": now.strftime("%Y-%m-%d"), "day_name": now.strftime("%A")}
        week_dates = [
            {
                "date": (now + timedelta(days=offset)).strftime("%Y-%m-%d"),
                "day_name": (now + timedelta(days=offset)).strftime("%A"),
            }
            for offset in range(14)
        ]

        ui.banner("Running AI analysis and planning…", border_style="magenta")

        total_steps_estimate = 14
        target_loggers = [
            "services.ai.langgraph.config.langsmith_config",
            "services.ai.langgraph.workflows.planning_workflow",
            "services.ai.langgraph.nodes.activity_summarizer_node",
            "services.ai.langgraph.nodes.data_summarizer_node",
            "services.ai.langgraph.nodes.metrics_summarizer_node",
            "services.ai.langgraph.nodes.physiology_summarizer_node",
            "services.ai.langgraph.nodes.metrics_expert_node",
            "services.ai.langgraph.nodes.physiology_expert_node",
            "services.ai.langgraph.nodes.activity_expert_node",
            "services.ai.model_config",
        ]

        result: dict[str, Any] = {}
        with ui.workflow_dashboard(total_steps_estimate=total_steps_estimate) as dash:
            dash.attach_loggers(target_loggers)
            if hitl_enabled:

                def prompt_user(question: str) -> str:
                    return dash.prompt(question)

                def show_progress(_: str) -> None:
                    pass

                workflow = create_integrated_analysis_and_planning_workflow()
                execution_id = f"cli_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}_complete"
                config = {"configurable": {"thread_id": execution_id}}

                async with trace(
                    name="Garmin HITL Session",
                    project_name="garmin_ai_coach_analysis",
                    inputs={
                        "thread_id": execution_id,
                        "athlete": athlete_name,
                        "plotting_enabled": plotting_enabled,
                        "hitl_enabled": True,
                    },
                    tags=[f"thread:{execution_id}", "garmin", "hitl", "cli"],
                ) as run:
                    result = await run_workflow_with_hitl(
                        workflow_app=workflow,
                        initial_state=create_initial_state(
                            user_id="cli_user",
                            athlete_name=athlete_name,
                            garmin_data=gd,
                            analysis_context=analysis_context,
                            planning_context=planning_context,
                            competitions=competitions,
                            current_date=current_date,
                            week_dates=week_dates,
                            execution_id=execution_id,
                            plotting_enabled=plotting_enabled,
                            hitl_enabled=True,
                        ),
                        config=config,
                        prompt_callback=prompt_user,
                        progress_callback=show_progress,
                    )
                    run.end(
                        outputs={
                            "status": "completed",
                            "execution_id": execution_id,
                            "cancelled": result.get("cancelled", False),
                        }
                    )
            else:
                result = await run_complete_analysis_and_planning(
                    user_id="cli_user",
                    athlete_name=athlete_name,
                    garmin_data=gd,
                    analysis_context=analysis_context,
                    planning_context=planning_context,
                    competitions=competitions,
                    current_date=current_date,
                    week_dates=week_dates,
                    plotting_enabled=plotting_enabled,
                    hitl_enabled=False,
                )

        files_generated: list[Path] = []
        for filename, key in [
            ("analysis.html", "analysis_html"),
            ("planning.html", "planning_html"),
            ("metrics_result.md", "metrics_result"),
            ("activity_result.md", "activity_result"),
            ("physiology_result.md", "physiology_result"),
            ("season_plan.md", "season_plan"),
        ]:
            if content := result.get(key):
                p = output_dir / filename
                p.write_text(content, encoding="utf-8")
                files_generated.append(p)

        ui.print_files_table(files_generated)

        cost_total = float(
            result.get("cost_summary", {}).get("total_cost_usd", 0.0)
            or result.get("execution_metadata", {}).get("total_cost_usd", 0.0)
            or sum(cost.get("total_cost", 0) for cost in result.get("costs", []))
        )
        total_tokens = int(
            result.get("cost_summary", {}).get("total_tokens", 0)
            or result.get("execution_metadata", {}).get("total_tokens", 0)
        )

        files_generated_names = [p.name for p in files_generated]
        summary_payload = {
            "athlete": athlete_name,
            "analysis_date": datetime.now().isoformat(),
            "competitions": competitions,
            "total_cost_usd": cost_total,
            "total_tokens": total_tokens,
            "execution_id": result.get("execution_id", ""),
            "trace_id": (result.get("execution_metadata", {}) or {}).get("trace_id", ""),
            "root_run_id": (result.get("execution_metadata", {}) or {}).get("root_run_id", ""),
            "files_generated": files_generated_names,
        }
        (output_dir / "summary.json").write_text(
            json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        ui.print_cost_panel(cost_total, total_tokens, result.get("execution_metadata", {}) or {})
        ui.print_results_saved(output_dir)

    except Exception as e:
        ui.error_panel(f"Analysis failed: {e}")
        logger.error(f"Analysis failed: {e}")
        raise


def create_config_template(output_path: Path) -> None:
    template_path = Path(__file__).parent / "coach_config_template.yaml"

    if template_path.exists():
        output_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
        logger.info(f"📄 Config template created: {output_path}")
        logger.info("Edit this file with your settings and run analysis with --config")
    else:
        logger.error("❌ Template file not found")


def main():
    parser = argparse.ArgumentParser(
        description="Garmin AI Coach CLI - AI Triathlon Coach",
        epilog="Example: python garmin_ai_coach_cli.py --config my_config.yaml",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", type=Path, help="Path to configuration file (YAML or JSON)")
    group.add_argument("--init-config", type=Path, help="Create a configuration template file")

    parser.add_argument("--output-dir", type=Path, help="Override output directory from config")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Fetch and cache Garmin data only (no AI analysis or report generation)",
    )

    args = parser.parse_args()

    if args.init_config:
        create_config_template(args.init_config)
        return

    if args.config:
        try:
            if args.cache_only:
                asyncio.run(cache_only_from_config(args.config, args.output_dir))
            else:
                asyncio.run(run_analysis_from_config(args.config, args.output_dir))
        except KeyboardInterrupt:
            print("Operation cancelled by user")
            logger.info("Operation cancelled by user")
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
