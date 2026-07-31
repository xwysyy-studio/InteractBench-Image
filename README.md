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

`artifact.json` records the task ID, its interactor mode, the case count and
every pinned revision. Consumers choose their own runner, compiler, isolation
mechanism, case selection, and result interpretation. The image has no custom
entrypoint.

## Case numbering

Case files are named by the upstream generator contract, which numbers
non-adaptive cases from 1 and adaptive cases from 101. A task's `interactor_mode`
in `meta.json` therefore decides which numbers exist:

| `interactor_mode` | Case files | Generator invocation |
|---|---|---|
| `non_adaptive` | `001.in` to `100.in` | seeds 1 to 100, `-mode=non` |
| `adaptive` | `101.in` to `200.in` | seeds 1 to 100, `-mode=adp` |
| `both` | `001.in` to `200.in` | `non` takes seeds 1 to 100, `adp` takes seeds 101 to 200 |

An `adaptive` task has no `001.in`, and a `non_adaptive` task has no `101.in`.
Both carry 100 cases; only `both` carries 200. The numbering gap between the two
ranges is what keeps the modes separable, so `case_count_per_mode` cannot exceed
100 without the ranges colliding.

## Reproducibility

[`task.lock.json`](task.lock.json) pins the InteractBench source revision, the
Hugging Face dataset revision and the per-mode case count. For each task the
publishing workflow verifies the dataset checksum, materializes the task from the
pinned revision, generates the complete case pool, checks the produced file names
against the set the task's interactor mode implies, builds the image, pushes it,
and then reads `SHA256SUMS` back inside the published image.

Tasks are published one at a time. The workflow accepts an explicit problem ID
list, a cap on how many tasks one run publishes, and a switch that skips tasks
whose immutable tag already exists, so the full dataset can be published across
several unhurried runs.

The InteractBench source and dataset are distributed under MIT. The bundled
testlib header carries its own MIT license under
`/opt/interactbench/third_party/testlib/LICENSE`.
