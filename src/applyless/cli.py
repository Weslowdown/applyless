from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from . import __version__
from .scoring import score_batch


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _print_result(result: dict) -> None:
    jobs = result["jobs"]
    print(f"\nApplyLess - {len(jobs)} roles ranked on resume evidence\n")
    for job in jobs:
        print(f"#{job['rank']}  {job['score']:>2}/100  {job['label']}")
        print(f"     {job['title']} @ {job['company']}")
        print(f"     {job['summary']}")
        if job["matched"]:
            top = ", ".join(item["skill"] for item in job["matched"][:4])
            print(f"     Evidence: {top}")
        if job["missing_must"]:
            print(f"     Must-have gaps: {', '.join(job['missing_must'][:5])}")
        if job["red_flags"]:
            print(f"     Check: {', '.join(flag['label'] for flag in job['red_flags'])}")
        print()
    print("Processed locally. Nothing was uploaded.\n")


def _sample_text(name: str) -> str:
    return files("applyless").joinpath("data", name).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="applyless",
        description="Rank job descriptions by evidence from your resume.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    score = subparsers.add_parser("score", help="Score one or more job descriptions.")
    score.add_argument("--resume", required=True, help="Resume text file, or - for stdin.")
    score.add_argument("--jobs", required=True, help="Job descriptions file, or - for stdin.")
    score.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    serve = subparsers.add_parser("serve", help="Open the local web interface.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="Open a browser automatically.")

    subparsers.add_parser("demo", help="Print the bundled fictional demo.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in {None, "demo"}:
        if args.command == "demo":
            print(_sample_text("sample_jobs.txt"))
            return 0
        parser.print_help()
        return 0

    if args.command == "score":
        try:
            result = score_batch(_read_text(args.resume), _read_text(args.jobs))
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_result(result)
        return 0

    if args.command == "serve":
        from .web import serve

        serve(host=args.host, port=args.port, open_browser=args.open)
        return 0
    return 1

