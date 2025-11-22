# Pre-commit Hooks

Automated code quality checks that run before each commit.

## Setup (One-time)

```bash
./scripts/setup_pre_commit.sh
```

Or manually:
```bash
pip install pre-commit
pre-commit install
```

## What Gets Checked

### Code Quality Tools
- **black**: Code formatting (100 char line length)
- **ruff**: Linting (errors, warnings, imports, naming conventions)
- **mypy**: Type checking (src/ directory only)
- **pytest**: Fast unit tests (10s timeout per test, stops after 3 failures)

### Standard Checks
- Trailing whitespace removal
- End-of-file fixer
- YAML syntax validation
- Large file detection (>1MB)
- Merge conflict detection
- Debug statement detection

## Usage

### Automatic (on commit)
Hooks run automatically when you `git commit`. If any hook fails, the commit is blocked.

```bash
$ git commit -m "Add feature"
black....................................................................Passed
ruff.....................................................................Passed
mypy.....................................................................Passed
pytest-fast..............................................................Passed
trailing-whitespace......................................................Passed
# ... other checks ...
[master abc123] Add feature
```

### Manual (on-demand)
```bash
# Run all hooks on all files
pre-commit run --all-files

# Run all hooks on staged files only
pre-commit run

# Run specific hook
pre-commit run black --all-files
pre-commit run mypy --all-files
pre-commit run ruff --all-files
pre-commit run pytest-fast --all-files

# Update hook versions
pre-commit autoupdate
```

### Skip Hooks (Emergency)
```bash
# Skip all hooks for this commit
git commit --no-verify -m "Emergency fix"

# NOT RECOMMENDED: Only for emergencies (production down, critical hotfix)
```

## Configuration Files

### `.pre-commit-config.yaml`
Main configuration for pre-commit hooks. Specifies which hooks to run and their versions.

### `.ruff.toml`
Ruff linter configuration. Controls which rules to check and ignore.

### `pyproject.toml`
Python project configuration. Contains settings for black, mypy, and pytest.

## Troubleshooting

### Hook fails with formatting errors
```bash
# Black or ruff will auto-fix most issues
pre-commit run --all-files

# Stage the fixes and retry
git add -u
git commit
```

### MyPy type checking errors
```bash
# Run mypy manually to see full output
pre-commit run mypy --all-files

# Common fixes:
# - Add type hints to function signatures
# - Add # type: ignore comments for unavoidable issues
# - Update mypy config in pyproject.toml if needed
```

### Pytest failures
```bash
# Run tests manually to see full output
pytest tests/unit/ -v

# Fix failing tests, then retry commit
git commit
```

### Slow pre-commit
```bash
# Pre-commit caches environments, so first run is slow
# Subsequent runs are much faster

# Clean cache if needed
pre-commit clean

# Skip slow tests during commit (run separately)
# Modify pytest-fast args in .pre-commit-config.yaml
```

### Update hooks
```bash
# Update to latest hook versions
pre-commit autoupdate

# Review changes
git diff .pre-commit-config.yaml

# Commit updated config
git add .pre-commit-config.yaml
git commit -m "chore: update pre-commit hooks"
```

### Uninstall hooks
```bash
# Remove pre-commit hooks
pre-commit uninstall

# Hooks in .pre-commit-config.yaml remain for other developers
```

## Best Practices

### DO
- Run `pre-commit run --all-files` before pushing
- Fix issues immediately (don't accumulate)
- Update hooks regularly with `pre-commit autoupdate`
- Add `# type: ignore` comments with justification
- Use `--no-verify` only for emergencies

### DON'T
- Commit broken code with `--no-verify`
- Ignore linting errors without understanding them
- Skip tests that are actually failing
- Disable hooks without team discussion

## Integration with CI/CD

Pre-commit hooks are a first line of defense. CI/CD should run the same checks:

```yaml
# .github/workflows/ci.yml example
- name: Run pre-commit
  run: |
    pip install pre-commit
    pre-commit run --all-files
```

## Hook Details

### Black (Code Formatter)
- Line length: 100 characters
- Target: Python 3.10
- Automatically formats code to PEP 8 standards
- No configuration needed, just run and commit

### Ruff (Linter)
- Checks: pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, flake8-bugbear
- Auto-fixes: Import sorting, style issues
- Ignores: Line length (handled by black), some bugbear rules
- Fast: Written in Rust, 10-100x faster than flake8

### MyPy (Type Checker)
- Checks: src/ directory only (not tests/)
- Mode: Lenient (--ignore-missing-imports, --no-strict-optional)
- Catches: Type errors, mismatched signatures, None-related bugs
- Recommended: Add type hints incrementally

### Pytest (Test Runner)
- Scope: tests/unit/ directory only
- Timeout: 10 seconds per test
- Stops: After 3 failures or first error
- Fast: Integration tests run separately in CI

## Examples

### Successful commit
```bash
$ git add src/core/new_feature.py
$ git commit -m "Add new feature"

black....................................................................Passed
ruff.....................................................................Passed
mypy.....................................................................Passed
pytest-fast..............................................................Passed
trailing-whitespace......................................................Passed
end-of-file-fixer........................................................Passed
check-yaml...............................................................Passed
check-added-large-files..................................................Passed
check-merge-conflict.....................................................Passed
debug-statements.........................................................Passed

[master abc123] Add new feature
 1 file changed, 50 insertions(+)
```

### Failed commit (auto-fixed)
```bash
$ git add src/core/new_feature.py
$ git commit -m "Add new feature"

black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted src/core/new_feature.py
1 file reformatted.

$ git add src/core/new_feature.py  # Stage auto-fixes
$ git commit -m "Add new feature"

black....................................................................Passed
# ... other checks pass ...
[master abc123] Add new feature
```

### Failed commit (manual fix required)
```bash
$ git commit -m "Add new feature"

mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

src/core/new_feature.py:42: error: Incompatible return value type (got "None", expected "str")

# Fix the error in your editor, then retry
$ git add src/core/new_feature.py
$ git commit -m "Add new feature"
```

## Support

For issues or questions:
1. Check this documentation
2. Run hooks manually to see full output
3. Check .pre-commit-config.yaml for configuration
4. Search pre-commit documentation: https://pre-commit.com/
