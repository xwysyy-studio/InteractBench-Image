#!/usr/bin/env python3
"""Materialize one pinned InteractBench task as an OCI build context."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "InteractBench-Image/1.0"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def clone_revision(repository: str, revision: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    run(["git", "init", "--quiet"], cwd=destination)
    run(["git", "remote", "add", "origin", repository], cwd=destination)
    run(["git", "fetch", "--quiet", "--depth", "1", "origin", revision], cwd=destination)
    run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=destination)


def expected_case_names(count_per_mode: int) -> list[str]:
    non_adaptive = [f"{number:03d}.in" for number in range(1, count_per_mode + 1)]
    adaptive = [f"{number:03d}.in" for number in range(101, 101 + count_per_mode)]
    return non_adaptive + adaptive


def write_checksums(artifact_root: Path) -> None:
    checksum_path = artifact_root / "SHA256SUMS"
    files = sorted(
        path
        for path in artifact_root.rglob("*")
        if path.is_file() and path != checksum_path
    )
    lines = [
        f"{sha256_file(path)}  {path.relative_to(artifact_root).as_posix()}"
        for path in files
    ]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def materialize(lock_path: Path, output_root: Path) -> None:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    task_id = lock["task_id"]
    count_per_mode = int(lock["case_count_per_mode"])

    work_root = REPOSITORY_ROOT / ".build"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir()

    upstream = work_root / "interactbench"
    clone_revision(
        lock["interactbench"]["repository"],
        lock["interactbench"]["revision"],
        upstream,
    )

    dataset = lock["dataset"]
    dataset_file = work_root / dataset["file"]
    dataset_url = (
        f"{dataset['repository']}/resolve/{dataset['revision']}/{dataset['file']}"
    )
    download(dataset_url, dataset_file)
    actual_dataset_sha256 = sha256_file(dataset_file)
    if actual_dataset_sha256 != dataset["sha256"]:
        raise RuntimeError(
            "dataset checksum mismatch: "
            f"expected {dataset['sha256']}, got {actual_dataset_sha256}"
        )

    if output_root.exists():
        shutil.rmtree(output_root)
    artifact_root = output_root / "opt" / "interactbench"
    problems_root = artifact_root / "data" / "problems"
    problems_root.mkdir(parents=True)

    run(
        [
            sys.executable,
            str(upstream / "scripts" / "import_from_jsonl.py"),
            "--type",
            "standard",
            "--input",
            str(dataset_file),
            "--output-dir",
            str(problems_root),
            "--problem-ids",
            task_id,
        ],
        cwd=upstream,
    )
    run(
        [
            sys.executable,
            str(upstream / "scripts" / "gen_cases.py"),
            "--root",
            str(problems_root),
            "--problem-ids",
            task_id,
            "--count",
            str(count_per_mode),
            "--clean",
            "--rebuild",
        ],
        cwd=upstream,
    )

    task_root = problems_root / task_id
    for generated_binary in (
        task_root / "generator" / "gen_cases",
        task_root / "generator" / "gen_cases.exe",
    ):
        generated_binary.unlink(missing_ok=True)

    actual_names = sorted(path.name for path in (task_root / "cases").glob("*.in"))
    expected_names = expected_case_names(count_per_mode)
    if actual_names != expected_names:
        raise RuntimeError(
            f"unexpected case set for {task_id}: "
            f"expected {len(expected_names)}, got {len(actual_names)}"
        )
    if len(actual_names) != int(lock["expected_case_count"]):
        raise RuntimeError(f"unexpected case count for {task_id}: {len(actual_names)}")

    shutil.copy2(upstream / "LICENSE", artifact_root / "LICENSE")
    shutil.copytree(
        upstream / "third_party" / "testlib",
        artifact_root / "third_party" / "testlib",
    )

    artifact = {
        "schema": 1,
        "benchmark": "InteractBench",
        "track": "standard",
        "task_id": task_id,
        "asset_root": f"data/problems/{task_id}",
        "case_count": len(actual_names),
        "interactbench_repository": lock["interactbench"]["repository"],
        "interactbench_revision": lock["interactbench"]["revision"],
        "dataset_repository": dataset["repository"],
        "dataset_revision": dataset["revision"],
        "dataset_file_sha256": dataset["sha256"],
    }
    (artifact_root / "artifact.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_checksums(artifact_root)
    print(f"prepared {task_id}: {len(actual_names)} cases at {artifact_root}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lock",
        type=Path,
        default=REPOSITORY_ROOT / "task.lock.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "build" / "rootfs",
    )
    args = parser.parse_args()
    materialize(args.lock.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
