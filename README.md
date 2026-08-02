# InteractBench task images

This repository publishes tool-independent OCI images containing immutable
InteractBench task assets. Every task in the pinned dataset gets its own image.
The images do not include a judge runner, sandbox adapter, model output, or
evaluation policy.

An image tag is the InteractBench problem ID, unchanged:

```bash
docker pull ghcr.io/xwysyy-studio/interactbench-task:cf1486_c1
```

Each task carries a plain problem ID tag and a generation-stamped tag. Problem
IDs never contain a hyphen, so filtering the hyphenated ones out leaves exactly
the catalog of published tasks:

```bash
gh api --paginate \
  /orgs/xwysyy-studio/packages/container/interactbench-task/versions \
  --jq '.[].metadata.container.tags[] | select(test("-") | not)'
```

`--paginate` matters: the endpoint returns 30 versions per page, and the full
catalog runs to several pages.

Alongside the plain problem ID, each build also publishes
`<problem-id>-<lock-digest>`, where the suffix is the first eight hex characters
of the SHA-256 of [`task.lock.json`](task.lock.json). That suffix changes
whenever any pinned input changes, so it identifies the exact asset generation.
Resolve either tag to a digest and evaluate against the digest.

## Image contents

```text
/opt/interactbench/
├── LICENSE
├── SHA256SUMS
├── artifact.json
├── third_party/testlib/
└── data/problems/<problem-id>/
    ├── desc.md
    ├── meta.json
    ├── cases/
    ├── generator/gen_cases.cpp
    └── interactor/
```

`artifact.json` records the task ID, its interactor mode, the number of cases
that were generated successfully, the configured numbering capacity, and every
pinned revision. Consumers choose their own runner, compiler, isolation
mechanism, case selection, and result interpretation. The image has no custom
entrypoint.

## Case numbering

Case files are named by the upstream generator contract, which numbers
non-adaptive cases from 1 and adaptive cases from 101. A task's `interactor_mode`
in `meta.json` therefore decides which numbers exist:

| `interactor_mode` | Legal case numbers | Generator invocation |
|---|---|---|
| `non_adaptive` | `001.in` to `100.in` | seeds 1 to 100, `-mode=non` |
| `adaptive` | `101.in` to `200.in` | seeds 1 to 100, `-mode=adp` |
| `both` | `001.in` to `200.in` | `non` takes seeds 1 to 100, `adp` takes seeds 101 to 200 |

The `adp` seed ranges intentionally differ between `adaptive` and `both`; they
match the released dataset, and regeneration reproduces the published case
files byte for byte.

An `adaptive` task has no `001.in`, and a `non_adaptive` task has no `101.in`.
The publisher attempts every configured seed independently. If a generator
fails deterministically for one seed, that numbered file is absent while later
seeds are still attempted; numbers are never shifted or filled from another
seed. At least one case must succeed. `case_count_per_mode` records the capacity
of each numbering range, while `case_count` records the number of case files
actually present. The numbering gap between the two ranges keeps the modes
separable, so `case_count_per_mode` cannot exceed 100 without the ranges
colliding.

## Reproducibility

[`task.lock.json`](task.lock.json) pins the InteractBench source revision, the
Hugging Face dataset revision and the per-mode case count. For each task the
publishing workflow verifies the dataset checksum, materializes the task from the
pinned revision, compiles the task generator, attempts every configured seed,
and builds an image from the successful outputs in their original numbered
positions. A compile failure or a task with no successful case fails
preparation. The workflow then runs the image and reads `SHA256SUMS` back from
inside it, and only pushes once that check passes, so an image that fails its own
integrity check never reaches the registry.

Tasks are published one at a time. The workflow accepts an explicit problem ID
list, a cap on how many tasks one run publishes, and a switch that skips a task
only when both of its tags already exist and resolve to the same digest, so the
full dataset can be published across several unhurried runs and a task left
half-pushed by an interrupted run is picked up again rather than skipped.

The InteractBench source and dataset are distributed under MIT. The bundled
testlib header carries its own MIT license under
`/opt/interactbench/third_party/testlib/LICENSE`.
