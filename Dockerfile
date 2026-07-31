FROM debian:bookworm-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818

ARG TASK_ID
ARG LOCK_DIGEST
ARG SOURCE_REVISION
ARG DATASET_REVISION

LABEL org.opencontainers.image.title="InteractBench task ${TASK_ID}"
LABEL org.opencontainers.image.description="Tool-independent InteractBench task assets with the complete generated case pool"
LABEL org.opencontainers.image.source="https://github.com/xwysyy-studio/InteractBench-Image"
LABEL org.opencontainers.image.url="https://github.com/kmsgk0/InteractBench"
LABEL org.opencontainers.image.version="${TASK_ID}-${LOCK_DIGEST}"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.interactbench.task.id="${TASK_ID}"
LABEL org.interactbench.asset.root="/opt/interactbench/data/problems/${TASK_ID}"
LABEL org.interactbench.source.revision="${SOURCE_REVISION}"
LABEL org.interactbench.dataset.revision="${DATASET_REVISION}"

COPY rootfs/ /

WORKDIR /opt/interactbench
