# InteractBench task images

This repository publishes tool-independent OCI images containing immutable
InteractBench task assets. The images do not include a judge runner, sandbox
adapter, model output, or evaluation policy.

The first published task is `cf1486_c1`:

```bash
docker pull ghcr.io/xwysyy-studio/interactbench-task:cf1486-c1
```

Use the digest emitted by the publishing workflow for reproducible evaluation.

## Image contents

```text
/opt/interactbench/
├── LICENSE
├── SHA256SUMS
├── artifact.json
├── third_party/testlib/
└── data/problems/cf1486_c1/
    ├── desc.md
    ├── meta.json
    ├── cases/001.in ... 200.in
    ├── generator/gen_cases.cpp
    └── interactor/
        ├── non_adaptive.cpp
        └── adaptive.cpp
```

Consumers choose their own runner, compiler, isolation mechanism, case
selection, and result interpretation. The image has no custom entrypoint.

## Reproducibility

[`task.lock.json`](task.lock.json) pins both the InteractBench source revision
and the Hugging Face dataset revision. GitHub Actions materializes the upstream
task, generates the complete non-adaptive and adaptive case pools, verifies the
expected 200 files, builds the image, pushes it to GHCR, and checks every file
against `SHA256SUMS` inside the published image.

The InteractBench source and dataset are distributed under MIT. The bundled
testlib header carries its own MIT license under
`/opt/interactbench/third_party/testlib/LICENSE`.
