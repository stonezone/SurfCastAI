"""CLI tests for validate-config command."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestValidateConfigCLI(unittest.TestCase):
    def _run_cli(self, cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "src/main.py", *args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_validate_config_exits_nonzero_on_errors(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.yaml"
            config_path.write_text(
                """
general:
  output_directory: ./output
forecast:
  use_local_generator: false
  templates_dir: ./missing_templates
openai:
  model: gpt-5-nano
"""
            )

            result = subprocess.run(
                [sys.executable, "src/main.py", "--config", str(config_path), "validate-config"],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "OPENAI_API_KEY": ""},
            )

            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout + result.stderr).lower()
            self.assertIn("validation", combined)


if __name__ == "__main__":
    unittest.main()
