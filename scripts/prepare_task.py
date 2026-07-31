#!/usr/bin/env python3
"""Materialize pinned InteractBench tasks as per-task OCI build contexts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# scripts/gen_cases.py numbers non-adaptive cases from 1 and adaptive cases
# from 101. A batch larger than the offset would make the two ranges overlap
# and silently overwrite cases.
ADAPTIVE_CASE_OFFSET = 100


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    """Fetch a pinned artifact, retrying only transient transport failures.

    Publishing 298 tasks means 298 fetches; a single rate-limit response must
    not be reported as a broken task.
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "InteractBench-Image/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
            return
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            last_error = error
        except urllib.error.URLError as error:
            last_error = error
        if attempt < 2:
            time.sleep(5 * 2**attempt)
    raise RuntimeError(f"download failed after 3 attempts: {url}: {last_error}")


def clone_revision(repository: str, revision: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    run(["git", "init", "--quiet"], cwd=destination)
    run(["git", "remote", "add", "origin", repository], cwd=destination)
    run(["git", "fetch", "--quiet", "--depth", "1", "origin", revision], cwd=destination)
    run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=destination)


def expected_case_names(interactor_mode: str, count_per_mode: int) -> list[str]:
    """Case names the upstream generator produces for one interactor mode.

    Mirrors scripts/gen_cases.py: ``non`` batches occupy 1..count and ``adp``
    batches occupy 101..100+count, both zero padded to the same width.
    """
    width = max(3, len(str(count_per_mode)))
    non_adaptive = [f"{number:0{width}d}.in" for number in range(1, count_per_mode + 1)]
    adaptive = [
        f"{number:0{width}d}.in"
        for number in range(
            ADAPTIVE_CASE_OFFSET + 1,
            ADAPTIVE_CASE_OFFSET + 1 + count_per_mode,
        )
    ]
    if interactor_mode == "adaptive":
        return adaptive
    if interactor_mode == "both":
        return sorted(non_adaptive + adaptive)
    return non_adaptive


def read_interactor_mode(task_root: Path) -> str:
    meta = json.loads((task_root / "meta.json").read_text(encoding="utf-8"))
    mode = meta.get("interactor_mode")
    if mode not in {"non_adaptive", "adaptive", "both"}:
        raise RuntimeError(f"unsupported interactor_mode {mode!r} in {task_root}")
    return mode


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


def all_problem_ids(dataset_file: Path) -> list[str]:
    ids = []
    with dataset_file.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                ids.append(json.loads(line)["problem_id"])
    return sorted(ids)


def fetch_dataset(lock: dict, work_root: Path) -> Path:
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
    return dataset_file


def materialize_task(
    *,
    task_id: str,
    lock: dict,
    lock_sha256: str,
    upstream: Path,
    staging_root: Path,
    output_root: Path,
) -> dict:
    count_per_mode = int(lock["case_count_per_mode"])
    task_root = staging_root / task_id
    interactor_mode = read_interactor_mode(task_root)

    run(
        [
            sys.executable,
            str(upstream / "scripts" / "gen_cases.py"),
            "--root",
            str(staging_root),
            "--problem-ids",
            task_id,
            "--count",
            str(count_per_mode),
            "--clean",
            "--rebuild",
        ],
        cwd=upstream,
    )

    for generated_binary in (
        task_root / "generator" / "gen_cases",
        task_root / "generator" / "gen_cases.exe",
    ):
        generated_binary.unlink(missing_ok=True)

    actual_names = sorted(path.name for path in (task_root / "cases").glob("*.in"))
    expected_names = expected_case_names(interactor_mode, count_per_mode)
    if actual_names != expected_names:
        missing = sorted(set(expected_names) - set(actual_names))
        unexpected = sorted(set(actual_names) - set(expected_names))
        raise RuntimeError(
            f"case set mismatch for {task_id} ({interactor_mode}): "
            f"expected {len(expected_names)}, got {len(actual_names)}, "
            f"missing {missing[:5]}, unexpected {unexpected[:5]}"
        )

    task_output = output_root / task_id
    if task_output.exists():
        shutil.rmtree(task_output)
    artifact_root = task_output / "rootfs" / "opt" / "interactbench"
    problems_root = artifact_root / "data" / "problems"
    problems_root.mkdir(parents=True)
    shutil.move(str(task_root), str(problems_root / task_id))

    shutil.copy2(upstream / "LICENSE", artifact_root / "LICENSE")
    shutil.copytree(
        upstream / "third_party" / "testlib",
        artifact_root / "third_party" / "testlib",
    )

    dataset = lock["dataset"]
    artifact = {
        "schema": 2,
        "benchmark": "InteractBench",
        "track": "standard",
        "task_id": task_id,
        "asset_root": f"data/problems/{task_id}",
        "interactor_mode": interactor_mode,
        "case_count": len(actual_names),
        "case_count_per_mode": count_per_mode,
        "lock_sha256": lock_sha256,
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
    print(
        f"prepared {task_id}: {interactor_mode}, {len(actual_names)} cases "
        f"at {task_output}",
        flush=True,
    )
    return artifact


def materialize(
    lock_path: Path,
    output_root: Path,
    problem_ids: list[str] | None,
) -> int:
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes.decode("utf-8"))
    lock_sha256 = hashlib.sha256(lock_bytes).hexdigest()
    count_per_mode = int(lock["case_count_per_mode"])
    if not 1 <= count_per_mode <= ADAPTIVE_CASE_OFFSET:
        raise RuntimeError(
            f"case_count_per_mode must be within 1..{ADAPTIVE_CASE_OFFSET}, "
            f"got {count_per_mode}"
        )

    work_root = REPOSITORY_ROOT / ".build"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir()

    dataset_file = fetch_dataset(lock, work_root)
    upstream = work_root / "interactbench"
    clone_revision(
        lock["interactbench"]["repository"],
        lock["interactbench"]["revision"],
        upstream,
    )
    known_ids = all_problem_ids(dataset_file)
    if problem_ids:
        unknown = sorted(set(problem_ids) - set(known_ids))
        if unknown:
            raise RuntimeError(f"unknown problem ids: {unknown}")
        selected = sorted(set(problem_ids))
    else:
        selected = known_ids

    staging_root = work_root / "problems"
    import_command = [
        sys.executable,
        str(upstream / "scripts" / "import_from_jsonl.py"),
        "--type",
        "standard",
        "--input",
        str(dataset_file),
        "--output-dir",
        str(staging_root),
        "--problem-ids",
        *selected,
    ]
    run(import_command, cwd=upstream)

    output_root.mkdir(parents=True, exist_ok=True)
    prepared: list[dict] = []
    failed: list[dict] = []
    for index, task_id in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {task_id}", flush=True)
        try:
            prepared.append(
                materialize_task(
                    task_id=task_id,
                    lock=lock,
                    lock_sha256=lock_sha256,
                    upstream=upstream,
                    staging_root=staging_root,
                    output_root=output_root,
                )
            )
        except Exception as exc:
            failed.append({"task_id": task_id, "error": str(exc)})
            print(f"[FAIL] {task_id}: {exc}", file=sys.stderr, flush=True)

    manifest = {
        "schema": 1,
        "lock_sha256": lock_sha256,
        "case_count_per_mode": count_per_mode,
        "requested": len(selected),
        "prepared": prepared,
        "failed": failed,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"prepared {len(prepared)}/{len(selected)} tasks, failed {len(failed)}",
        flush=True,
    )
    return 1 if failed else 0


def list_tasks(lock_path: Path) -> int:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    work_root = REPOSITORY_ROOT / ".build"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir()
    try:
        for task_id in all_problem_ids(fetch_dataset(lock, work_root)):
            print(task_id)
    finally:
        shutil.rmtree(work_root)
    return 0


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
        default=REPOSITORY_ROOT / "build",
    )
    parser.add_argument(
        "--problem-ids",
        nargs="*",
        default=None,
        help="Prepare specific problem IDs (default: every task in the dataset)",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="Print every task ID in the pinned dataset and exit",
    )
    args = parser.parse_args()
    if args.list_tasks:
        return list_tasks(args.lock.resolve())
    return materialize(
        args.lock.resolve(),
        args.output.resolve(),
        args.problem_ids,
    )


if __name__ == "__main__":
    raise SystemExit(main())
