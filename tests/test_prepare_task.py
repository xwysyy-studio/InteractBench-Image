from __future__ import annotations

import importlib.util
import json
import tempfile
import textwrap
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_task.py"
SPEC = importlib.util.spec_from_file_location("prepare_task", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
prepare_task = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_task)


class MaterializeTaskTests(unittest.TestCase):
    def test_keeps_successful_cases_when_one_seed_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "upstream"
            staging = root / "staging"
            output = root / "output"
            task = staging / "problem_1"

            (upstream / "scripts").mkdir(parents=True)
            (upstream / "third_party" / "testlib").mkdir(parents=True)
            (upstream / "LICENSE").write_text("license\n", encoding="utf-8")
            (upstream / "third_party" / "testlib" / "testlib.h").write_text(
                "", encoding="utf-8"
            )
            (upstream / "scripts" / "gen_cases.py").write_text(
                textwrap.dedent(
                    """
                    import pathlib
                    import sys

                    root = pathlib.Path(sys.argv[sys.argv.index("--root") + 1])
                    task_id = sys.argv[sys.argv.index("--problem-ids") + 1]
                    cases = root / task_id / "cases"
                    cases.mkdir(parents=True, exist_ok=True)
                    (cases / "001.in").write_text("seed=1 mode=-mode=non\\n")
                    (cases / "002.in").write_text("")
                    (cases / "003.in").write_text("seed=3 mode=-mode=non\\n")
                    raise SystemExit(1)
                    """
                ),
                encoding="utf-8",
            )

            (task / "generator").mkdir(parents=True)
            (task / "cases").mkdir()
            (task / "meta.json").write_text(
                json.dumps({"interactor_mode": "non_adaptive"}), encoding="utf-8"
            )
            (task / "generator" / "gen_cases.cpp").write_text(
                textwrap.dedent(
                    """
                    #include <cstdlib>
                    #include <iostream>

                    int main(int argc, char **argv) {
                        int seed = std::atoi(argv[1]);
                        if (seed == 2) return 3;
                        std::cout << "seed=" << seed << " mode=" << argv[2] << "\\n";
                        return 0;
                    }
                    """
                ),
                encoding="utf-8",
            )

            lock = {
                "case_count_per_mode": 3,
                "interactbench": {"repository": "upstream", "revision": "source-rev"},
                "dataset": {
                    "repository": "dataset",
                    "revision": "dataset-rev",
                    "sha256": "a" * 64,
                },
            }

            artifact = prepare_task.materialize_task(
                task_id="problem_1",
                lock=lock,
                lock_sha256="b" * 64,
                upstream=upstream,
                staging_root=staging,
                output_root=output,
            )

            artifact_root = output / "problem_1" / "rootfs" / "opt" / "interactbench"
            cases = artifact_root / "data" / "problems" / "problem_1" / "cases"
            self.assertEqual(artifact["case_count"], 2)
            self.assertEqual(
                sorted(path.name for path in cases.glob("*.in")),
                ["001.in", "003.in"],
            )
            self.assertEqual(
                (cases / "003.in").read_text(encoding="utf-8"),
                "seed=3 mode=-mode=non\n",
            )
            self.assertFalse((cases / "002.in").exists())


if __name__ == "__main__":
    unittest.main()
