"""
Generate the raw synthetic patient dataset using Synthea.

Produces five annual batches (2022 to 2026), each with a fixed
population, seed and reference date, documented in the architecture
reference. Each batch is written to its own directory under
data/raw/synthea/ along with a manifest.json recording how it was
generated, which supports lineage and audit requirements later in
the pipeline.

Requires Java 17 or newer and the Synthea jar downloaded separately
into tools/synthea-with-dependencies.jar (see tools/README.md).
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNTHEA_JAR = REPO_ROOT / "tools" / "synthea-with-dependencies.jar"
SYNTHEA_VERSION = "4.0.0"
POPULATION_PER_BATCH = 1000

BATCHES = [
    {"year": 2022, "seed": 2022, "reference_date": "12-31-2022"},
    {"year": 2023, "seed": 2023, "reference_date": "12-31-2023"},
    {"year": 2024, "seed": 2024, "reference_date": "12-31-2024"},
    {"year": 2025, "seed": 2025, "reference_date": "12-31-2025"},
    {"year": 2026, "seed": 2026, "reference_date": "12-31-2026"},
]


def build_config_file(batch_dir: Path) -> Path:
    config_path = batch_dir / "synthea.properties"
    config_path.write_text(
        f"exporter.baseDirectory = {batch_dir / 'fhir'}\n"
        "exporter.fhir.export = true\n"
        "exporter.csv.export = false\n"
    )
    return config_path


def generate_batch(batch: dict) -> None:
    batch_dir = REPO_ROOT / "data" / "raw" / "synthea" / f"batch_{batch['year']}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    config_path = build_config_file(batch_dir)

    command = [
        "java",
        "-jar",
        str(SYNTHEA_JAR),
        "-p",
        str(POPULATION_PER_BATCH),
        "-s",
        str(batch["seed"]),
        "-r",
        batch["reference_date"],
        "-c",
        str(config_path),
    ]

    print(f"Generating batch {batch['year']}...")
    subprocess.run(command, check=True)

    manifest = {
        "batch_id": f"batch_{batch['year']}",
        "source": "synthea",
        "synthea_version": SYNTHEA_VERSION,
        "population_requested": POPULATION_PER_BATCH,
        "seed": batch["seed"],
        "reference_date": batch["reference_date"],
        "module_filter": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Batch {batch['year']} done, manifest written.")


def main() -> None:
    if not SYNTHEA_JAR.exists():
        print(
            f"Synthea jar not found at {SYNTHEA_JAR}. "
            "See tools/README.md for the download step."
        )
        sys.exit(1)

    for batch in BATCHES:
        generate_batch(batch)


if __name__ == "__main__":
    main()