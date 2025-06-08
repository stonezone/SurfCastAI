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

from ..core.config import Config


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
            
            # Format outputs
            output_paths = {}
            
            if 'markdown' in self.formats:
                markdown_path = self._format_markdown(forecast_data, forecast_dir)
                output_paths['markdown'] = str(markdown_path)
            
            if 'html' in self.formats:
                html_path = self._format_html(forecast_data, forecast_dir)
                output_paths['html'] = str(html_path)
            
            if 'pdf' in self.formats:
                pdf_path = self._format_pdf(forecast_data, forecast_dir)
                output_paths['pdf'] = str(pdf_path)
            
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
        """
        Format forecast as markdown.
        
        Args:
            forecast_data: Complete forecast data
            output_dir: Output directory
            
        Returns:
            Path to markdown file
        """
        self.logger.info("Formatting forecast as markdown")
        
        # Extract forecast information
        forecast_id = forecast_data.get('forecast_id')
        generated_time = forecast_data.get('generated_time')
        
        # Generate human-readable date
        try:
            date_obj = datetime.fromisoformat(generated_time.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%B %d, %Y at %H:%M %Z')
        except (ValueError, TypeError):
            date_str = generated_time
        
        # Create markdown content
        markdown = f"# Hawaii Surf Forecast\n\n"
        markdown += f"*Generated on {date_str}*\n\n"
        
        # Add main forecast
        main_forecast = forecast_data.get('main_forecast', '')
        if main_forecast:
            # Format main forecast by adding headers
            formatted_forecast = self._format_forecast_text(main_forecast)
            markdown += f"## Main Forecast\n\n{formatted_forecast}\n\n"
        
        # Add shore-specific forecasts
        north_shore = forecast_data.get('north_shore', '')
        if north_shore:
            # Format north shore forecast
            formatted_ns = self._format_forecast_text(north_shore)
            markdown += f"## North Shore Forecast\n\n{formatted_ns}\n\n"
        
        south_shore = forecast_data.get('south_shore', '')
        if south_shore:
            # Format south shore forecast
            formatted_ss = self._format_forecast_text(south_shore)
            markdown += f"## South Shore Forecast\n\n{formatted_ss}\n\n"
        
        # Add daily forecast
        daily = forecast_data.get('daily', '')
        if daily:
            # Format daily forecast
            formatted_daily = self._format_forecast_text(daily)
            markdown += f"## Daily Forecast\n\n{formatted_daily}\n\n"
        
        # Add confidence information
        confidence = forecast_data.get('metadata', {}).get('confidence', {})
        if confidence:
            overall_score = confidence.get('overall_score', 0)
            markdown += f"## Forecast Confidence\n\n"
            markdown += f"Overall confidence: {overall_score:.1f}/1.0\n\n"
            
            # Add confidence factors
            factors = confidence.get('factors', {})
            if factors:
                markdown += "**Confidence Factors:**\n\n"
                for factor, value in factors.items():
                    markdown += f"- {factor.replace('_', ' ').title()}: {value:.1f}/1.0\n"
                markdown += "\n"
        
        # Add footer
        markdown += "---\n"
        markdown += "*Generated by SurfCastAI - AI-Powered Surf Forecasting*\n"
        
        # Write to file
        output_path = output_dir / f"{forecast_id}.md"
        with open(output_path, 'w') as f:
            f.write(markdown)
        
        return output_path
    
    def _format_html(self, forecast_data: Dict[str, Any], output_dir: Path) -> Path:
        """
        Format forecast as HTML.
        
        Args:
            forecast_data: Complete forecast data
            output_dir: Output directory
            
        Returns:
            Path to HTML file
        """
        self.logger.info("Formatting forecast as HTML")
        
        # Extract forecast information
        forecast_id = forecast_data.get('forecast_id')
        generated_time = forecast_data.get('generated_time')
        
        # Generate human-readable date
        try:
            date_obj = datetime.fromisoformat(generated_time.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%B %d, %Y at %H:%M %Z')
        except (ValueError, TypeError):
            date_str = generated_time
        
        # Create HTML content with CSS styling
        html = f"""<!DOCTYPE html>
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
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        h1, h2, h3, h4 {{
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
            background-color: white;
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .forecast-section h2 {{
            margin-top: 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
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
            background-color: #eee;
            height: 20px;
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
            gap: 10px;
        }}
        .factor {{
            flex: 1;
            min-width: 150px;
            background-color: #f0f0f0;
            padding: 10px;
            border-radius: 5px;
        }}
        .footer {{
            text-align: center;
            font-size: 0.9em;
            color: #666;
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <h1>Hawaii Surf Forecast</h1>
    <div class="generated-date">Generated on {date_str}</div>
"""
        
        # Add main forecast
        main_forecast = forecast_data.get('main_forecast', '')
        if main_forecast:
            # Format main forecast
            formatted_forecast = self._format_forecast_text(main_forecast)
            formatted_forecast = self._markdown_to_html(formatted_forecast)
            
            html += f"""    <div class="forecast-section">
        <h2>Main Forecast</h2>
        {formatted_forecast}
    </div>
"""
        
        # Add shore-specific forecasts
        north_shore = forecast_data.get('north_shore', '')
        south_shore = forecast_data.get('south_shore', '')
        
        if north_shore or south_shore:
            html += f"""    <div class="shore-specific">
"""
            
            if north_shore:
                # Format north shore forecast
                formatted_ns = self._format_forecast_text(north_shore)
                formatted_ns = self._markdown_to_html(formatted_ns)
                
                html += f"""        <div class="forecast-section shore-forecast">
            <h2>North Shore Forecast</h2>
            {formatted_ns}
        </div>
"""
            
            if south_shore:
                # Format south shore forecast
                formatted_ss = self._format_forecast_text(south_shore)
                formatted_ss = self._markdown_to_html(formatted_ss)
                
                html += f"""        <div class="forecast-section shore-forecast">
            <h2>South Shore Forecast</h2>
            {formatted_ss}
        </div>
"""
            
            html += f"""    </div>
"""
        
        # Add daily forecast
        daily = forecast_data.get('daily', '')
        if daily:
            # Format daily forecast
            formatted_daily = self._format_forecast_text(daily)
            formatted_daily = self._markdown_to_html(formatted_daily)
            
            html += f"""    <div class="forecast-section">
        <h2>Daily Forecast</h2>
        {formatted_daily}
    </div>
"""
        
        # Add confidence information
        confidence = forecast_data.get('metadata', {}).get('confidence', {})
        if confidence:
            overall_score = confidence.get('overall_score', 0)
            confidence_percent = int(overall_score * 100)
            
            html += f"""    <div class="forecast-section">
        <h2>Forecast Confidence</h2>
        <p>Overall confidence: {overall_score:.1f}/1.0</p>
        <div class="confidence-meter">
            <div class="confidence-level" style="width: {confidence_percent}%;"></div>
        </div>
"""
            
            # Add confidence factors
            factors = confidence.get('factors', {})
            if factors:
                html += f"""        <h3>Confidence Factors</h3>
        <div class="confidence-factors">
"""
                
                for factor, value in factors.items():
                    factor_percent = int(value * 100)
                    factor_name = factor.replace('_', ' ').title()
                    
                    html += f"""            <div class="factor">
                <p>{factor_name}: {value:.1f}</p>
                <div class="confidence-meter">
                    <div class="confidence-level" style="width: {factor_percent}%;"></div>
                </div>
            </div>
"""
                
                html += f"""        </div>
"""
            
            html += f"""    </div>
"""
        
        # Add footer
        html += f"""    <div class="footer">
        Generated by SurfCastAI - AI-Powered Surf Forecasting
    </div>
</body>
</html>
"""
        
        # Write to file
        output_path = output_dir / f"{forecast_id}.html"
        with open(output_path, 'w') as f:
            f.write(html)
        
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
            weasyprint.HTML(filename=str(html_path)).write_pdf(pdf_path)
            
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