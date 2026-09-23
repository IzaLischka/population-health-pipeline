"""
Document the provenance of a manually-ingested raw dataset.

This project's raw patient data is a one-time manual download of a
pre-generated Synthea sample set (see data/raw/synthea/SOURCE.md),
not an automated pull via API/SFTP/streaming like the other
portfolio projects use. "Manual" must not mean "untracked": this
script walks the already-extracted files, fingerprints every one of
them, and writes two artifacts that make the raw layer auditable:

- manifest.json: one record of what was ingested, from where, when,
  and how many/how large the files are. This is the file lineage and
  quality tooling downstream (bronze layer, dbt tests, etc.) can
  point back to as the source of truth for "what raw data does this
  pipeline claim to be built from".
- checksums.sha256: a standard sha256sum-format file, one line per
  ingested file, so a corrupted or silently-replaced raw file is
  detectable later (re-run this script with --verify to check).

Usage:
    python scripts/document_raw_source.py \\
        --source-dir data/raw/synthea \\
        --source-url https://synthea.mitre.org/downloads \\
        --source-name "Synthea 1K Sample Synthetic Patient Records (FHIR R4)"

    # Later, to confirm nothing in the raw folder has drifted:
    python scripts/document_raw_source.py --source-dir data/raw/synthea --verify
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

MANIFEST_FILENAME = "manifest.json"
CHECKSUMS_FILENAME = "checksums.sha256"
CHUNK_SIZE_BYTES = 1024 * 1024

# Files this script itself writes; never fingerprint its own output,
# or a re-run would fold yesterday's manifest into today's checksum list.
GENERATED_FILENAMES = {MANIFEST_FILENAME, CHECKSUMS_FILENAME}


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_files(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.name not in GENERATED_FILENAMES
    )


def write_checksums(source_dir: Path, files: list[Path]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    lines = []
    for path in files:
        digest = sha256_of_file(path)
        relative_path = path.relative_to(source_dir).as_posix()
        checksums[relative_path] = digest
        lines.append(f"{digest}  {relative_path}")
    (source_dir / CHECKSUMS_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums


def write_manifest(
    source_dir: Path,
    source_url: str,
    source_name: str,
    downloaded_at: str,
    checksums: dict[str, str],
) -> None:
    total_size_bytes = sum(
        (source_dir / relative_path).stat().st_size for relative_path in checksums
    )
    manifest = {
        "dataset": "raw_synthea_patient_records",
        "source_name": source_name,
        "source_url": source_url,
        "ingestion_method": "manual_download",
        "ingestion_note": (
            "One-time manual download and extraction of a pre-generated "
            "Synthea sample set, chosen over local generation because of a "
            "known Synthea failure mode where certain seeds put a "
            "simulated patient into a runaway aging loop. Other portfolio "
            "projects demonstrate API/SFTP/streaming ingestion instead; "
            "this repo's raw layer is documented here rather than "
            "automated because that isn't this project's point of "
            "emphasis."
        ),
        "downloaded_at": downloaded_at,
        "documented_at": datetime.now(UTC).isoformat(),
        "file_count": len(checksums),
        "total_size_bytes": total_size_bytes,
        "checksum_algorithm": "sha256",
        "checksums_file": CHECKSUMS_FILENAME,
    }
    (source_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def verify(source_dir: Path) -> int:
    checksums_path = source_dir / CHECKSUMS_FILENAME
    if not checksums_path.exists():
        print(f"No {CHECKSUMS_FILENAME} found in {source_dir}. Nothing to verify against.")
        return 1

    expected: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative_path = line.split("  ", 1)
        expected[relative_path] = digest

    actual_files = {
        path.relative_to(source_dir).as_posix(): path for path in discover_files(source_dir)
    }

    missing = sorted(set(expected) - set(actual_files))
    unexpected = sorted(set(actual_files) - set(expected))
    mismatched = sorted(
        relative_path
        for relative_path, digest in expected.items()
        if relative_path in actual_files and sha256_of_file(actual_files[relative_path]) != digest
    )

    if not missing and not unexpected and not mismatched:
        print(f"OK: {len(expected)} files match {CHECKSUMS_FILENAME}.")
        return 0

    if missing:
        print(f"Missing files (listed in checksums but not on disk): {missing}")
    if unexpected:
        print(f"Unexpected files (on disk but not in checksums): {unexpected}")
    if mismatched:
        print(f"Checksum mismatch (file content changed since documenting): {mismatched}")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--source-url")
    parser.add_argument("--source-name")
    parser.add_argument(
        "--downloaded-at",
        help="ISO date/time the file was downloaded, e.g. 2026-09-15. Defaults to now if omitted.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check the existing checksums.sha256 against what's on disk "
        "instead of writing a new manifest.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir.resolve()

    if not source_dir.is_dir():
        print(f"{source_dir} is not a directory.")
        sys.exit(1)

    if args.verify:
        sys.exit(verify(source_dir))

    if not args.source_url or not args.source_name:
        print("--source-url and --source-name are required unless --verify is passed.")
        sys.exit(1)

    files = discover_files(source_dir)
    if not files:
        print(f"No files found under {source_dir}. Did you extract the dataset there?")
        sys.exit(1)

    downloaded_at = args.downloaded_at or datetime.now(UTC).isoformat()
    checksums = write_checksums(source_dir, files)
    write_manifest(source_dir, args.source_url, args.source_name, downloaded_at, checksums)

    print(f"Documented {len(files)} files under {source_dir}.")
    print(f"Wrote {MANIFEST_FILENAME} and {CHECKSUMS_FILENAME}.")


if __name__ == "__main__":
    main()
