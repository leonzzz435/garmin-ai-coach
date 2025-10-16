import logging
from datetime import datetime

from services.ai.tools.plotting.plot_storage import PlotMetadata, PlotStorage
from services.ai.tools.plotting.reference_resolver import PlotReferenceResolver

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


async def plot_resolution_node(state: TrainingAnalysisState) -> dict[str, str | dict | list]:
    logger.info("Starting plot resolution node")

    if not state.get("plotting_enabled", False):
        logger.info("Plotting disabled - skipping plot resolution")
        return {
            "analysis_html": state.get("analysis_html", ""),
            "plot_resolution_stats": {
                "total_references": 0,
                "resolved_count": 0,
                "missing_plots": [],
                "skipped": True,
                "reason": "plotting_disabled",
            },
        }

    try:
        analysis_html = state.get("analysis_html", "")

        if not analysis_html:
            logger.warning("No HTML content to resolve plots in")
            return {"errors": ["No HTML content available for plot resolution"]}

        plot_storage = PlotStorage(state["execution_id"])

        logger.info(
            f"Found {len(state.get('plots', []))} plot entries and "
            f"{len(state.get('plot_storage_data', {}))} plot storage entries"
        )

        for plot_id, plot_data in state.get("plot_storage_data", {}).items():
            plot_storage.plots[plot_id] = PlotMetadata(
                plot_id=plot_data["plot_id"],
                description=plot_data["description"],
                agent_name=plot_data["agent_name"],
                created_at=datetime.fromisoformat(plot_data["created_at"]),
                html_content=plot_data["html_content"],
                data_summary=plot_data["data_summary"],
            )

        resolver = PlotReferenceResolver(plot_storage)
        validation_result = resolver.validate_plot_references(analysis_html)
        logger.info(f"Plot validation result: {validation_result}")

        if validation_result["total_references"] == 0:
            logger.info("No plot references found in HTML content")
            return {
                "analysis_html": analysis_html,
                "plot_resolution_stats": {
                    "total_references": 0,
                    "resolved_count": 0,
                    "missing_plots": [],
                },
            }

        logger.info(
            f"About to resolve {validation_result['total_references']} plot references"
        )
        logger.info(f"Available plots in storage: {list(plot_storage.plots.keys())}")

        for plot_id in validation_result["found_plots"]:
            plot_html = plot_storage.get_plot_html(plot_id)
            if plot_html:
                logger.info(f"Plot {plot_id} has HTML content: {len(plot_html)} characters")
            else:
                logger.warning(f"Plot {plot_id} has no HTML content!")

        resolved_html = resolver.resolve_plot_references(analysis_html)
        logger.info(f"Resolution result: {len(resolved_html)} characters")

        resolved_count = (
            validation_result["total_references"]
            - resolver.validate_plot_references(resolved_html)["total_references"]
        )

        logger.info(
            f"Plot resolution completed: "
            f"{resolved_count}/{validation_result['total_references']} plots resolved"
        )

        return {
            "analysis_html": resolved_html,
            "plot_resolution_stats": {
                "total_references": validation_result["total_references"],
                "resolved_count": resolved_count,
                "missing_plots": validation_result["missing_plots"],
                "available_plots_summary": resolver.get_plot_summary(),
            },
            "costs": [{
                "agent": "plot_resolution",
                "execution_time": 0.1,
                "timestamp": datetime.now().isoformat(),
            }],
        }

    except Exception as e:
        logger.error(f"Plot resolution node failed: {e}")
        return {
            "errors": [f"Plot resolution failed: {str(e)}"],
            "analysis_html": state.get("analysis_html", ""),
        }
