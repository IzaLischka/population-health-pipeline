"""
Smoke test: validate a sample of the raw Synthea FHIR bundles against
the fhir.resources library, before committing to it as the structural
validation layer for the bronze schema validator.

Synthea exports FHIR R4 (4.0.1). fhir.resources 8.x treats R5 as its
default resource set and folds R4 support into an R4B (4.3.0)
compatibility sub-package rather than keeping a strictly separate R4
4.0.1 package (see the discussion linked from the architecture
reference). The two releases are close but not identical, so this
gets verified against real data instead of assumed.

Usage:
    python scripts/smoke_test_fhir_resources.py \
        --source-dir data/raw/synthea/fhir --sample-size 30
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from fhir.resources.R4B.bundle import Bundle
from pydantic import ValidationError


def sample_files(source_dir: Path, sample_size: int, seed: int) -> list[Path]:
    all_files = sorted(source_dir.glob("*.json"))
    if not all_files:
        print(f"No .json files found under {source_dir}.")
        sys.exit(1)
    random.Random(seed).shuffle(all_files)
    return all_files[:sample_size]


def validate_bundle(path: Path) -> tuple[bool, str | None, Counter]:
    resource_type_counts: Counter = Counter()
    raw_text = path.read_text(encoding="utf-8")
    raw_json = json.loads(raw_text)
    for entry in raw_json.get("entry", []):
        resource = entry.get("resource", {})
        resource_type_counts[resource.get("resourceType", "unknown")] += 1

    try:
        Bundle.model_validate_json(raw_text)
        return True, None, resource_type_counts
    except ValidationError as error:
        return False, str(error), resource_type_counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    files = sample_files(args.source_dir, args.sample_size, args.seed)

    passed = 0
    failed = 0
    resource_type_totals: Counter = Counter()
    failures: list[tuple[Path, str]] = []

    for path in files:
        ok, error, resource_type_counts = validate_bundle(path)
        resource_type_totals.update(resource_type_counts)
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((path, error))

    print(f"Validated {len(files)} bundles: {passed} passed, {failed} failed.\n")

    print("Resource types encountered across the sample:")
    for resource_type, count in resource_type_totals.most_common():
        print(f"  {resource_type}: {count}")

    if failures:
        print("\nFailures:")
        for path, error in failures:
            print(f"\n--- {path.name} ---")
            print(error)
        sys.exit(1)

    print("\nAll sampled bundles validated cleanly against fhir.resources R4B.")


if __name__ == "__main__":
    main()
