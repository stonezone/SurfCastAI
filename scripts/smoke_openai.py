"""Minimal OpenAI smoke test for gpt-5-nano."""

from __future__ import annotations

import argparse
import sys

from openai import OpenAI


def run_smoke(model: str, max_output_tokens: int | None) -> int:
    client = OpenAI()
    try:
        request = {
            "model": model,
            "input": "Say hi in one sentence.",
        }
        if max_output_tokens is not None:
            request["max_output_tokens"] = max_output_tokens

        response = client.responses.create(**request)
    except Exception as exc:  # pragma: no cover - runtime smoke only
        print(f"ERROR: {exc}")
        return 1

    text = getattr(response, "output_text", None)
    if not text:
        try:
            chunks = []
            for item in getattr(response, "output", []):
                item_type = getattr(item, "type", "")
                if item_type == "output_text":
                    chunks.append(getattr(item, "text", ""))
                    continue

                content = getattr(item, "content", None)
                if not content:
                    continue

                for block in content:
                    if getattr(block, "type", "") == "output_text":
                        chunks.append(getattr(block, "text", ""))
            text = "".join(chunks)
        except Exception:  # pragma: no cover - fallback for unexpected shapes
            text = None

    if text:
        print(text.strip())
        return 0

    print("ERROR: Response did not include text output")
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a quick OpenAI smoke test")
    parser.add_argument("--model", default="gpt-5-nano", help="Model to invoke")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional completion token budget for the assistant output",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return run_smoke(args.model, args.max_tokens)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
