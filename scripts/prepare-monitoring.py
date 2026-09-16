#!/usr/bin/env python3
"""Append Lume monitoring to the current shared Prometheus configuration."""

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def integrate(base: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    jobs = result.setdefault("scrape_configs", [])
    existing = {job.get("job_name") for job in jobs}
    additions = fragment.get("scrape_configs", [])
    duplicates = existing & {job.get("job_name") for job in additions}
    if duplicates:
        names = ", ".join(sorted(str(name) for name in duplicates))
        raise ValueError(f"scrape job already exists: {names}")
    jobs.extend(copy.deepcopy(additions))

    rules = result.setdefault("rule_files", [])
    for rule_file in fragment.get("rule_files", []):
        if rule_file not in rules:
            rules.append(rule_file)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("source and output must differ")

    raw = args.source.read_bytes()
    base = json.loads(raw)
    fragment_path = Path(__file__).resolve().parents[1] / "deploy/monitoring/scrape.json"
    result = integrate(base, json.loads(fragment_path.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, delete=False) as temp:
        temp.write(json.dumps(result, indent=2) + "\n")
        temporary = Path(temp.name)
    temporary.chmod(args.source.stat().st_mode & 0o777)
    os.replace(temporary, args.output)
    args.output.with_suffix(".source.sha256").write_text(
        hashlib.sha256(raw).hexdigest() + "\n", encoding="utf-8"
    )
    print("Generated Lume integration; validate before deployment.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot prepare monitoring config: {error}") from None
