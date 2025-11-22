# Python Environment Setup

This project now ships with a resilient bootstrap flow that avoids the brittle
`python3` shims configured in the host shell (for example, when `conda init` is
enabled in `~/.bash_profile`).  The key points:

* `setup.sh` honours an optional `PYTHON` environment variable.  Point it at an
  explicit interpreter (for example,
  `/opt/homebrew/Caskroom/miniforge/base/bin/python3`) when the default
  `python3` shim is slow or interactive.
* If `ensurepip` is disabled in the interpreter that created the virtual
  environment, the script now falls back to unpacking the bundled pip wheel
  directly into `venv/`.  That keeps the install self-contained without relying
  on shell tricks.
* All dependency installation is routed through the freshly created virtual
  environment, so subsequent tooling (pytest, CLI scripts, etc.) should be
  launched via `venv/bin/python` or `source venv/bin/activate` to ensure the
  correct interpreter is in use.

Usage example:

```bash
# Pick a stable interpreter
export PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3

# Bootstrap the environment
./setup.sh --force

# Activate and verify
source venv/bin/activate
python -m pip list | head
```

If your shell profile automatically activates `conda` (or another environment
manager) for login shells, it is strongly recommended to run project commands
via the absolute interpreter (`venv/bin/python …`) to avoid the extra shell
initialisation overhead.
