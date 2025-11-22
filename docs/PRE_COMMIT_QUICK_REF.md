# Pre-commit Hooks Quick Reference

## One-Time Setup
```bash
./scripts/setup_pre_commit.sh
```

## What Runs on Commit
1. **black** - Auto-formats code (100 char lines)
2. **ruff** - Auto-fixes linting issues (imports, types, etc.)
3. **mypy** - Type checking (src/ only)
4. **pytest** - Fast unit tests (10s timeout, stops at 3 failures)
5. **Standard checks** - Whitespace, EOF, YAML, large files, merge conflicts

## Common Commands
```bash
# Run all hooks manually
pre-commit run --all-files

# Run specific hook
pre-commit run black
pre-commit run ruff
pre-commit run mypy
pre-commit run pytest-fast

# Update hooks
pre-commit autoupdate

# Skip hooks (emergency only)
git commit --no-verify
```

## Typical Workflow
```bash
# 1. Make changes
vim src/core/new_feature.py

# 2. Try to commit
git add src/core/new_feature.py
git commit -m "Add new feature"

# 3a. If hooks pass
# ✓ Commit succeeds

# 3b. If hooks auto-fix
# Stage the fixes and retry
git add -u
git commit -m "Add new feature"

# 3c. If hooks fail
# Read error message, fix issue, retry
vim src/core/new_feature.py
git add src/core/new_feature.py
git commit -m "Add new feature"
```

## Troubleshooting

### Black reformatted my code
This is expected! Stage the changes and commit:
```bash
git add -u
git commit
```

### Ruff found linting issues
Most are auto-fixed. For remaining issues:
```bash
# See what failed
pre-commit run ruff --all-files

# Fix manually or add exceptions
```

### MyPy type errors
Add type hints or use `# type: ignore`:
```bash
# Example fix
def my_func() -> str:  # Add return type
    return "hello"

# Or suppress
result = my_func()  # type: ignore
```

### Tests are failing
Fix the tests first, then commit:
```bash
# Run tests manually to see full output
pytest tests/unit/ -v

# Fix tests, then retry commit
```

### Pre-commit is slow
First run installs environments (2-3 min). Subsequent runs are fast (<5s).

## Configuration Files
- `.pre-commit-config.yaml` - Hook configuration
- `.ruff.toml` - Linting rules
- `pyproject.toml` - Black, mypy, pytest settings

## Full Documentation
See `docs/PRE_COMMIT_HOOKS.md` for complete guide.
