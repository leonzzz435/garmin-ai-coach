import logging
import re
from typing import Any

from .plot_storage import PlotStorage

logger = logging.getLogger(__name__)


class PlotReferenceResolver:
    PLOT_PATTERN = r'\[PLOT:([^\]]+)\]'

    def __init__(self, plot_storage: PlotStorage):
        self.plot_storage = plot_storage

    def resolve_plot_references(self, text: str) -> str:
        resolved_plots = set()
        
        def replace_plot_reference(match):
            plot_id = match.group(1)
            if plot_id in resolved_plots:
                logger.warning(f"Removing duplicate reference to plot {plot_id}")
                return ""
            resolved_plots.add(plot_id)
            return self._embed_plot(plot_id)

        resolved_text = re.sub(self.PLOT_PATTERN, replace_plot_reference, text)
        
        original_refs = len(re.findall(self.PLOT_PATTERN, text))
        duplicates_removed = original_refs - len(resolved_plots)
        
        logger.info(
            f"Resolved {len(resolved_plots)}/{original_refs} plot references, "
            f"removed {duplicates_removed} duplicates"
        )
        
        return resolved_text

    def _embed_plot(self, plot_id: str) -> str:
        plot_html = self.plot_storage.get_plot_html(plot_id)
        
        if plot_html:
            return self._wrap_plot_html(plot_id, plot_html)
        
        plot_metadata = self.plot_storage.get_plot(plot_id)
        logger.warning(f"Plot {plot_id} not found, using fallback")
        
        if plot_metadata:
            return f"""
<div class="plot-fallback" style="padding: 20px; border: 2px dashed #ccc; margin: 10px 0; text-align: center; background-color: #f9f9f9;">
    <p><strong>Plot Unavailable: {plot_metadata.description}</strong></p>
    <p><em>Created by {plot_metadata.agent_name}</em></p>
    <p>Plot ID: {plot_id}</p>
</div>"""
        
        return f"""
<div class="plot-error" style="padding: 20px; border: 2px solid #ff6b6b; margin: 10px 0; text-align: center; background-color: #ffe0e0;">
    <p><strong>Plot Not Found</strong></p>
    <p>Plot ID: {plot_id}</p>
</div>"""

    def _wrap_plot_html(self, plot_id: str, plot_html: str) -> str:
        return f"""
<div class="plot-container" id="plot-{plot_id}" style="margin: 20px 0; width: 100%; overflow: hidden;">
    <div class="plot-content" style="width: 100%; height: auto;">
        {plot_html}
    </div>
</div>"""

    def extract_plot_references(self, text: str) -> list[str]:
        return re.findall(self.PLOT_PATTERN, text)

    def validate_plot_references(self, text: str) -> dict[str, Any]:
        referenced_plots = self.extract_plot_references(text)
        available_plots = set(self.plot_storage.get_all_plots().keys())
        
        found_plots = [pid for pid in referenced_plots if pid in available_plots]
        missing_plots = [pid for pid in referenced_plots if pid not in available_plots]
        
        return {
            "total_references": len(referenced_plots),
            "unique_references": len(set(referenced_plots)),
            "found_plots": found_plots,
            "missing_plots": missing_plots,
            "validation_passed": len(missing_plots) == 0,
        }

    def get_plot_summary(self) -> str:
        plots = self.plot_storage.list_available_plots()
        
        if not plots:
            return "No plots available"
        
        summary_lines = [f"Available plots ({len(plots)}):"] + [
            f"  - {plot['plot_id']}: {plot['description']} (by {plot['agent_name']})"
            for plot in plots
        ]
        
        return "\n".join(summary_lines)


class HTMLPlotEmbedder:
    
    @staticmethod
    def add_plot_styles() -> str:
        return """
<style>
.plot-container {
    margin: 20px 0;
    width: 100%;
    overflow: hidden;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.plot-content {
    width: 100%;
    height: auto;
}

.plot-fallback {
    padding: 20px;
    border: 2px dashed #ccc;
    margin: 10px 0;
    text-align: center;
    background-color: #f9f9f9;
    border-radius: 8px;
}

.plot-error {
    padding: 20px;
    border: 2px solid #ff6b6b;
    margin: 10px 0;
    text-align: center;
    background-color: #ffe0e0;
    border-radius: 8px;
    color: #d63031;
}

@media (max-width: 768px) {
    .plot-container {
        margin: 15px 0;
    }
}

.js-plotly-plot {
    width: 100% !important;
    height: auto !important;
}
</style>"""

    @staticmethod
    def wrap_html_document(content: str) -> str:
        styles = HTMLPlotEmbedder.add_plot_styles()
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Training Analysis Report</title>
    {styles}
</head>
<body>
    {content}
</body>
</html>"""
