#!/usr/bin/env python3
"""
SurfCastAI Dependency Verification Script
Automatically verifies dependency versions and compatibility
Enhanced version for migration monitoring
"""

import importlib
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

# Expected versions (from our verification)
EXPECTED_VERSIONS = {
    "openai": "1.84.0",
    "aiohttp": "3.12.11",
    "pydantic": "2.11.5",
    "numpy": "2.3.0",
    "pandas": "2.3.0",
    "httpx": "0.28.0",
    "pytest": "8.3.2",
    "rich": "13.8.1",
    "pillow": "11.0.0",
    "weasyprint": "62.3",
    "markdown": "3.7",
    "beautifulsoup4": "4.12.3",
    "pyyaml": "6.0.2",
    "python-dotenv": "1.0.1",
    "typing_extensions": "4.12.2",
    "colorama": "0.4.6",
    "pytz": "2024.1",
    "aiofiles": "24.1.0",
}

CRITICAL_PACKAGES = ["openai", "aiohttp", "pydantic", "numpy"]


class Colors:
    """Terminal colors for output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}\n")


def print_status(package: str, current: str, expected: str, status: str):
    """Print package status with colors."""
    color_map = {
        "CRITICAL": Colors.RED,
        "OUTDATED": Colors.YELLOW,
        "CURRENT": Colors.GREEN,
        "NEWER": Colors.BLUE,
        "UNKNOWN": Colors.PURPLE,
    }

    color = color_map.get(status, Colors.WHITE)
    print(f"{package:20} {current:15} → {expected:15} {color}[{status}]{Colors.ENDC}")


def get_package_version(package_name: str) -> str:
    """Get the currently installed version of a package."""
    try:
        # Handle special cases
        if package_name == "pillow":
            from PIL import Image

            module = Image
        else:
            module = importlib.import_module(package_name)

        version = getattr(module, "__version__", "Unknown")
        return version
    except ImportError:
        return "Not Installed"
    except Exception:
        return "Error"


def compare_versions(current: str, expected: str) -> str:
    """Compare version strings and return status."""
    if current in ["Not Installed", "Error", "Unknown"]:
        return "CRITICAL"

    try:
        # Clean version strings (remove post/dev/rc suffixes)
        def clean_version(v):
            import re

            return re.split(r"[+-]", v)[0]

        current_clean = clean_version(current)
        expected_clean = clean_version(expected)

        # Simple version comparison (works for most packages)
        current_parts = [int(x) for x in current_clean.split(".")]
        expected_parts = [int(x) for x in expected_clean.split(".")]

        # Pad shorter version with zeros
        max_len = max(len(current_parts), len(expected_parts))
        current_parts += [0] * (max_len - len(current_parts))
        expected_parts += [0] * (max_len - len(expected_parts))

        if current_parts < expected_parts:
            if current_parts[0] < expected_parts[0]:  # Major version behind
                return "CRITICAL"
            else:
                return "OUTDATED"
        elif current_parts == expected_parts:
            return "CURRENT"
        else:
            return "NEWER"
    except Exception:
        return "UNKNOWN"


def check_openai_model_usage():
    """Check for deprecated OpenAI model usage."""
    print_header("OpenAI Model Usage Check")

    deprecated_models = ["gpt-4-1106-preview", "gpt-3.5-turbo-1106", "gpt-4-0613"]
    recommended_models = ["gpt-4o", "gpt-4o-2024-08-06", "gpt-4o-mini"]
    issues_found = []
    good_usage = []

    # Search for model usage in Python files
    python_files = list(Path(".").rglob("*.py"))
    yaml_files = list(Path(".").rglob("*.yaml")) + list(Path(".").rglob("*.yml"))

    for file_path in python_files + yaml_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

                # Check for deprecated models
                for model in deprecated_models:
                    if model in content:
                        issues_found.append((file_path, model, "deprecated"))

                # Check for recommended models
                for model in recommended_models:
                    if model in content:
                        good_usage.append((file_path, model))

        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")

    if issues_found:
        print(f"{Colors.RED}❌ Deprecated model usage found:{Colors.ENDC}")
        for file_path, model, issue_type in issues_found:
            print(f"  {file_path}: {model}")
        print(
            f"\n{Colors.YELLOW}Recommendation: Update to 'gpt-4o' or 'gpt-4o-2024-08-06'{Colors.ENDC}"
        )
    else:
        print(f"{Colors.GREEN}✅ No deprecated model usage found{Colors.ENDC}")

    if good_usage:
        print(f"\n{Colors.GREEN}✅ Current model usage found:{Colors.ENDC}")
        for file_path, model in good_usage:
            print(f"  {file_path}: {model}")


def check_import_compatibility():
    """Test critical imports for compatibility."""
    print_header("Import Compatibility Check")

    tests = [
        ("openai", "from openai import AsyncOpenAI"),
        ("aiohttp", "import aiohttp"),
        ("pydantic", "from pydantic import BaseModel"),
        ("numpy", "import numpy as np"),
        ("pandas", "import pandas as pd"),
        ("httpx", "import httpx"),
        ("rich", "import rich"),
        ("pytest", "import pytest"),
        ("PIL", "from PIL import Image"),
        ("yaml", "import yaml"),
        ("markdown", "import markdown"),
        ("bs4", "from bs4 import BeautifulSoup"),
        ("dotenv", "import dotenv"),
        ("colorama", "import colorama"),
    ]

    for package, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"{Colors.GREEN}✅ {package:20} import successful{Colors.ENDC}")
        except ImportError as e:
            print(f"{Colors.RED}❌ {package:20} import failed: {e}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  {package:20} import warning: {e}{Colors.ENDC}")


def check_numpy_compatibility():
    """Check NumPy 2.x specific compatibility."""
    print_header("NumPy 2.x Compatibility Check")

    try:
        import numpy as np

        version = tuple(map(int, np.__version__.split(".")[:2]))

        if version >= (2, 0):
            print(f"{Colors.GREEN}✅ NumPy 2.x detected ({np.__version__}){Colors.ENDC}")

            # Test free-threaded support
            try:
                if hasattr(sys, "_is_gil_enabled"):
                    gil_status = "disabled" if not sys._is_gil_enabled() else "enabled"
                    print(f"   GIL status: {gil_status}")
                else:
                    print("   Free-threaded Python not available")
            except:
                print("   Could not determine GIL status")

            # Test for deprecated functionality
            print("   Testing deprecated functionality...")

            # Test array creation (common breaking change area)
            try:
                arr = np.array([1, 2, 3], dtype=np.int32)
                print(f"   ✅ Array creation: {arr.dtype}")
            except Exception as e:
                print(f"   ❌ Array creation issue: {e}")

        else:
            print(
                f"{Colors.YELLOW}⚠️  NumPy 1.x detected ({np.__version__}) - consider upgrading{Colors.ENDC}"
            )

    except ImportError:
        print(f"{Colors.RED}❌ NumPy not installed{Colors.ENDC}")


def check_openai_api():
    """Test OpenAI API compatibility."""
    print_header("OpenAI API Compatibility Check")

    try:
        from openai import AsyncOpenAI

        print(f"{Colors.GREEN}✅ AsyncOpenAI import successful{Colors.ENDC}")

        # Check if API key is available
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            print(f"{Colors.GREEN}✅ API key found in environment{Colors.ENDC}")

            # Test client creation
            try:
                client = AsyncOpenAI(api_key=api_key)
                print(f"{Colors.GREEN}✅ Client creation successful{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️  Client creation warning: {e}{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}⚠️  No OPENAI_API_KEY found in environment{Colors.ENDC}")

    except ImportError as e:
        print(f"{Colors.RED}❌ OpenAI import failed: {e}{Colors.ENDC}")


def performance_benchmark():
    """Run basic performance benchmarks."""
    print_header("Performance Benchmark")

    try:
        import time
        from typing import Optional

        from pydantic import BaseModel

        class TestModel(BaseModel):
            id: int
            name: str
            value: float | None = None

        # Benchmark model creation
        start_time = time.time()
        for i in range(1000):
            TestModel(id=i, name=f"test_{i}", value=i * 0.1)
        creation_time = time.time() - start_time

        print(f"Pydantic model creation (1000 instances): {creation_time:.3f}s")

        if creation_time < 0.05:
            print(f"{Colors.GREEN}✅ Excellent performance (likely Pydantic 2.11+){Colors.ENDC}")
        elif creation_time < 0.1:
            print(f"{Colors.GREEN}✅ Good performance{Colors.ENDC}")
        elif creation_time < 0.5:
            print(f"{Colors.YELLOW}⚠️  Acceptable performance{Colors.ENDC}")
        else:
            print(f"{Colors.RED}❌ Slow performance - check Pydantic version{Colors.ENDC}")

        # Test numpy performance (if available)
        try:
            import numpy as np

            start_time = time.time()
            arr = np.random.random((1000, 1000))
            result = np.dot(arr, arr.T)
            numpy_time = time.time() - start_time
            print(f"NumPy matrix multiplication (1000x1000): {numpy_time:.3f}s")

            if numpy_time < 0.1:
                print(f"{Colors.GREEN}✅ Excellent NumPy performance{Colors.ENDC}")
            elif numpy_time < 0.5:
                print(f"{Colors.GREEN}✅ Good NumPy performance{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}⚠️  Acceptable NumPy performance{Colors.ENDC}")

        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  NumPy benchmark failed: {e}{Colors.ENDC}")

    except Exception as e:
        print(f"{Colors.RED}❌ Benchmark failed: {e}{Colors.ENDC}")


def generate_upgrade_commands():
    """Generate pip upgrade commands for outdated packages."""
    print_header("Upgrade Commands")

    outdated_packages = []

    for package, expected_version in EXPECTED_VERSIONS.items():
        current_version = get_package_version(package)
        status = compare_versions(current_version, expected_version)

        if status in ["CRITICAL", "OUTDATED"]:
            outdated_packages.append((package, expected_version, status))

    if outdated_packages:
        print("Run these commands to upgrade outdated packages:\n")

        # Critical updates first
        critical = [p for p in outdated_packages if p[2] == "CRITICAL"]
        if critical:
            print(f"{Colors.RED}# CRITICAL UPDATES (run first):{Colors.ENDC}")
            for package, version, _ in critical:
                print(f"pip install {package}=={version}")
            print()

        # Other updates
        others = [p for p in outdated_packages if p[2] != "CRITICAL"]
        if others:
            print(f"{Colors.YELLOW}# OTHER UPDATES:{Colors.ENDC}")
            for package, version, _ in others:
                print(f"pip install {package}=={version}")
            print()

        # All at once command (excluding critical for safety)
        print(f"{Colors.BLUE}# OR upgrade non-critical packages all at once:{Colors.ENDC}")
        if others:
            other_packages = " ".join([f"{p}=={v}" for p, v, _ in others])
            print(f"pip install {other_packages}")

        print(f"\n{Colors.PURPLE}# COMPLETE UPGRADE (all packages):{Colors.ENDC}")
        all_packages = " ".join([f"{p}=={v}" for p, v, _ in outdated_packages])
        print(f"pip install {all_packages}")

    else:
        print(f"{Colors.GREEN}✅ All packages are up to date!{Colors.ENDC}")


def check_requirements_file():
    """Check if requirements.txt matches expected versions."""
    print_header("Requirements File Check")

    req_file = Path("requirements.txt")
    if not req_file.exists():
        print(f"{Colors.RED}❌ requirements.txt not found{Colors.ENDC}")
        return

    with open(req_file) as f:
        content = f.read()

    print("Checking requirements.txt against expected versions...")

    mismatches = []
    for package, expected_version in EXPECTED_VERSIONS.items():
        if f"{package}==" in content:
            # Extract version from requirements.txt
            import re

            pattern = rf"{package}==([^\s\n#]+)"
            match = re.search(pattern, content)
            if match:
                req_version = match.group(1)
                if req_version != expected_version:
                    mismatches.append((package, req_version, expected_version))
                else:
                    print(f"{Colors.GREEN}✅ {package:20} {req_version}{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}⚠️  {package:20} version not found{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}⚠️  {package:20} not in requirements.txt{Colors.ENDC}")

    if mismatches:
        print(f"\n{Colors.YELLOW}Version mismatches found:{Colors.ENDC}")
        for package, req_version, expected_version in mismatches:
            print(f"  {package}: {req_version} → {expected_version}")


def main():
    """Main verification function."""
    print_header("SurfCastAI Dependency Verification")

    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Working directory: {os.getcwd()}")

    # Check package versions
    print_header("Package Version Check")
    print(f"{'Package':<20} {'Current':<15} {'Expected':<15} Status")
    print("-" * 70)

    critical_issues = 0

    for package, expected_version in EXPECTED_VERSIONS.items():
        current_version = get_package_version(package)
        status = compare_versions(current_version, expected_version)
        print_status(package, current_version, expected_version, status)

        if status == "CRITICAL" and package in CRITICAL_PACKAGES:
            critical_issues += 1

    # Run additional checks
    check_requirements_file()
    check_openai_model_usage()
    check_import_compatibility()
    check_numpy_compatibility()
    check_openai_api()
    performance_benchmark()
    generate_upgrade_commands()

    # Final summary
    print_header("Migration Status Summary")

    if critical_issues > 0:
        print(f"{Colors.RED}❌ {critical_issues} critical package(s) need updating{Colors.ENDC}")
        print(f"{Colors.RED}   Priority: Update OpenAI and NumPy first{Colors.ENDC}")
        return 1
    else:
        print(f"{Colors.GREEN}✅ No critical issues found{Colors.ENDC}")
        print(f"{Colors.GREEN}   Your dependencies are ready for migration!{Colors.ENDC}")

        # Check if we're fully migrated
        all_current = True
        for package, expected_version in EXPECTED_VERSIONS.items():
            current_version = get_package_version(package)
            status = compare_versions(current_version, expected_version)
            if status not in ["CURRENT", "NEWER"]:
                all_current = False
                break

        if all_current:
            print(f"{Colors.GREEN}🎉 MIGRATION COMPLETE! All packages are up to date.{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}📝 Some packages still need updating (see above){Colors.ENDC}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
