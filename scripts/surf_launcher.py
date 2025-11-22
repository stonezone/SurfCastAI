#!/usr/bin/env python3
"""
🏄 SURFCASTAI LAUNCHER 🏄
Totally Tubular Edition - 1985 Style!

A radical, 80s-themed CLI launcher for the SurfCastAI surf forecasting system.
Because predicting waves should be as gnarly as riding them!
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from colorama import Back, Fore, Style, init

    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

    # Fallback no-op color codes
    class _Fore:
        GREEN = CYAN = YELLOW = RED = MAGENTA = BLUE = WHITE = ""

    class _Style:
        BRIGHT = RESET_ALL = ""

    Fore = _Fore()
    Style = _Style()


# ASCII Art Constants
LOGO = f"""{Fore.CYAN}{Style.BRIGHT}
╔════════════════════════════════════════════════════════════════════╗
║  🏄 SURFCASTAI LAUNCHER 🏄  [Totally Tubular Edition v1.0] 🤙    ║
║                                                                    ║
║       {Fore.BLUE}___    ___    ___    ___                                   {Fore.CYAN}║
║    {Fore.BLUE}__/   \\__/   \\__/   \\__/   \\__     {Fore.YELLOW}Hang Ten with AI!{Fore.CYAN}          ║
║ {Fore.BLUE}___/                            \\___                          {Fore.CYAN}║
║                                                                    ║
║           {Fore.MAGENTA}~ Catching the Perfect Forecast Since 2025 ~{Fore.CYAN}           ║
╚════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

WAVE_SEPARATOR = f"{Fore.BLUE}{'~' * 70}{Style.RESET_ALL}"

SURFBOARD = f"""{Fore.YELLOW}
           /)
      ___(//__
     /         \\
    |  O     O  |
     \\    ^    /
      \\_______/
        |   |
        |   |
       _|   |_
      (_______)
{Style.RESET_ALL}"""

# 80s Slang Dictionary
SLANG = {
    "success": [
        "Totally radical!",
        "Gnarly!",
        "Tubular!",
        "Cowabunga!",
        "Most excellent!",
        "Bodacious!",
        "Righteous!",
        "Awesome sauce!",
        "Rad to the max!",
        "Stellar!",
    ],
    "error": [
        "Bummer, dude!",
        "Bogus!",
        "Weak sauce!",
        "Major wipeout!",
        "Grody to the max!",
        "That's so lame!",
        "Totally uncool!",
        "Barf me out!",
        "Gag me with a spoon!",
    ],
    "thinking": [
        "Hang loose...",
        "Shredding data...",
        "Carving the numbers...",
        "Catching some waves...",
        "Paddling out...",
        "Getting stoked...",
    ],
    "greeting": [
        "Welcome back, dude!",
        "Ready to shred?",
        "Surf's up!",
        "Let's get radical!",
        "Time to catch some waves!",
        "Stoked to see you!",
    ],
}


class SurfLauncher:
    """The most tubular surf forecast launcher ever created!"""

    def __init__(self):
        """Initialize the radical launcher."""
        self.project_root = Path(__file__).parent.parent
        self.config_path = self.project_root / "config" / "config.yaml"
        self.main_script = self.project_root / "src" / "main.py"
        self.config: dict[str, Any] = {}
        self.specialist_enabled = bool(
            self.config.get("forecast", {}).get("use_specialist_team", False)
        )

        # Load config
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from config.yaml."""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    self.config = yaml.safe_load(f) or {}
        except Exception as e:
            self._print_error(f"Error loading config: {e}")

    def _save_config(self) -> None:
        """Save configuration to config.yaml."""
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            self._print_error(f"Error saving config: {e}")

    def _clear_screen(self) -> None:
        """Clear the terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    def _print_success(self, message: str) -> None:
        """Print a success message in green."""
        import random

        slang = random.choice(SLANG["success"])
        print(f"{Fore.GREEN}{Style.BRIGHT}{slang} {message}{Style.RESET_ALL}")

    def _print_error(self, message: str) -> None:
        """Print an error message in red."""
        import random

        slang = random.choice(SLANG["error"])
        print(f"{Fore.RED}{Style.BRIGHT}{slang} {message}{Style.RESET_ALL}")

    def _print_info(self, message: str) -> None:
        """Print an info message in cyan."""
        print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

    def _print_warning(self, message: str) -> None:
        """Print a warning message in yellow."""
        print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")

    def _print_status_bar(self) -> None:
        """Print the current status bar."""
        model = self.config.get("openai", {}).get("model", "gpt-5-nano")
        specialist_status = (
            f"{Fore.GREEN}ON{Fore.CYAN}" if self.specialist_enabled else f"{Fore.RED}OFF{Fore.CYAN}"
        )
        latest_bundle = self._get_latest_bundle_id()

        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print(f"┌{'─' * 68}┐")
        print(
            f"│ Status: Model: {Fore.YELLOW}{model:<15}{Fore.CYAN} │ Specialist Team: {specialist_status}{Fore.CYAN} │ Latest Bundle: {Fore.MAGENTA}{latest_bundle:<10}{Fore.CYAN}│"
        )
        print(f"└{'─' * 68}┘{Style.RESET_ALL}")

    def _get_latest_bundle_id(self) -> str:
        """Get the latest bundle ID."""
        data_dir = self.project_root / "data"
        if not data_dir.exists():
            return "None"

        # Find latest bundle directory
        bundles = [d for d in data_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not bundles:
            return "None"

        latest = max(bundles, key=lambda d: d.stat().st_mtime)
        return latest.name[:10]  # Just first 10 chars

    def _list_bundles(self) -> list[dict[str, Any]]:
        """List all available bundles."""
        data_dir = self.project_root / "data"
        if not data_dir.exists():
            return []

        bundles = []
        for bundle_dir in sorted(data_dir.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True):
            if bundle_dir.is_dir() and not bundle_dir.name.startswith("."):
                metadata_file = bundle_dir / "metadata.json"
                bundles.append(
                    {
                        "id": bundle_dir.name,
                        "path": bundle_dir,
                        "time": datetime.fromtimestamp(bundle_dir.stat().st_mtime),
                        "has_metadata": metadata_file.exists(),
                    }
                )

        return bundles[:10]  # Just show last 10

    def _run_command(self, args: list[str], description: str) -> bool:
        """Run a main.py command."""
        import random

        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{random.choice(SLANG['thinking'])}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Running: {' '.join(args)}{Style.RESET_ALL}\n")

        try:
            result = subprocess.run([sys.executable] + args, cwd=self.project_root, check=False)

            if result.returncode == 0:
                self._print_success(description)
                return True
            else:
                self._print_error(f"{description} (exit code: {result.returncode})")
                return False
        except Exception as e:
            self._print_error(f"Error running command: {e}")
            return False

    def show_main_menu(self) -> None:
        """Display the main menu."""
        self._clear_screen()
        print(LOGO)
        self._print_status_bar()
        print(f"\n{WAVE_SEPARATOR}\n")

        print(f"{Fore.YELLOW}{Style.BRIGHT}MAIN MENU:{Style.RESET_ALL}\n")
        print(
            f"  {Fore.CYAN}1.{Style.RESET_ALL} 🌊 Run Full Forecast (collect + process + forecast)"
        )
        print(f"  {Fore.CYAN}2.{Style.RESET_ALL} 📊 Collect Data Only")
        print(f"  {Fore.CYAN}3.{Style.RESET_ALL} 🤖 Generate Forecast (latest bundle)")
        print(f"  {Fore.CYAN}4.{Style.RESET_ALL} 🔍 Generate Forecast (select bundle)")
        print(f"  {Fore.CYAN}5.{Style.RESET_ALL} ⚙️  Model Settings")
        specialist_label = (
            f"{Fore.GREEN}ON{Style.RESET_ALL}"
            if self.specialist_enabled
            else f"{Fore.RED}OFF{Style.RESET_ALL}"
        )
        print(
            f"  {Fore.CYAN}6.{Style.RESET_ALL} 👥 Toggle Specialist Team (currently: {specialist_label})"
        )
        print(f"  {Fore.CYAN}7.{Style.RESET_ALL} 📁 View Recent Forecasts")
        print(f"  {Fore.CYAN}8.{Style.RESET_ALL} 📋 List Data Bundles")
        print(f"  {Fore.CYAN}9.{Style.RESET_ALL} ❓ Help/Info")
        print(f"  {Fore.CYAN}0.{Style.RESET_ALL} 🚪 Exit (Catch you later!)")

        print(f"\n{WAVE_SEPARATOR}\n")

    def show_model_menu(self) -> None:
        """Display the model settings menu."""
        self._clear_screen()
        current_model = self.config.get("openai", {}).get("model", "gpt-5-nano")

        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                      MODEL SETTINGS MENU                           ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        print(
            f"\n{Fore.YELLOW}Current Model: {Fore.MAGENTA}{Style.BRIGHT}{current_model}{Style.RESET_ALL}\n"
        )

        print(f"{Fore.YELLOW}{Style.BRIGHT}CHOOSE YOUR AI SHREDDING POWER:{Style.RESET_ALL}\n")

        # GPT-5-nano
        check = "✓" if current_model == "gpt-5-nano" else " "
        print(f"  {Fore.CYAN}1.{Style.RESET_ALL} [{Fore.GREEN}{check}{Style.RESET_ALL}] GPT-5-nano")
        print(f"      {Fore.CYAN}└─ Speed:    {Fore.GREEN}★★★★★{Style.RESET_ALL} (Lightning fast!)")
        print(f"      {Fore.CYAN}└─ Cost:     {Fore.GREEN}★★★★★{Style.RESET_ALL} (Super cheap!)")
        print(
            f"      {Fore.CYAN}└─ Quality:  {Fore.YELLOW}★★★☆☆{Style.RESET_ALL} (Good for quick forecasts)"
        )

        # GPT-5-mini
        check = "✓" if current_model == "gpt-5-mini" else " "
        print(
            f"\n  {Fore.CYAN}2.{Style.RESET_ALL} [{Fore.GREEN}{check}{Style.RESET_ALL}] GPT-5-mini"
        )
        print(f"      {Fore.CYAN}└─ Speed:    {Fore.GREEN}★★★★☆{Style.RESET_ALL} (Pretty fast!)")
        print(f"      {Fore.CYAN}└─ Cost:     {Fore.GREEN}★★★★☆{Style.RESET_ALL} (Reasonable)")
        print(
            f"      {Fore.CYAN}└─ Quality:  {Fore.GREEN}★★★★☆{Style.RESET_ALL} (Balanced - recommended!)"
        )

        # GPT-5
        check = "✓" if current_model == "gpt-5" else " "
        print(f"\n  {Fore.CYAN}3.{Style.RESET_ALL} [{Fore.GREEN}{check}{Style.RESET_ALL}] GPT-5")
        print(
            f"      {Fore.CYAN}└─ Speed:    {Fore.YELLOW}★★★☆☆{Style.RESET_ALL} (Slower, but worth it!)"
        )
        print(f"      {Fore.CYAN}└─ Cost:     {Fore.YELLOW}★★☆☆☆{Style.RESET_ALL} (More expensive)")
        print(
            f"      {Fore.CYAN}└─ Quality:  {Fore.GREEN}★★★★★{Style.RESET_ALL} (Maximum accuracy!)"
        )

        print(f"\n  {Fore.CYAN}4.{Style.RESET_ALL} View Full Config")
        print(f"  {Fore.CYAN}b.{Style.RESET_ALL} Back to Main Menu")

        print(f"\n{WAVE_SEPARATOR}\n")

    def show_help(self) -> None:
        """Display help information."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                    🏄 SURFCASTAI HELP CENTER 🏄                    ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        print(f"\n{Fore.YELLOW}{Style.BRIGHT}WHAT EACH OPTION DOES:{Style.RESET_ALL}\n")

        print(f"{Fore.CYAN}1. Run Full Forecast{Style.RESET_ALL}")
        print("   └─ Collects fresh data, processes it, and generates a complete forecast")
        print("   └─ This is your all-in-one, totally radical option!")

        print(f"\n{Fore.CYAN}2. Collect Data Only{Style.RESET_ALL}")
        print("   └─ Just grab the latest buoy, weather, and satellite data")
        print("   └─ Use this if you want to collect data for later")

        print(f"\n{Fore.CYAN}3. Generate Forecast (latest){Style.RESET_ALL}")
        print("   └─ Use the most recent data bundle to create a forecast")
        print("   └─ Perfect when you already collected data")

        print(f"\n{Fore.CYAN}4. Generate Forecast (select){Style.RESET_ALL}")
        print("   └─ Pick a specific data bundle to forecast from")
        print("   └─ Great for comparing forecasts from different times")

        print(f"\n{Fore.YELLOW}{Style.BRIGHT}MODEL COMPARISON:{Style.RESET_ALL}\n")
        print(f"  {Fore.GREEN}GPT-5-nano{Style.RESET_ALL}:  Fast & cheap - good for testing")
        print(f"  {Fore.GREEN}GPT-5-mini{Style.RESET_ALL}:  Balanced - best value (recommended)")
        print(f"  {Fore.GREEN}GPT-5{Style.RESET_ALL}:       Slowest but most accurate")

        print(f"\n{Fore.YELLOW}{Style.BRIGHT}SPECIALIST TEAM:{Style.RESET_ALL}\n")
        print("  When enabled, uses multiple AI agents to analyze different aspects:")
        print("  • Swell Expert - analyzes wave patterns")
        print("  • Wind Specialist - checks wind conditions")
        print("  • Weather Analyst - reviews weather patterns")
        print("  • Tides Guru - evaluates tidal effects")
        print("  → Results in more detailed (but slower) forecasts!")

        print(f"\n{Fore.YELLOW}{Style.BRIGHT}DATA BUNDLES:{Style.RESET_ALL}\n")
        print("  Each data collection creates a 'bundle' - a timestamped collection of:")
        print("  • Buoy observations")
        print("  • Weather forecasts")
        print("  • Satellite imagery")
        print("  • Wave model data")
        print("  → All organized by timestamp for easy tracking!")

        print(f"\n{Fore.YELLOW}{Style.BRIGHT}SURF TIPS FROM THE 80s:{Style.RESET_ALL}\n")
        print("  • Always check North Shore in winter (November-March)")
        print("  • South Shore pumps in summer (May-September)")
        print("  • Dawn patrol = best conditions (offshore winds, glassy water)")
        print("  • When in doubt, paddle out!")
        print("  • Never turn your back on the ocean, dude!")

        print(f"\n{WAVE_SEPARATOR}")
        input(f"\n{Fore.CYAN}Press ENTER to return to main menu...{Style.RESET_ALL}")

    def view_recent_forecasts(self) -> None:
        """Display recent forecast outputs."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                      RECENT FORECASTS                              ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        output_dir = self.project_root / "output"
        if not output_dir.exists():
            self._print_warning("\nNo forecasts found yet, dude! Run a forecast first!")
            input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")
            return

        forecasts = sorted(
            [d for d in output_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )[:10]

        if not forecasts:
            self._print_warning("\nNo forecasts found yet! Time to generate one!")
            input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")
            return

        print(f"\n{Fore.YELLOW}Here are your most recent forecasts:{Style.RESET_ALL}\n")

        for i, forecast_dir in enumerate(forecasts, 1):
            timestamp = datetime.fromtimestamp(forecast_dir.stat().st_mtime)
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")

            # Check for output files
            has_md = (forecast_dir / "forecast.md").exists()
            has_html = (forecast_dir / "forecast.html").exists()
            has_pdf = (forecast_dir / "forecast.pdf").exists()

            formats = []
            if has_md:
                formats.append("MD")
            if has_html:
                formats.append("HTML")
            if has_pdf:
                formats.append("PDF")

            format_str = ", ".join(formats) if formats else "No outputs"

            print(f"  {Fore.CYAN}{i}.{Style.RESET_ALL} {forecast_dir.name}")
            print(
                f"     {Fore.CYAN}└─{Style.RESET_ALL} {time_str} | Formats: {Fore.GREEN}{format_str}{Style.RESET_ALL}"
            )

        print(f"\n{Fore.CYAN}Forecast outputs are in: {Fore.YELLOW}{output_dir}{Style.RESET_ALL}")
        print(f"\n{WAVE_SEPARATOR}")
        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def list_bundles(self) -> None:
        """Display list of data bundles."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                      DATA BUNDLES                                  ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        bundles = self._list_bundles()

        if not bundles:
            self._print_warning("\nNo data bundles found! Collect some data first!")
            input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")
            return

        print(f"\n{Fore.YELLOW}Available bundles (newest first):{Style.RESET_ALL}\n")

        for i, bundle in enumerate(bundles, 1):
            time_str = bundle["time"].strftime("%Y-%m-%d %H:%M")
            status = (
                f"{Fore.GREEN}✓{Style.RESET_ALL}"
                if bundle["has_metadata"]
                else f"{Fore.YELLOW}?{Style.RESET_ALL}"
            )

            print(f"  {Fore.CYAN}{i}.{Style.RESET_ALL} {status} {bundle['id'][:36]}...")
            print(f"     {Fore.CYAN}└─{Style.RESET_ALL} {time_str}")

        print(f"\n{WAVE_SEPARATOR}")
        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def select_bundle(self) -> str | None:
        """Let user select a bundle."""
        bundles = self._list_bundles()

        if not bundles:
            self._print_warning("\nNo bundles available!")
            return None

        print(f"\n{Fore.YELLOW}Select a bundle:{Style.RESET_ALL}\n")

        for i, bundle in enumerate(bundles, 1):
            time_str = bundle["time"].strftime("%Y-%m-%d %H:%M")
            print(f"  {Fore.CYAN}{i}.{Style.RESET_ALL} {bundle['id'][:36]}... ({time_str})")

        print(f"  {Fore.CYAN}0.{Style.RESET_ALL} Cancel")

        while True:
            choice = input(f"\n{Fore.CYAN}Enter number:{Style.RESET_ALL} ").strip()

            if choice == "0":
                return None

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(bundles):
                    return bundles[idx]["id"]
                else:
                    self._print_error("Invalid selection, try again!")
            except ValueError:
                self._print_error("Enter a number, dude!")

    def set_model(self, model: str) -> None:
        """Set the OpenAI model in config."""
        if "openai" not in self.config:
            self.config["openai"] = {}

        self.config["openai"]["model"] = model
        self._save_config()
        self._print_success(f"Model set to {model}!")

    def view_config(self) -> None:
        """Display current configuration."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                    CURRENT CONFIGURATION                           ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        print(f"\n{Fore.YELLOW}OpenAI Settings:{Style.RESET_ALL}")
        print(
            f"  Model: {Fore.GREEN}{self.config.get('openai', {}).get('model', 'gpt-5-nano')}{Style.RESET_ALL}"
        )

        api_key = self.config.get("openai", {}).get("api_key") or os.getenv("OPENAI_API_KEY")
        if api_key:
            print(f"  API Key: {Fore.GREEN}✓ Configured{Style.RESET_ALL}")
        else:
            print(f"  API Key: {Fore.RED}✗ Not configured{Style.RESET_ALL}")

        print(f"\n{Fore.YELLOW}Directories:{Style.RESET_ALL}")
        print(
            f"  Data: {Fore.CYAN}{self.config.get('general', {}).get('data_directory', './data')}{Style.RESET_ALL}"
        )
        print(
            f"  Output: {Fore.CYAN}{self.config.get('general', {}).get('output_directory', './output')}{Style.RESET_ALL}"
        )

        print(f"\n{Fore.YELLOW}Data Sources:{Style.RESET_ALL}")
        sources = self.config.get("data_sources", {})
        for source, config in sources.items():
            enabled = config.get("enabled", False)
            status = (
                f"{Fore.GREEN}ON{Style.RESET_ALL}" if enabled else f"{Fore.RED}OFF{Style.RESET_ALL}"
            )
            url_count = len(config.get("urls", []))
            print(f"  {source}: {status} ({url_count} URLs)")

        print(f"\n{WAVE_SEPARATOR}")
        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def run_full_forecast(self) -> None:
        """Run the complete forecast pipeline."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                      FULL FORECAST RUN                             ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        print(f"\n{Fore.YELLOW}This will:{Style.RESET_ALL}")
        print("  • Collect fresh data from all sources")
        print("  • Process and analyze the data")
        print("  • Generate a complete surf forecast")
        print("  • Create output files (Markdown + HTML)")

        confirm = input(f"\n{Fore.CYAN}Ready to shred? (y/n):{Style.RESET_ALL} ").strip().lower()

        if confirm != "y":
            self._print_info("Forecast cancelled. Catch you later!")
            return

        self._run_command(
            [str(self.main_script), "run", "--mode", "full"], "Full forecast completed!"
        )

        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def collect_data_only(self) -> None:
        """Collect data without generating forecast."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                      DATA COLLECTION                               ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        print(f"\n{Fore.YELLOW}Collecting data from all sources...{Style.RESET_ALL}")

        self._run_command(
            [str(self.main_script), "run", "--mode", "collect"], "Data collection complete!"
        )

        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def generate_forecast_latest(self) -> None:
        """Generate forecast from latest bundle."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                  FORECAST FROM LATEST BUNDLE                       ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        latest = self._get_latest_bundle_id()
        print(f"\n{Fore.YELLOW}Using bundle: {Fore.CYAN}{latest}{Style.RESET_ALL}")

        self._run_command(
            [str(self.main_script), "run", "--mode", "forecast"], "Forecast generation complete!"
        )

        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def generate_forecast_select(self) -> None:
        """Generate forecast from selected bundle."""
        self._clear_screen()
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                  FORECAST FROM SELECTED BUNDLE                     ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)

        bundle_id = self.select_bundle()

        if not bundle_id:
            self._print_info("Cancelled.")
            return

        print(f"\n{Fore.YELLOW}Using bundle: {Fore.CYAN}{bundle_id}{Style.RESET_ALL}")

        self._run_command(
            [str(self.main_script), "run", "--mode", "forecast", "--bundle", bundle_id],
            "Forecast generation complete!",
        )

        input(f"\n{Fore.CYAN}Press ENTER to continue...{Style.RESET_ALL}")

    def handle_main_menu(self, choice: str) -> bool:
        """Handle main menu selection. Returns False to exit."""
        if choice == "1":
            self.run_full_forecast()
        elif choice == "2":
            self.collect_data_only()
        elif choice == "3":
            self.generate_forecast_latest()
        elif choice == "4":
            self.generate_forecast_select()
        elif choice == "5":
            self.model_settings_menu()
        elif choice == "6":
            self.specialist_enabled = not self.specialist_enabled
            if "forecast" not in self.config:
                self.config["forecast"] = {}
            self.config["forecast"]["use_specialist_team"] = self.specialist_enabled
            self._save_config()
            status = "enabled" if self.specialist_enabled else "disabled"
            self._print_success(f"Specialist team {status}!")
        elif choice == "7":
            self.view_recent_forecasts()
        elif choice == "8":
            self.list_bundles()
        elif choice == "9":
            self.show_help()
        elif choice == "0":
            return False
        else:
            self._print_error("Invalid choice! Pick a number from the menu.")

        return True

    def model_settings_menu(self) -> None:
        """Model settings submenu."""
        while True:
            self.show_model_menu()
            choice = input(f"{Fore.CYAN}Enter your choice:{Style.RESET_ALL} ").strip()

            if choice == "1":
                self.set_model("gpt-5-nano")
            elif choice == "2":
                self.set_model("gpt-5-mini")
            elif choice == "3":
                self.set_model("gpt-5")
            elif choice == "4":
                self.view_config()
            elif choice.lower() == "b":
                break
            else:
                self._print_error("Invalid choice!")

    def run(self) -> None:
        """Main run loop."""
        import random

        # Welcome message
        self._clear_screen()
        print(LOGO)
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{random.choice(SLANG['greeting'])}{Style.RESET_ALL}")
        print(SURFBOARD)
        input(f"\n{Fore.CYAN}Press ENTER to enter the main menu...{Style.RESET_ALL}")

        # Main loop
        while True:
            self.show_main_menu()
            choice = input(f"{Fore.CYAN}Enter your choice:{Style.RESET_ALL} ").strip()

            if not self.handle_main_menu(choice):
                break

        # Goodbye message
        self._clear_screen()
        print(f"\n{Fore.CYAN}{Style.BRIGHT}")
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║                    CATCH YOU ON THE NEXT WAVE!                     ║")
        print("║                                                                    ║")
        print("║                  Thanks for using SurfCastAI! 🏄                  ║")
        print("║                                                                    ║")
        print("║           Stay stoked, keep shredding, and hang loose! 🤙        ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print(Style.RESET_ALL)
        print(f"\n{Fore.YELLOW}  ~ Cowabunga, dude! ~{Style.RESET_ALL}\n")


def main():
    """Entry point."""
    try:
        launcher = SurfLauncher()
        launcher.run()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Whoa! Ctrl+C detected! Later, dude! 🏄{Style.RESET_ALL}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Bummer! Unexpected error: {e}{Style.RESET_ALL}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
