#!/bin/bash
# Setup pre-commit hooks for SurfCastAI

set -e

echo "================================"
echo "SurfCastAI Pre-commit Setup"
echo "================================"
echo ""

# Check if in virtualenv
if [ -z "$VIRTUAL_ENV" ]; then
    echo "WARNING: Not in a virtual environment!"
    echo "Consider activating your venv first."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Installing pre-commit..."
pip install pre-commit

echo ""
echo "Installing pre-commit hooks..."
pre-commit install

echo ""
echo "Running pre-commit on all files (initial check)..."
echo "This may take a few minutes on first run..."
echo ""
pre-commit run --all-files || true

echo ""
echo "================================"
echo "✓ Pre-commit hooks installed!"
echo "================================"
echo ""
echo "Hooks will now run automatically before each commit."
echo ""
echo "Useful commands:"
echo "  pre-commit run --all-files     # Run all hooks manually"
echo "  pre-commit run black           # Run specific hook"
echo "  pre-commit autoupdate          # Update hook versions"
echo "  git commit --no-verify         # Skip hooks (emergency only)"
echo ""
echo "See docs/PRE_COMMIT_HOOKS.md for more information."
