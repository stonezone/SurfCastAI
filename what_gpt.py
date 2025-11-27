#!/usr/bin/env python3
"""
List GPT* models available to the current OpenAI API key.

Requirements:
    pip install --upgrade openai
Environment:
    OPENAI_API_KEY must be set.
"""

import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print(
        "Error: The 'openai' package is not installed.\n"
        "Install it with: pip install --upgrade openai",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(
            "Error: OPENAI_API_KEY environment variable is not set.\n"
            "Export it before running this script, for example:\n"
            "  export OPENAI_API_KEY='sk-...'",
            file=sys.stderr,
        )
        sys.exit(1)

    # The client also reads OPENAI_API_KEY from the environment,
    # but we pass it explicitly for clarity.
    client = OpenAI(api_key=api_key)

    try:
        response = client.models.list()
    except Exception as exc:
        print(f"Error: Failed to list models: {exc}", file=sys.stderr)
        sys.exit(1)

    # response.data is an iterable of model objects; each has an `id`.  [oai_citation:2‡OpenAI Platform](https://platform.openai.com/docs/api-reference/models/list?utm_source=chatgpt.com)
    gpt_models = []

    for model in getattr(response, "data", []):
        model_id = getattr(model, "id", "")
        if isinstance(model_id, str) and "gpt" in model_id.lower():
            gpt_models.append(model_id)

    if not gpt_models:
        print("No GPT* models are visible for this API key.")
        return

    print("GPT models available to your API key:\n")
    for model_id in sorted(gpt_models):
        print(f" - {model_id}")


if __name__ == "__main__":
    main()
