import logging
import re
from typing import Any

from .plot_storage import PlotStorage

logger = logging.getLogger(__name__)


class PlotReferenceResolver:

    def __init__(self, plot_storage: PlotStorage):
        self.plot_storage = plot_storage

    def resolve_plot_references(self, text: str) -> str:
        # Pattern to match [PLOT:plot_id] references
        plot_pattern = r'\[PLOT:([^\]]+)\]'

        def replace_plot_reference(match):
            plot_id = match.group(1)
            return self._embed_plot(plot_id)

        # Replace all plot references
        resolved_text = re.sub(plot_pattern, replace_plot_reference, text)

        # Log statistics
        original_refs = len(re.findall(plot_pattern, text))
        remaining_refs = len(re.findall(plot_pattern, resolved_text))
        resolved_count = original_refs - remaining_refs

        logger.info(f"Resolved {resolved_count}/{original_refs} plot references")

        return resolved_text

    def _embed_plot(self, plot_id: str) -> str:
        plot_html = self.plot_storage.get_plot_html(plot_id)

        if plot_html:
            # Wrap plot in responsive container
            return self._wrap_plot_html(plot_id, plot_html)
        else:
            # Fallback for missing plots
            plot_metadata = self.plot_storage.get_plot(plot_id)
            if plot_metadata:
                fallback = f"""
                <div class="plot-fallback" style="padding: 20px; border: 2px dashed #ccc; margin: 10px 0; text-align: center; background-color: #f9f9f9;">
                    <p><strong>Plot Unavailable: {plot_metadata.description}</strong></p>
                    <p><em>Created by {plot_metadata.agent_name}</em></p>
                    <p>Plot ID: {plot_id}</p>
                </div>
                """
            else:
                fallback = f"""
                <div class="plot-error" style="padding: 20px; border: 2px solid #ff6b6b; margin: 10px 0; text-align: center; background-color: #ffe0e0;">
                    <p><strong>Plot Not Found</strong></p>
                    <p>Plot ID: {plot_id}</p>
                </div>
                """

            logger.warning(f"Plot {plot_id} not found, using fallback")
            return fallback

    def _wrap_plot_html(self, plot_id: str, plot_html: str) -> str:
        return f"""
        <div class="plot-container" id="plot-{plot_id}" style="margin: 20px 0; width: 100%; overflow: hidden;">
            <div class="plot-content" style="width: 100%; height: auto;">
                {plot_html}
            </div>
        </div>
        """

    def extract_plot_references(self, text: str) -> list[str]:
        plot_pattern = r'\[PLOT:([^\]]+)\]'
        return re.findall(plot_pattern, text)

    def validate_plot_references(self, text: str) -> dict[str, Any]:
        referenced_plots = self.extract_plot_references(text)
        available_plots = set(self.plot_storage.get_all_plots().keys())

        found_plots = []
        missing_plots = []

        for plot_id in referenced_plots:
            if plot_id in available_plots:
                found_plots.append(plot_id)
            else:
                missing_plots.append(plot_id)

        return {
            'total_references': len(referenced_plots),
            'unique_references': len(set(referenced_plots)),
            'found_plots': found_plots,
            'missing_plots': missing_plots,
            'validation_passed': len(missing_plots) == 0,
        }

    def get_plot_summary(self) -> str:
        plots = self.plot_storage.list_available_plots()

        if not plots:
            return "No plots available"

        summary_lines = [f"Available plots ({len(plots)}):"]
        for plot in plots:
            summary_lines.append(
                f"  - {plot['plot_id']}: {plot['description']} (by {plot['agent_name']})"
            )

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
        
        /* Responsive plot sizing */
        @media (max-width: 768px) {
            .plot-container {
                margin: 15px 0;
            }
        }
        
        /* Ensure Plotly plots are responsive */
        .js-plotly-plot {
            width: 100% !important;
            height: auto !important;
        }
        </style>
        """

    @staticmethod
    def wrap_html_document(content: str) -> str:
        styles = HTMLPlotEmbedder.add_plot_styles()

        return f"""
        <!DOCTYPE html>
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
        </html>
        """
