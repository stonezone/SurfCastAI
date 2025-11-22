"""
Forecast formatter for SurfCastAI.

This module handles formatting of generated forecasts into
various output formats (markdown, HTML, PDF).
"""

import logging
import os
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
from datetime import datetime
import re
from textwrap import dedent

from ..core.config import Config
from .visualization import ForecastVisualizer
from .historical import HistoricalComparator


class ForecastFormatter:
    """
    Formatter for converting forecasts into various output formats.

    Features:
    - Converts raw forecast text to structured formats
    - Supports markdown, HTML, and PDF output
    - Provides customization options for different formats
    - Handles shore-specific and daily forecast variants
    """

    def __init__(self, config: Config):
        """
        Initialize the forecast formatter.

        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger('forecast.formatter')

        # Load formatting options
        self.formats = self.config.get('forecast', 'formats', 'markdown,html,pdf').split(',')
        self.output_dir = Path(self.config.get('general', 'output_directory', './output'))

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.visualizer = ForecastVisualizer(self.logger.getChild('visuals'))
        self.history = HistoricalComparator(self.output_dir, self.logger.getChild('history'))

    def format_forecast(self, forecast_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Format a forecast into the configured output formats.

        Args:
            forecast_data: Complete forecast data with generated text

        Returns:
            Dictionary with paths to formatted output files
        """
        try:
            self.logger.info("Starting forecast formatting")

            # Extract forecast information
            forecast_id = forecast_data.get('forecast_id', f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            generated_time = forecast_data.get('generated_time', datetime.now().isoformat())

            # Create forecast directory
            forecast_dir = self.output_dir / forecast_id
            forecast_dir.mkdir(exist_ok=True)

            # Generate visualizations with error handling
            try:
                self.logger.info("Generating visualizations...")
                visualizations = self.visualizer.generate_all(forecast_data, forecast_dir)
                self.logger.info(f"Generated {len(visualizations)} visualizations")
                forecast_data.setdefault('metadata', {})['visualizations'] = visualizations
            except Exception as e:
                self.logger.error(f"Visualization generation failed: {e}")
                forecast_data.setdefault('metadata', {})['visualizations'] = {}

            # Build historical summary with error handling
            try:
                self.logger.info("Building historical summary...")
                history_summary = self.history.build_summary(forecast_id, forecast_dir, forecast_data)
                if history_summary:
                    self.logger.info("Historical summary completed")
                    forecast_data['metadata']['historical_summary'] = history_summary
                else:
                    self.logger.info("No historical summary available")
            except Exception as e:
                self.logger.error(f"Historical summary generation failed: {e}")

            # Format outputs
            output_paths = {}

            if 'markdown' in self.formats:
                try:
                    self.logger.info("Generating markdown format...")
                    markdown_path = self._format_markdown(forecast_data, forecast_dir)
                    output_paths['markdown'] = str(markdown_path)
                    self.logger.info(f"Markdown format saved to: {markdown_path}")
                except Exception as e:
                    self.logger.error(f"Failed to generate markdown: {e}")

            if 'html' in self.formats:
                try:
                    self.logger.info("Generating HTML format...")
                    html_path = self._format_html(forecast_data, forecast_dir)
                    output_paths['html'] = str(html_path)
                    self.logger.info(f"HTML format saved to: {html_path}")
                except Exception as e:
                    self.logger.error(f"Failed to generate html: {e}")

            if 'pdf' in self.formats:
                try:
                    self.logger.info("Generating PDF format...")
                    pdf_path = self._format_pdf(forecast_data, forecast_dir)
                    output_paths['pdf'] = str(pdf_path)
                    self.logger.info(f"PDF format saved to: {pdf_path}")
                except Exception as e:
                    self.logger.error(f"Failed to generate pdf: {e}")

            # Save original forecast data for reference
            with open(forecast_dir / 'forecast_data.json', 'w') as f:
                # Convert to JSON-serializable format
                serializable_data = self._make_serializable(forecast_data)
                json.dump(serializable_data, f, indent=2)

            output_paths['json'] = str(forecast_dir / 'forecast_data.json')

            self.logger.info(f"Forecast formatting completed for forecast ID: {forecast_id}")
            return output_paths

        except Exception as e:
            self.logger.error(f"Error formatting forecast: {e}")
            return {'error': str(e)}

    def _make_serializable(self, data: Any) -> Any:
        """
        Make data JSON-serializable.

        Args:
            data: Data to make serializable

        Returns:
            JSON-serializable data
        """
        if isinstance(data, dict):
            return {k: self._make_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._make_serializable(item) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            # Convert to string representation
            return str(data)

    def _format_markdown(self, forecast_data: Dict[str, Any], output_dir: Path) -> Path:
        """Format forecast as markdown."""
        self.logger.info("Formatting forecast as markdown")

        forecast_id = forecast_data.get('forecast_id')
        generated_time = forecast_data.get('generated_time')

        try:
            date_obj = datetime.fromisoformat(generated_time.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%B %d, %Y at %H:%M %Z')
        except (ValueError, TypeError):
            date_str = generated_time

        markdown_parts: List[str] = []
        markdown_parts.append("# Hawaii Surf Forecast\n")
        markdown_parts.append(f"*Generated on {date_str}*\n\n")

        main_forecast = forecast_data.get('main_forecast', '')
        if main_forecast:
            formatted = self._format_forecast_text(main_forecast)
            markdown_parts.append(f"## Main Forecast\n\n{formatted}\n\n")

        north_shore = forecast_data.get('north_shore', '')
        if north_shore:
            formatted_ns = self._format_forecast_text(north_shore)
            markdown_parts.append(f"## North Shore Forecast\n\n{formatted_ns}\n\n")

        south_shore = forecast_data.get('south_shore', '')
        if south_shore:
            formatted_ss = self._format_forecast_text(south_shore)
            markdown_parts.append(f"## South Shore Forecast\n\n{formatted_ss}\n\n")

        daily = forecast_data.get('daily', '')
        if daily:
            formatted_daily = self._format_forecast_text(daily)
            markdown_parts.append(f"## Daily Forecast\n\n{formatted_daily}\n\n")

        confidence = forecast_data.get('metadata', {}).get('confidence', {})
        if confidence:
            overall_score = confidence.get('overall_score', 0)
            category = confidence.get('category', 'Moderate')
            breakdown = confidence.get('breakdown', {})

            markdown_parts.append('## Forecast Confidence\n\n')
            markdown_parts.append(
                f"**{category}** Confidence ({breakdown.get('overall_score_out_of_10', overall_score * 10):.1f}/10)\n\n"
            )

            factors = confidence.get('factors', {})
            if factors and breakdown.get('factor_descriptions'):
                markdown_parts.append('**Confidence Factors:**\n\n')
                descriptions = breakdown.get('factor_descriptions', {})
                factors_out_of_10 = breakdown.get('factors', {})

                for factor_key in ['model_consensus', 'source_reliability', 'data_completeness',
                                  'forecast_horizon', 'historical_accuracy']:
                    if factor_key in factors_out_of_10:
                        factor_name = factor_key.replace('_', ' ').title()
                        score_10 = factors_out_of_10[factor_key]
                        description = descriptions.get(factor_key, '')
                        markdown_parts.append(f"- **{factor_name}**: {score_10}/10 - {description}\n")
                markdown_parts.append('\n')

                # Add data source summary
                if 'total_sources' in breakdown:
                    source_counts = breakdown.get('source_counts', {})
                    markdown_parts.append(
                        f"**Data Sources**: {breakdown['total_sources']} sources "
                        f"({source_counts.get('buoys', 0)} buoys, "
                        f"{source_counts.get('models', 0)} models, "
                        f"{source_counts.get('weather', 0)} weather)\n\n"
                    )

        visuals = forecast_data.get('metadata', {}).get('visualizations', {})
        if visuals:
            markdown_parts.append('## Visual Highlights\n\n')
            for name, image_path in visuals.items():
                rel_path = Path(image_path)
                try:
                    rel_path = rel_path.relative_to(output_dir)
                except ValueError:
                    rel_path = Path(image_path).name
                caption = name.replace('_', ' ').title()
                markdown_parts.append(f"![{caption}]({rel_path.as_posix()})\n\n")

        history = forecast_data.get('metadata', {}).get('historical_summary')
        if history:
            prev_id = history.get('previous_id', 'previous forecast')
            prev_time = history.get('previous_generated', 'unknown time')
            markdown_parts.append('## Historical Comparison\n\n')
            markdown_parts.append(f"Compared with **{prev_id}** generated on {prev_time}:\n\n")
            for line in history.get('summary_lines', []):
                markdown_parts.append(f"- {line}\n")
            markdown_parts.append('\n')

        markdown_parts.append('---\n')
        markdown_parts.append('*Generated by SurfCastAI - AI-Powered Surf Forecasting*\n')

        output_path = output_dir / f"{forecast_id}.md"
        with open(output_path, 'w') as fh:
            fh.write(''.join(markdown_parts))
        return output_path
    def _format_html(self, forecast_data: Dict[str, Any], output_dir: Path) -> Path:
        """Format forecast as responsive HTML."""
        self.logger.info("Formatting forecast as HTML")

        forecast_id = forecast_data.get('forecast_id')
        generated_time = forecast_data.get('generated_time')

        try:
            date_obj = datetime.fromisoformat(generated_time.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%B %d, %Y at %H:%M %Z')
        except (ValueError, TypeError, AttributeError):
            date_str = str(generated_time)

        segments: List[str] = []
        segments.append(
            dedent(
                f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hawaii Surf Forecast</title>
    <style>
        body {{
            font-family: 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 960px;
            margin: 0 auto;
            padding: 24px;
            background-color: #f5f7fa;
        }}
        h1, h2, h3 {{
            color: #0066cc;
        }}
        h1 {{
            border-bottom: 2px solid #0066cc;
            padding-bottom: 10px;
            text-align: center;
        }}
        .generated-date {{
            text-align: center;
            font-style: italic;
            color: #666;
            margin-bottom: 30px;
        }}
        .forecast-section {{
            background-color: #ffffff;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 28px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }}
        .forecast-section h2 {{
            margin-top: 0;
            border-bottom: 1px solid #e5eaf1;
            padding-bottom: 12px;
        }}
        .shore-specific {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .shore-forecast {{
            flex: 1;
            min-width: 300px;
        }}
        .confidence-meter {{
            background-color: #e8ecf5;
            height: 18px;
            border-radius: 10px;
            margin: 10px 0;
            overflow: hidden;
        }}
        .confidence-level {{
            height: 100%;
            background-color: #0066cc;
        }}
        .confidence-factors {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .factor {{
            flex: 1;
            min-width: 160px;
            background-color: #f0f4ff;
            padding: 10px;
            border-radius: 5px;
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
        }}
        .chart-card {{
            background-color: #ffffff;
            border-radius: 6px;
            padding: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .chart-card img {{
            width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        .history-card ul {{
            padding-left: 18px;
        }}
        .history-card ul li {{
            margin-bottom: 6px;
        }}
        @media (max-width: 640px) {{
            body {{
                padding: 14px;
            }}
            .shore-specific {{
                flex-direction: column;
            }}
        }}
        .footer {{
            text-align: center;
            font-size: 0.9em;
            color: #666;
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #d7dce5;
        }}
    </style>
</head>
<body>
    <h1>Hawaii Surf Forecast</h1>
    <div class="generated-date">Generated on {date_str}</div>
"""
            )
        )

        main_forecast = forecast_data.get('main_forecast', '')
        if main_forecast:
            formatted = self._markdown_to_html(self._format_forecast_text(main_forecast))
            segments.append(
                dedent(
                    f"""    <div class="forecast-section">
        <h2>Main Forecast</h2>
        {formatted}
    </div>
"""
                )
            )

        north_shore = forecast_data.get('north_shore', '')
        south_shore = forecast_data.get('south_shore', '')
        if north_shore or south_shore:
            shore_sections: List[str] = ['    <div class="shore-specific">']
            if north_shore:
                formatted_ns = self._markdown_to_html(self._format_forecast_text(north_shore))
                shore_sections.append(
                    dedent(
                        f"""        <div class="forecast-section shore-forecast">
            <h2>North Shore Forecast</h2>
            {formatted_ns}
        </div>
"""
                    ).rstrip('\n')
                )
            if south_shore:
                formatted_ss = self._markdown_to_html(self._format_forecast_text(south_shore))
                shore_sections.append(
                    dedent(
                        f"""        <div class="forecast-section shore-forecast">
            <h2>South Shore Forecast</h2>
            {formatted_ss}
        </div>
"""
                    ).rstrip('\n')
                )
            shore_sections.append("    </div>")
            segments.append("\n".join(shore_sections) + "\n")

        daily = forecast_data.get('daily', '')
        if daily:
            formatted_daily = self._markdown_to_html(self._format_forecast_text(daily))
            segments.append(
                dedent(
                    f"""    <div class="forecast-section">
        <h2>Daily Forecast</h2>
        {formatted_daily}
    </div>
"""
                )
            )

        visuals = forecast_data.get('metadata', {}).get('visualizations', {})
        if visuals:
            visual_block = [
                '    <div class="forecast-section">',
                '        <h2>Visual Highlights</h2>',
                '        <div class="charts-grid">',
            ]
            for name, image_path in visuals.items():
                rel_path = Path(image_path)
                try:
                    rel_path = rel_path.relative_to(output_dir)
                except ValueError:
                    rel_path = Path(image_path).name
                caption = name.replace('_', ' ').title()
                visual_block.append(
                    dedent(
                        f"""            <div class="chart-card">
                <img src="{rel_path.as_posix()}" alt="{caption}" loading="lazy">
                <p><strong>{caption}</strong></p>
            </div>
"""
                    ).rstrip('\n')
                )
            visual_block.extend(['        </div>', '    </div>'])
            segments.append("\n".join(visual_block) + "\n")

        history = forecast_data.get('metadata', {}).get('historical_summary')
        if history:
            prev_id = history.get('previous_id', 'previous forecast')
            prev_time = history.get('previous_generated', 'unknown time')
            history_block = [
                '    <div class="forecast-section history-card">',
                f'        <h2>Historical Comparison</h2>',
                f'        <p>Compared with <strong>{prev_id}</strong> generated on {prev_time}:</p>',
                '        <ul>',
            ]
            for line in history.get('summary_lines', []):
                history_block.append(f"            <li>{line}</li>")
            history_block.extend(['        </ul>', '    </div>'])
            segments.append("\n".join(history_block) + "\n")

        confidence = forecast_data.get('metadata', {}).get('confidence', {})
        if confidence:
            overall_score = confidence.get('overall_score', 0)
            confidence_percent = int(overall_score * 100)
            segments.append(
                dedent(
                    f"""    <div class="forecast-section">
        <h2>Forecast Confidence</h2>
        <p>Overall confidence: {overall_score:.1f}/1.0</p>
        <div class="confidence-meter">
            <div class="confidence-level" style="width: {confidence_percent}%"></div>
        </div>
"""
                )
            )
            factors = confidence.get('factors', {})
            if factors:
                factor_lines = ['        <h3>Confidence Factors</h3>', '        <div class="confidence-factors">']
                for factor, value in factors.items():
                    factor_percent = int(value * 100)
                    factor_name = factor.replace('_', ' ').title()
                    factor_lines.append(
                        dedent(
                            f"""            <div class="factor">
                <p>{factor_name}: {value:.1f}</p>
                <div class="confidence-meter">
                    <div class="confidence-level" style="width: {factor_percent}%"></div>
                </div>
            </div>
"""
                        ).rstrip('\n')
                    )
                factor_lines.append('        </div>')
                segments.append("\n".join(factor_lines) + "\n")
            segments.append("    </div>\n")

        segments.append(
            dedent(
                """    <div class="footer">
        Generated by SurfCastAI - AI-Powered Surf Forecasting
    </div>
</body>
</html>
"""
            )
        )

        html = ''.join(segments)
        output_path = output_dir / f"{forecast_id}.html"
        with open(output_path, 'w') as fh:
            fh.write(html)
        return output_path


    def _format_pdf(self, forecast_data: Dict[str, Any], output_dir: Path) -> Path:
        """
        Format forecast as PDF.

        Args:
            forecast_data: Complete forecast data
            output_dir: Output directory

        Returns:
            Path to PDF file
        """
        self.logger.info("Formatting forecast as PDF")

        # Create HTML version first
        html_path = self._format_html(forecast_data, output_dir)

        try:
            # Import weasyprint for PDF generation
            import weasyprint

            # Extract forecast information
            forecast_id = forecast_data.get('forecast_id')

            # Generate PDF
            pdf_path = output_dir / f"{forecast_id}.pdf"
            weasyprint.HTML(filename=str(html_path), base_url=str(output_dir)).write_pdf(pdf_path)

            return pdf_path

        except ImportError:
            self.logger.error("WeasyPrint not installed. Please install it with: pip install weasyprint")
            # Return the HTML path as fallback
            return html_path
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            # Return the HTML path as fallback
            return html_path

    def _format_forecast_text(self, text: str) -> str:
        """
        Format raw forecast text by adding proper markdown structure.

        Args:
            text: Raw forecast text

        Returns:
            Formatted text
        """
        # Add heading levels to all-caps lines
        lines = text.split('\n')
        formatted_lines = []

        for line in lines:
            # Skip empty lines
            if not line.strip():
                formatted_lines.append(line)
                continue

            # Check if line is an all-caps header
            if line.isupper() and len(line) > 5:
                # Convert to title case for better readability
                title_line = line.title()
                formatted_lines.append(f"### {title_line}")
            elif line.strip().isupper() and len(line) > 5:
                # Handle lines with leading/trailing whitespace
                title_line = line.strip().title()
                formatted_lines.append(f"### {title_line}")
            else:
                formatted_lines.append(line)

        formatted_text = '\n'.join(formatted_lines)

        # Highlight important terms (feet, wave heights, etc.)
        formatted_text = re.sub(r'(\d+[\-\–]?\d*\s*(?:feet|foot|ft)(?:\s*\(Hawaiian\s*(?:scale)?\)?)?)',
                              r'**\1**', formatted_text, flags=re.IGNORECASE)

        formatted_text = re.sub(r'(\d+[\-\–]\d+\s*(?:seconds|second|sec|s))',
                              r'**\1**', formatted_text, flags=re.IGNORECASE)

        return formatted_text

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert markdown to HTML.

        Args:
            markdown_text: Markdown text

        Returns:
            HTML text
        """
        try:
            # Try to import markdown
            import markdown

            # Convert markdown to HTML
            html = markdown.markdown(markdown_text)
            return html

        except ImportError:
            self.logger.warning("Markdown not installed. Using basic HTML conversion.")

            # Basic conversion
            html = markdown_text

            # Convert headers
            html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
            html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
            html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

            # Convert bold
            html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)

            # Convert italic
            html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)

            # Convert paragraphs
            html = re.sub(r'\n\n', r'</p><p>', html)
            html = f"<p>{html}</p>"

            return html
