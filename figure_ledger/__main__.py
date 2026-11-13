"""CLI: python -m figure_ledger transcripts/*.jsonl"""

from __future__ import annotations

import sys
from pathlib import Path

from figure_ledger.score import format_details, format_table, score_path

_FLAGS = {"--verbose", "--help", "-h"}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    unknown = [arg for arg in args if arg.startswith("-") and arg not in _FLAGS]
    if unknown:
        print(f"unknown flag: {unknown[0]}", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    if "--help" in args or "-h" in args:
        print(_usage())
        return 0
    paths = [arg for arg in args if arg not in _FLAGS]
    if not paths:
        print(_usage(), file=sys.stderr)
        return 2
    verbose = "--verbose" in args
    try:
        reports = [score_path(Path(path)) for path in paths]
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(format_table(reports))
    if verbose:
        print()
        print(format_details(reports))
    return 0


def _usage() -> str:
    return (
        "usage: python -m figure_ledger [--verbose] <transcript.jsonl>...\n"
        "\n"
        "Score each figure in an assistant reply against tool output above that reply.\n"
        "\n"
        "sourced    the same value is in an earlier tool result\n"
        "mismatch   an earlier tool result has a different value of the same kind\n"
        "orphan     no earlier tool result has that kind of figure\n"
        "\n"
        "The report does not edit the file."
    )


if __name__ == "__main__":
    raise SystemExit(main())
