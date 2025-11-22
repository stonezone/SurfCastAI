#!/usr/bin/env python3
"""
 ██████╗██╗   ██╗██████╗ ███████╗██████╗  ██████╗ █████╗ ███████╗████████╗ █████╗ ██╗
██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║
██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝██║     ███████║███████╗   ██║   ███████║██║
██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗██║     ██╔══██║╚════██║   ██║   ██╔══██║██║
╚██████╗   ██║   ██████╔╝███████╗██║  ██║╚██████╗██║  ██║███████║   ██║   ██║  ██║██║
 ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝

88     88   db   Yb        dP    db    88 88         .dP"Y8 88  88 88""Yb 888888
88     88  dPYb   Yb  db  dP    dPYb   88 88         `Ybo." 88  88 88__dP 88__
88  .o 88 dP__Yb   YbdPYbdP    dP__Yb  88 88   oooo  o.`Y8b 88  88 88"Yb  88""
88ood8 88 dP""" "Yb   YP  YP    dP" """Yb 88 88   oooo  8bodP' 88ood8 88  Yb 88

╭─ NEURAL WAVE PREDICTION SYSTEM v2.1.1 ─ [CLASSIFIED] ─ HAWAII DIVISION ──────╮
│                                                                               │
│  🌊 AI-POWERED SURF FORECASTING TERMINAL 🌊                                 │
│  📡 SATELLITE UPLINK: ACTIVE                                                │
│  🎯 PREDICTION ACCURACY: 94.7%                                              │
│  ⚡ QUANTUM PROCESSORS: ONLINE                                               │
│                                                                               │
╰───────────────────────────── [PRESS ANY KEY TO JACK IN] ────────────────────╯

80s Cyberpunk Command Line Interface for SurfCastAI
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import box
from rich.align import Align
from rich.columns import Columns

# Rich imports for gorgeous terminal UI
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Import SurfCastAI modules
try:
    from src.core import Config, load_config
    from src.main import run_pipeline, setup_logging

    SURFCAST_AVAILABLE = True
except ImportError as e:
    SURFCAST_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Initialize Rich console
console = Console()

# Cyberpunk color theme
NEON_CYAN = "#00FFFF"
NEON_MAGENTA = "#FF00FF"
NEON_GREEN = "#00FF00"
NEON_YELLOW = "#FFFF00"
NEON_ORANGE = "#FF8000"
DARK_BLUE = "#000080"
MATRIX_GREEN = "#00FF41"
ERROR_RED = "#FF0040"
WARNING_AMBER = "#FFB000"


class SurfCastCLI:
    """
    Cyberpunk-themed CLI launcher for SurfCastAI.
    """

    def __init__(self):
        self.config = None
        self.available_models = [
            "gpt-4o",
            "gpt-4o-2024-08-06",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]
        self.current_model = "gpt-4o"
        self.load_config()

    def load_config(self):
        """Load SurfCastAI configuration."""
        try:
            self.config = load_config()
            self.current_model = self.config.get("openai", "model", "gpt-4o")
        except Exception:
            self.config = None

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    def show_banner(self):
        """Display the epic cyberpunk banner."""
        banner_text = """
███████╗██╗   ██╗██████╗ ███████╗ ██████╗ █████╗ ███████╗████████╗     █████╗ ██╗
██╔════╝██║   ██║██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝╚══██╔══╝    ██╔══██╗██║
███████╗██║   ██║██████╔╝█████╗  ██║     ███████║███████╗   ██║       ███████║██║
╚════██║██║   ██║██╔══██╗██╔══╝  ██║     ██╔══██║╚════██║   ██║       ██╔══██║██║
███████║╚██████╔╝██║  ██║██║     ╚██████╗██║  ██║███████║   ██║       ██║  ██║██║
╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝      ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝       ╚═╝  ╚═╝╚═╝

██╗  ██╗ █████╗ ██╗    ██╗ █████╗ ██╗██╗    ██╗ █████╗ ██╗   ██╗███████╗███████╗
██║  ██║██╔══██╗██║    ██║██╔══██╗██║██║    ██║██╔══██╗██║   ██║██╔════╝██╔════╝
███████║███████║██║ █╗ ██║███████║██║██║ █╗ ██║███████║██║   ██║█████╗  ███████╗
██╔══██║██╔══██║██║███╗██║██╔══██║██║██║███╗██║██╔══██║╚██╗ ██╔╝██╔══╝  ╚════██║
██║  ██║██║  ██║╚███╔███╔╝██║  ██║██║╚███╔███╔╝██║  ██║ ╚████╔╝ ███████╗███████║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝ ╚══╝╚══╝ ╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝
        """

        subtitle = (
            """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🌊 NEURAL WAVE PREDICTION SYSTEM v2.1.1 🌊              ║
║                           [CLASSIFIED] - HAWAII DIVISION                     ║
║                                                                              ║
║  📡 SATELLITE UPLINK: [ACTIVE]     🎯 PREDICTION ACCURACY: 94.7%           ║
║  ⚡ QUANTUM CORES: [ONLINE]         💎 DATA FUSION: [OPERATIONAL]           ║
║  🧠 AI MODEL: """
            + f"{self.current_model:<13}"
            + """     🔮 FORECAST ENGINE: [READY]     ║
║                                                                              ║
║           >>> ADVANCED SURF INTELLIGENCE FOR THE DIGITAL AGE <<<            ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        )

        # Create gradient effect for banner
        banner_panel = Panel(
            Align.center(
                Text(banner_text, style=f"bold {NEON_CYAN}")
                + Text(subtitle, style=f"bold {NEON_MAGENTA}")
            ),
            box=box.DOUBLE,
            border_style=NEON_GREEN,
            title="[bold cyan]⚡ TERMINAL ACCESS GRANTED ⚡[/bold cyan]",
            title_align="center",
        )

        console.print(banner_panel)

        # Status bar
        status_text = f"🔗 CONNECTION: SECURE | 📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 🌐 NODE: OAHU-PRIME | 🔋 POWER: 100%"
        console.print(
            Panel(
                Align.center(Text(status_text, style=f"bold {MATRIX_GREEN}")),
                box=box.HEAVY,
                border_style=DARK_BLUE,
            )
        )
        console.print()

    def show_main_menu(self):
        """Display the main cyberpunk menu."""
        menu_items = [
            (
                "1",
                "🚀 FULL NEURAL PIPELINE",
                "Execute complete data collection → processing → forecast → AI analysis",
                NEON_CYAN,
            ),
            (
                "2",
                "📡 DATA COLLECTION ONLY",
                "Gather fresh intel from satellites, buoys, and weather stations",
                NEON_GREEN,
            ),
            (
                "3",
                "⚙️  DATA PROCESSING ONLY",
                "Process existing data bundles through quantum fusion algorithms",
                NEON_YELLOW,
            ),
            (
                "4",
                "🔮 FORECAST GENERATION",
                "Generate AI-powered surf predictions from processed data",
                NEON_MAGENTA,
            ),
            ("5", "🧠 AI ANALYSIS ONLY", "Run GPT analysis on existing forecasts", NEON_ORANGE),
            ("", "─" * 75, "", "dim"),
            (
                "6",
                "🎯 GPT MODEL SELECTOR",
                f"Current: {self.current_model} | Switch AI analysis models",
                WARNING_AMBER,
            ),
            ("7", "📊 BUNDLE MANAGER", "View, analyze, and manage data bundles", NEON_CYAN),
            (
                "8",
                "📈 SYSTEM MONITORING",
                "Live logs, performance metrics, health status",
                MATRIX_GREEN,
            ),
            (
                "9",
                "🛠️  DEVELOPER TOOLS",
                "Benchmarks, tests, demos, and debugging utilities",
                NEON_YELLOW,
            ),
            ("", "─" * 75, "", "dim"),
            ("A", "⚙️  CONFIGURATION", "View and modify system configuration", NEON_GREEN),
            (
                "B",
                "📚 HELP & EXAMPLES",
                "Documentation, usage examples, and tutorials",
                NEON_MAGENTA,
            ),
            ("C", "📋 README & STATUS", "View project documentation and system status", NEON_CYAN),
            ("D", "🔍 DEPENDENCY CHECK", "Verify and update system dependencies", WARNING_AMBER),
            ("", "─" * 75, "", "dim"),
            ("Q", "🚪 DISCONNECT", "Exit the neural interface", ERROR_RED),
        ]

        # Create a fancy table for the menu
        table = Table(box=box.DOUBLE_EDGE, border_style=NEON_CYAN, show_header=False)
        table.add_column("CMD", justify="center", style="bold", width=5)
        table.add_column("OPERATION", style="bold", width=25)
        table.add_column("DESCRIPTION", width=45)

        for cmd, operation, description, color in menu_items:
            if cmd == "":
                table.add_row("", operation, "", style="dim")
            else:
                table.add_row(
                    f"[{color}]{cmd}[/{color}]",
                    f"[{color}]{operation}[/{color}]",
                    f"[dim]{description}[/dim]",
                )

        menu_panel = Panel(
            table,
            title="[bold neon]⚡ MAIN NEURAL INTERFACE ⚡[/bold neon]",
            title_align="center",
            border_style=NEON_MAGENTA,
            box=box.DOUBLE_EDGE,
        )

        console.print(menu_panel)
        console.print()

    def get_user_choice(self) -> str:
        """Get user menu choice with cyberpunk styling."""
        choice_prompt = Text(">>> SELECT NEURAL COMMAND", style=f"bold {NEON_GREEN}")
        choice_prompt.append(" [", style="dim")
        choice_prompt.append("1-9, A-D, Q", style=f"bold {NEON_YELLOW}")
        choice_prompt.append("]: ", style="dim")

        console.print(choice_prompt, end="")
        choice = input().strip().upper()
        console.print()
        return choice

    def loading_animation(self, message: str, duration: float = 2.0):
        """Show a cyberpunk loading animation."""
        with Progress(
            SpinnerColumn(spinner_style=NEON_CYAN),
            TextColumn(f"[{NEON_GREEN}]{message}[/{NEON_GREEN}]"),
            BarColumn(bar_width=40, style=NEON_MAGENTA, complete_style=NEON_CYAN),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=100)
            for i in range(100):
                time.sleep(duration / 100)
                progress.update(task, advance=1)

    async def run_pipeline_mode(self, mode: str, description: str):
        """Run SurfCastAI pipeline with cyberpunk interface."""
        if not SURFCAST_AVAILABLE:
            console.print(
                Panel(
                    f"[{ERROR_RED}]❌ SYSTEM ERROR: SurfCastAI modules not available[/{ERROR_RED}]\n"
                    f"[dim]Import Error: {IMPORT_ERROR}[/dim]",
                    title="[red]NEURAL INTERFACE FAILURE[/red]",
                    border_style=ERROR_RED,
                )
            )
            return

        console.print(
            Panel(
                f"[{NEON_CYAN}]🚀 INITIALIZING: {description}[/{NEON_CYAN}]\n"
                f"[dim]Mode: {mode} | Model: {self.current_model}[/dim]",
                title="[cyan]NEURAL PIPELINE ACTIVATED[/cyan]",
                border_style=NEON_CYAN,
            )
        )

        try:
            # Load config and setup logging
            config = load_config()
            logger = setup_logging(config)

            # Update model in config if different
            if hasattr(config, "_config") and "openai" in config._config:
                config._config["openai"]["model"] = self.current_model

            # Show fancy progress
            console.print(
                f"[{NEON_GREEN}]📡 Establishing quantum link to data sources...[/{NEON_GREEN}]"
            )
            time.sleep(1)

            console.print(f"[{NEON_YELLOW}]⚡ Spinning up neural processors...[/{NEON_YELLOW}]")
            time.sleep(1)

            console.print(
                f"[{NEON_MAGENTA}]🧠 Loading AI model: {self.current_model}[/{NEON_MAGENTA}]"
            )
            time.sleep(1)

            # Run the actual pipeline
            with Progress(
                SpinnerColumn(spinner_style=NEON_CYAN),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"[{NEON_GREEN}]Executing {mode} pipeline...[/{NEON_GREEN}]", total=None
                )

                results = await run_pipeline(config, logger, mode)

                progress.update(task, completed=True)

            # Display results
            self.show_pipeline_results(results, mode)

        except Exception as e:
            console.print(
                Panel(
                    f"[{ERROR_RED}]❌ PIPELINE FAILURE: {str(e)}[/{ERROR_RED}]\n"
                    f"[dim]Check logs for detailed error information[/dim]",
                    title="[red]SYSTEM MALFUNCTION[/red]",
                    border_style=ERROR_RED,
                )
            )

        console.print(f"\n[{NEON_CYAN}]Press Enter to return to main interface...[/{NEON_CYAN}]")
        input()

    def show_pipeline_results(self, results: dict[str, Any], mode: str):
        """Display pipeline results with cyberpunk styling."""

        # Create results table
        table = Table(
            title=f"[{NEON_CYAN}]🎯 PIPELINE EXECUTION REPORT - {mode.upper()}[/{NEON_CYAN}]",
            box=box.DOUBLE_EDGE,
            border_style=NEON_GREEN,
        )
        table.add_column("COMPONENT", style="bold")
        table.add_column("STATUS", justify="center")
        table.add_column("DETAILS")

        for component, result in results.items():
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                if status == "success":
                    status_icon = f"[{NEON_GREEN}]✅ SUCCESS[/{NEON_GREEN}]"
                elif status == "error":
                    status_icon = f"[{ERROR_RED}]❌ FAILED[/{ERROR_RED}]"
                else:
                    status_icon = f"[{WARNING_AMBER}]⚠️ {status.upper()}[/{WARNING_AMBER}]"

                # Extract meaningful details
                details = []
                if "bundle_id" in result:
                    details.append(f"Bundle: {result['bundle_id']}")
                if "forecast_id" in result:
                    details.append(f"Forecast: {result['forecast_id']}")
                if "formats" in result:
                    details.append(f"Formats: {', '.join(result['formats'].keys())}")

                detail_text = " | ".join(details) if details else "No additional details"

                table.add_row(
                    f"[{NEON_CYAN}]{component.upper()}[/{NEON_CYAN}]",
                    status_icon,
                    f"[dim]{detail_text}[/dim]",
                )

        console.print(table)

        # Show output files if available
        if "forecast" in results and "formats" in results["forecast"]:
            formats = results["forecast"]["formats"]
            console.print(f"\n[{NEON_MAGENTA}]📁 OUTPUT FILES GENERATED:[/{NEON_MAGENTA}]")
            for format_name, file_path in formats.items():
                console.print(
                    f"   • [{NEON_YELLOW}]{format_name.upper()}[/{NEON_YELLOW}]: {file_path}"
                )

    def select_gpt_model(self):
        """Allow user to select GPT model with cyberpunk interface."""
        console.print(
            Panel(
                f"[{NEON_MAGENTA}]🧠 AI MODEL SELECTION INTERFACE[/{NEON_MAGENTA}]\n"
                f"[dim]Current Model: {self.current_model}[/dim]",
                title="[magenta]NEURAL MODEL MATRIX[/magenta]",
                border_style=NEON_MAGENTA,
            )
        )

        # Create model table
        table = Table(box=box.ROUNDED, border_style=NEON_CYAN)
        table.add_column("ID", justify="center", style="bold")
        table.add_column("MODEL", style="bold")
        table.add_column("DESCRIPTION", width=50)
        table.add_column("STATUS", justify="center")

        model_descriptions = {
            "gpt-4o": "Latest flagship model with vision, fastest and most capable",
            "gpt-4o-2024-08-06": "Specific stable version of GPT-4o with consistent performance",
            "gpt-4o-mini": "Smaller, faster model for simple analysis tasks",
            "gpt-4-turbo": "Previous generation turbo model, still very capable",
            "gpt-4": "Original GPT-4 model, reliable and well-tested",
            "gpt-3.5-turbo": "Legacy model, fastest but less sophisticated",
        }

        for i, model in enumerate(self.available_models):
            current = "👑 ACTIVE" if model == self.current_model else ""
            description = model_descriptions.get(model, "Advanced language model")

            table.add_row(
                f"[{NEON_YELLOW}]{i+1}[/{NEON_YELLOW}]",
                f"[{NEON_GREEN}]{model}[/{NEON_GREEN}]",
                f"[dim]{description}[/dim]",
                f"[{NEON_CYAN}]{current}[/{NEON_CYAN}]" if current else "",
            )

        console.print(table)
        console.print()

        try:
            choice = Prompt.ask(
                f"[{NEON_GREEN}]Select model[/{NEON_GREEN}]",
                choices=[str(i + 1) for i in range(len(self.available_models))],
                default="1",
            )

            new_model = self.available_models[int(choice) - 1]

            if new_model != self.current_model:
                console.print(
                    f"\n[{NEON_CYAN}]🔄 Switching AI model: {self.current_model} → {new_model}[/{NEON_CYAN}]"
                )
                self.current_model = new_model

                # Update config file if possible
                try:
                    config_path = Path("config/config.yaml")
                    if config_path.exists():
                        # Simple replacement in config file
                        with open(config_path) as f:
                            content = f.read()

                        # Replace model line
                        import re

                        content = re.sub(r"model: gpt-[\w\-\.]+", f"model: {new_model}", content)

                        with open(config_path, "w") as f:
                            f.write(content)

                        console.print(f"[{NEON_GREEN}]✅ Configuration updated![/{NEON_GREEN}]")

                except Exception as e:
                    console.print(
                        f"[{WARNING_AMBER}]⚠️ Could not update config file: {e}[/{WARNING_AMBER}]"
                    )
            else:
                console.print(f"\n[{NEON_YELLOW}]Model unchanged: {new_model}[/{NEON_YELLOW}]")

        except (ValueError, KeyboardInterrupt):
            console.print(f"[{WARNING_AMBER}]Operation cancelled[/{WARNING_AMBER}]")

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def show_bundle_manager(self):
        """Show bundle management interface."""
        if not SURFCAST_AVAILABLE:
            console.print(
                Panel(
                    f"[{ERROR_RED}]❌ SurfCastAI modules not available[/{ERROR_RED}]",
                    title="[red]MODULE ERROR[/red]",
                    border_style=ERROR_RED,
                )
            )
            console.print(f"[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
            input()
            return

        console.print(
            Panel(
                f"[{NEON_CYAN}]📊 DATA BUNDLE MANAGEMENT SYSTEM[/{NEON_CYAN}]",
                title="[cyan]QUANTUM STORAGE MATRIX[/cyan]",
                border_style=NEON_CYAN,
            )
        )

        try:
            from src.core import BundleManager

            config = load_config() if self.config else None
            data_dir = config.data_directory if config else Path("./data")
            bundle_manager = BundleManager(data_dir)
            bundles = bundle_manager.list_bundles()

            if not bundles:
                console.print(
                    f"[{WARNING_AMBER}]📭 No data bundles found in quantum storage[/{WARNING_AMBER}]"
                )
            else:
                # Create bundles table
                table = Table(box=box.ROUNDED, border_style=NEON_GREEN)
                table.add_column("#", justify="center", style="bold")
                table.add_column("BUNDLE ID", style="bold")
                table.add_column("TIMESTAMP", style="dim")
                table.add_column("FILES", justify="center")
                table.add_column("SUCCESS RATE", justify="center")
                table.add_column("SIZE", justify="center")

                for i, bundle in enumerate(bundles[:10]):  # Show top 10
                    bundle_id = bundle.get("bundle_id", "unknown")
                    timestamp = bundle.get("timestamp", "unknown")
                    stats = bundle.get("stats", {})
                    total_files = stats.get("total_files", 0)
                    successful = stats.get("successful_files", 0)
                    size_mb = stats.get("total_size_mb", 0)

                    success_rate = (successful / total_files * 100) if total_files > 0 else 0
                    rate_color = (
                        NEON_GREEN
                        if success_rate > 80
                        else WARNING_AMBER if success_rate > 50 else ERROR_RED
                    )

                    table.add_row(
                        f"[{NEON_YELLOW}]{i+1}[/{NEON_YELLOW}]",
                        f"[{NEON_CYAN}]{bundle_id}[/{NEON_CYAN}]",
                        f"[dim]{timestamp}[/dim]",
                        f"[{NEON_MAGENTA}]{successful}/{total_files}[/{NEON_MAGENTA}]",
                        f"[{rate_color}]{success_rate:.1f}%[/{rate_color}]",
                        f"[dim]{size_mb:.1f} MB[/dim]",
                    )

                console.print(table)

                if len(bundles) > 10:
                    console.print(f"[dim]... and {len(bundles) - 10} more bundles[/dim]")

        except Exception as e:
            console.print(
                Panel(
                    f"[{ERROR_RED}]❌ Error accessing bundle storage: {str(e)}[/{ERROR_RED}]",
                    title="[red]STORAGE ERROR[/red]",
                    border_style=ERROR_RED,
                )
            )

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def show_system_status(self):
        """Show system monitoring interface."""
        console.print(
            Panel(
                f"[{NEON_GREEN}]📈 NEURAL SYSTEM MONITORING DASHBOARD[/{NEON_GREEN}]",
                title="[green]QUANTUM DIAGNOSTICS[/green]",
                border_style=NEON_GREEN,
            )
        )

        # System info table
        table = Table(box=box.ROUNDED, border_style=NEON_CYAN, title="SYSTEM STATUS")
        table.add_column("COMPONENT", style="bold")
        table.add_column("STATUS", justify="center")
        table.add_column("DETAILS")

        # Check Python version
        python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        table.add_row(
            f"[{NEON_CYAN}]PYTHON RUNTIME[/{NEON_CYAN}]",
            f"[{NEON_GREEN}]✅ ACTIVE[/{NEON_GREEN}]",
            f"[dim]Version {python_version}[/dim]",
        )

        # Check SurfCastAI
        if SURFCAST_AVAILABLE:
            table.add_row(
                f"[{NEON_CYAN}]SURFCAST AI[/{NEON_CYAN}]",
                f"[{NEON_GREEN}]✅ ONLINE[/{NEON_GREEN}]",
                "[dim]Neural modules loaded[/dim]",
            )
        else:
            table.add_row(
                f"[{NEON_CYAN}]SURFCAST AI[/{NEON_CYAN}]",
                f"[{ERROR_RED}]❌ OFFLINE[/{ERROR_RED}]",
                "[dim]Import error detected[/dim]",
            )

        # Check config
        if self.config:
            table.add_row(
                f"[{NEON_CYAN}]CONFIGURATION[/{NEON_CYAN}]",
                f"[{NEON_GREEN}]✅ LOADED[/{NEON_GREEN}]",
                f"[dim]Model: {self.current_model}[/dim]",
            )
        else:
            table.add_row(
                f"[{NEON_CYAN}]CONFIGURATION[/{NEON_CYAN}]",
                f"[{WARNING_AMBER}]⚠️ MISSING[/{WARNING_AMBER}]",
                "[dim]Config file not found[/dim]",
            )

        # Check directories
        for dir_name, dir_path in [("DATA", "data"), ("OUTPUT", "output"), ("LOGS", "logs")]:
            if Path(dir_path).exists():
                table.add_row(
                    f"[{NEON_CYAN}]{dir_name} STORAGE[/{NEON_CYAN}]",
                    f"[{NEON_GREEN}]✅ MOUNTED[/{NEON_GREEN}]",
                    f"[dim]Path: {dir_path}[/dim]",
                )
            else:
                table.add_row(
                    f"[{NEON_CYAN}]{dir_name} STORAGE[/{NEON_CYAN}]",
                    f"[{WARNING_AMBER}]⚠️ MISSING[/{WARNING_AMBER}]",
                    "[dim]Directory not found[/dim]",
                )

        console.print(table)

        # Recent logs
        console.print(f"\n[{NEON_MAGENTA}]📋 RECENT NEURAL ACTIVITY:[/{NEON_MAGENTA}]")
        log_file = Path("logs/surfcastai.log")
        if log_file.exists():
            try:
                with open(log_file) as f:
                    lines = f.readlines()
                    recent_lines = lines[-10:] if len(lines) > 10 else lines

                    for line in recent_lines:
                        # Color code log levels
                        if "ERROR" in line:
                            console.print(f"[{ERROR_RED}]{line.strip()}[/{ERROR_RED}]")
                        elif "WARNING" in line:
                            console.print(f"[{WARNING_AMBER}]{line.strip()}[/{WARNING_AMBER}]")
                        elif "INFO" in line:
                            console.print(f"[dim]{line.strip()}[/dim]")
                        else:
                            console.print(f"[dim]{line.strip()}[/dim]")
            except Exception as e:
                console.print(f"[{ERROR_RED}]❌ Could not read log file: {e}[/{ERROR_RED}]")
        else:
            console.print(f"[{WARNING_AMBER}]📭 No log file found[/{WARNING_AMBER}]")

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def show_developer_tools(self):
        """Show developer tools menu."""
        console.print(
            Panel(
                f"[{NEON_YELLOW}]🛠️ DEVELOPER TOOLS & DIAGNOSTICS[/{NEON_YELLOW}]",
                title="[yellow]HACKER UTILITIES[/yellow]",
                border_style=NEON_YELLOW,
            )
        )

        tools_menu = [
            ("1", "🧪 Run Tests", "test_forecast_engine.py"),
            ("2", "📊 Benchmarks", "benchmark_forecast_engine.py"),
            ("3", "🎮 Demo Mode", "show_demo.py"),
            ("4", "🔍 Dependency Check", "verify_dependencies.py"),
            ("5", "📈 Performance Analysis", "Custom performance tests"),
            ("6", "🐛 Debug Console", "Interactive Python REPL"),
        ]

        table = Table(box=box.ROUNDED, border_style=NEON_YELLOW)
        table.add_column("CMD", justify="center", style="bold")
        table.add_column("TOOL", style="bold")
        table.add_column("DESCRIPTION")

        for cmd, tool, desc in tools_menu:
            table.add_row(
                f"[{NEON_YELLOW}]{cmd}[/{NEON_YELLOW}]",
                f"[{NEON_GREEN}]{tool}[/{NEON_GREEN}]",
                f"[dim]{desc}[/dim]",
            )

        console.print(table)

        choice = Prompt.ask(
            f"[{NEON_GREEN}]Select tool[/{NEON_GREEN}]",
            choices=["1", "2", "3", "4", "5", "6", "q"],
            default="q",
        )

        if choice == "1":
            self.run_script("test_forecast_engine.py")
        elif choice == "2":
            self.run_script("benchmark_forecast_engine.py")
        elif choice == "3":
            self.run_script("show_demo.py")
        elif choice == "4":
            self.run_script("verify_dependencies.py")
        elif choice == "5":
            self.run_performance_analysis()
        elif choice == "6":
            self.run_debug_console()

    def run_script(self, script_name: str):
        """Run a Python script with cyberpunk interface."""
        script_path = Path(script_name)
        if not script_path.exists():
            console.print(f"[{ERROR_RED}]❌ Script not found: {script_name}[/{ERROR_RED}]")
            return

        console.print(f"[{NEON_CYAN}]🚀 Executing: {script_name}[/{NEON_CYAN}]")
        console.print(
            Panel(
                f"[{NEON_GREEN}]Running in secure neural sandbox...[/{NEON_GREEN}]",
                border_style=NEON_GREEN,
            )
        )

        try:
            # Run script and capture output
            result = subprocess.run(
                [sys.executable, str(script_path)], capture_output=True, text=True, cwd=project_root
            )

            # Display output
            if result.stdout:
                console.print(f"[{NEON_GREEN}]📤 OUTPUT:[/{NEON_GREEN}]")
                console.print(Panel(result.stdout, border_style=NEON_GREEN))

            if result.stderr:
                console.print(f"[{ERROR_RED}]❌ ERRORS:[/{ERROR_RED}]")
                console.print(Panel(result.stderr, border_style=ERROR_RED))

            console.print(
                f"[{NEON_CYAN}]✅ Script completed with exit code: {result.returncode}[/{NEON_CYAN}]"
            )

        except Exception as e:
            console.print(f"[{ERROR_RED}]❌ Execution failed: {str(e)}[/{ERROR_RED}]")

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def run_performance_analysis(self):
        """Run custom performance analysis."""
        console.print(
            Panel(
                f"[{NEON_MAGENTA}]📈 NEURAL PERFORMANCE ANALYSIS[/{NEON_MAGENTA}]",
                title="[magenta]QUANTUM BENCHMARKS[/magenta]",
                border_style=NEON_MAGENTA,
            )
        )

        try:
            # Test import speed
            start_time = time.time()
            import aiohttp
            import numpy
            import openai
            import pandas
            import pydantic

            import_time = time.time() - start_time

            # Test computation speed
            start_time = time.time()
            import numpy as np

            arr = np.random.random((1000, 1000))
            result = np.dot(arr, arr.T)
            numpy_time = time.time() - start_time

            # Test Pydantic speed
            from pydantic import BaseModel

            class TestModel(BaseModel):
                id: int
                name: str
                value: float

            start_time = time.time()
            for i in range(1000):
                TestModel(id=i, name=f"test_{i}", value=i * 0.1)
            pydantic_time = time.time() - start_time

            # Display results
            table = Table(box=box.ROUNDED, border_style=NEON_MAGENTA, title="PERFORMANCE METRICS")
            table.add_column("COMPONENT", style="bold")
            table.add_column("TIME", justify="center")
            table.add_column("RATING", justify="center")

            def get_rating(time_val, thresholds):
                if time_val < thresholds[0]:
                    return f"[{NEON_GREEN}]🚀 EXCELLENT[/{NEON_GREEN}]"
                elif time_val < thresholds[1]:
                    return f"[{NEON_YELLOW}]⚡ GOOD[/{NEON_YELLOW}]"
                else:
                    return f"[{WARNING_AMBER}]⚠️ SLOW[/{WARNING_AMBER}]"

            table.add_row(
                f"[{NEON_CYAN}]MODULE IMPORTS[/{NEON_CYAN}]",
                f"[dim]{import_time:.3f}s[/dim]",
                get_rating(import_time, [0.1, 0.5]),
            )

            table.add_row(
                f"[{NEON_CYAN}]NUMPY COMPUTATION[/{NEON_CYAN}]",
                f"[dim]{numpy_time:.3f}s[/dim]",
                get_rating(numpy_time, [0.1, 0.5]),
            )

            table.add_row(
                f"[{NEON_CYAN}]PYDANTIC MODELS[/{NEON_CYAN}]",
                f"[dim]{pydantic_time:.3f}s[/dim]",
                get_rating(pydantic_time, [0.05, 0.2]),
            )

            console.print(table)

        except Exception as e:
            console.print(f"[{ERROR_RED}]❌ Performance analysis failed: {str(e)}[/{ERROR_RED}]")

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def run_debug_console(self):
        """Run interactive Python console."""
        console.print(
            Panel(
                f"[{NEON_MAGENTA}]🐛 NEURAL DEBUG CONSOLE[/{NEON_MAGENTA}]\n"
                f"[dim]Type 'exit()' or Ctrl+D to return to main interface[/dim]",
                title="[magenta]INTERACTIVE PYTHON SHELL[/magenta]",
                border_style=NEON_MAGENTA,
            )
        )

        # Launch Python REPL
        import code

        vars_dict = {
            "console": console,
            "Path": Path,
            "datetime": datetime,
        }

        # Add SurfCastAI modules if available
        if SURFCAST_AVAILABLE:
            try:
                from src.core import Config, load_config

                vars_dict["Config"] = Config
                vars_dict["load_config"] = load_config
                vars_dict["config"] = self.config
            except ImportError:
                pass

        code.interact(local=vars_dict, banner="🧠 Neural debug console active...")

    def show_help(self):
        """Show help and examples."""
        console.print(
            Panel(
                f"[{NEON_MAGENTA}]📚 NEURAL INTERFACE DOCUMENTATION[/{NEON_MAGENTA}]",
                title="[magenta]HELP & EXAMPLES[/magenta]",
                border_style=NEON_MAGENTA,
            )
        )

        help_sections = [
            (
                "🚀 PIPELINE MODES",
                [
                    "Full Pipeline: Complete data collection → processing → forecast → analysis",
                    "Data Collection: Gather intel from satellites, buoys, weather stations",
                    "Processing: Transform raw data through quantum fusion algorithms",
                    "Forecast: Generate AI-powered surf predictions",
                    "Analysis: Run GPT analysis on existing forecasts",
                ],
            ),
            (
                "🧠 AI MODELS",
                [
                    "gpt-4o: Latest flagship model, fastest and most capable",
                    "gpt-4o-mini: Smaller model for quick analysis",
                    "gpt-4-turbo: Previous generation, still very capable",
                    "Switch models anytime via GPT Model Selector",
                ],
            ),
            (
                "📊 DATA BUNDLES",
                [
                    "Each run creates a timestamped data bundle",
                    "Bundles contain raw data from all sources",
                    "View bundle history and statistics",
                    "Process existing bundles without re-collecting",
                ],
            ),
            (
                "🛠️ DEVELOPER TOOLS",
                [
                    "Run tests to validate system functionality",
                    "Benchmark performance across components",
                    "Demo mode for exploring features",
                    "Debug console for advanced troubleshooting",
                ],
            ),
        ]

        for title, items in help_sections:
            console.print(f"\n[{NEON_CYAN}]{title}[/{NEON_CYAN}]")
            for item in items:
                console.print(f"  • [dim]{item}[/dim]")

        console.print(f"\n[{NEON_GREEN}]💡 PRO TIPS:[/{NEON_GREEN}]")
        console.print("  • [dim]Start with 'Full Pipeline' for complete forecast generation[/dim]")
        console.print(
            "  • [dim]Use 'Forecast Only' mode to generate multiple forecasts from same data[/dim]"
        )
        console.print("  • [dim]Check System Monitoring for real-time status and logs[/dim]")
        console.print("  • [dim]Switch AI models to compare analysis quality[/dim]")

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def show_readme(self):
        """Display README.md and project status."""
        console.print(
            Panel(
                f"[{NEON_CYAN}]📋 PROJECT DOCUMENTATION & STATUS[/{NEON_CYAN}]",
                title="[cyan]NEURAL PROJECT MATRIX[/cyan]",
                border_style=NEON_CYAN,
            )
        )

        readme_path = Path("README.md")
        migration_path = Path("MIGRATION_COMPLETE.md")

        if readme_path.exists():
            console.print(f"[{NEON_GREEN}]📖 README.md found - displaying content:[/{NEON_GREEN}]")
            try:
                with open(readme_path) as f:
                    content = f.read()[:2000]  # First 2000 chars
                    console.print(Panel(content, border_style=NEON_GREEN, title="README.md"))
                    if len(content) >= 2000:
                        console.print("[dim]... (content truncated)[/dim]")
            except Exception as e:
                console.print(f"[{ERROR_RED}]❌ Could not read README.md: {e}[/{ERROR_RED}]")
        else:
            console.print(f"[{WARNING_AMBER}]📭 README.md not found[/{WARNING_AMBER}]")

        if migration_path.exists():
            console.print(f"\n[{NEON_MAGENTA}]📋 Recent migration status:[/{NEON_MAGENTA}]")
            try:
                with open(migration_path) as f:
                    lines = f.readlines()[:20]  # First 20 lines
                    content = "".join(lines)
                    console.print(
                        Panel(content, border_style=NEON_MAGENTA, title="MIGRATION_COMPLETE.md")
                    )
            except Exception as e:
                console.print(f"[{ERROR_RED}]❌ Could not read migration status: {e}[/{ERROR_RED}]")

        console.print(f"\n[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
        input()

    def run_dependency_check(self):
        """Run the dependency verification script."""
        console.print(
            Panel(
                f"[{WARNING_AMBER}]🔍 NEURAL DEPENDENCY ANALYSIS[/{WARNING_AMBER}]",
                title="[yellow]SYSTEM VERIFICATION[/yellow]",
                border_style=WARNING_AMBER,
            )
        )

        self.run_script("verify_dependencies.py")

    async def main_loop(self):
        """Main interface loop."""
        while True:
            self.clear_screen()
            self.show_banner()
            self.show_main_menu()

            choice = self.get_user_choice()

            if choice == "1":
                await self.run_pipeline_mode("full", "COMPLETE NEURAL PIPELINE")
            elif choice == "2":
                await self.run_pipeline_mode("collect", "DATA COLLECTION MATRIX")
            elif choice == "3":
                await self.run_pipeline_mode("process", "QUANTUM DATA PROCESSING")
            elif choice == "4":
                await self.run_pipeline_mode("forecast", "AI FORECAST GENERATION")
            elif choice == "5":
                # Run analysis only
                console.print(
                    Panel(
                        f"[{NEON_ORANGE}]🧠 AI ANALYSIS MODULE[/{NEON_ORANGE}]\n"
                        f"[dim]Running GPT analysis on existing forecasts...[/dim]",
                        title="[orange]NEURAL ANALYSIS[/orange]",
                        border_style=NEON_ORANGE,
                    )
                )
                self.run_script("run_forecast_with_analysis.py")
            elif choice == "6":
                self.select_gpt_model()
            elif choice == "7":
                self.show_bundle_manager()
            elif choice == "8":
                self.show_system_status()
            elif choice == "9":
                self.show_developer_tools()
            elif choice == "A":
                console.print(
                    Panel(
                        f"[{NEON_GREEN}]⚙️ CONFIGURATION MATRIX[/{NEON_GREEN}]\n"
                        f"[dim]Config file: config/config.yaml[/dim]\n"
                        f"[dim]Current model: {self.current_model}[/dim]",
                        title="[green]SYSTEM CONFIG[/green]",
                        border_style=NEON_GREEN,
                    )
                )
                console.print(f"[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
                input()
            elif choice == "B":
                self.show_help()
            elif choice == "C":
                self.show_readme()
            elif choice == "D":
                self.run_dependency_check()
            elif choice == "Q":
                # Exit with style
                console.print(
                    Panel(
                        f"[{NEON_CYAN}]🚪 DISCONNECTING FROM NEURAL INTERFACE...[/{NEON_CYAN}]\n"
                        f"[dim]Thank you for using SurfCastAI[/dim]\n"
                        f"[{NEON_GREEN}]May the waves be with you! 🌊[/{NEON_GREEN}]",
                        title="[cyan]NEURAL LINK TERMINATED[/cyan]",
                        border_style=NEON_CYAN,
                    )
                )
                break
            else:
                console.print(f"[{ERROR_RED}]❌ Invalid command: {choice}[/{ERROR_RED}]")
                console.print(f"[{NEON_CYAN}]Press Enter to continue...[/{NEON_CYAN}]")
                input()


def main():
    """Entry point for the cyberpunk CLI."""
    try:
        cli = SurfCastCLI()
        asyncio.run(cli.main_loop())
    except KeyboardInterrupt:
        console.print(f"\n[{NEON_CYAN}]🚪 Neural interface disconnected by user[/{NEON_CYAN}]")
    except Exception as e:
        console.print(f"\n[{ERROR_RED}]❌ SYSTEM CRITICAL ERROR: {str(e)}[/{ERROR_RED}]")


if __name__ == "__main__":
    main()
