FROM scratch AS assets

COPY rootfs/ /

# The verify stage runs the integrity checks that used to run inside the
# published image; the final image is pure assets and has no shell. Build it
# explicitly with --target verify before building the default target.
FROM debian:bookworm-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818 AS verify

COPY --from=assets /opt/interactbench /opt/interactbench

ARG TASK_ID
ARG EXPECT_MODE
ARG EXPECT_CASES

RUN set -eu; \
    root="/opt/interactbench/data/problems/${TASK_ID}"; \
    set -- "$root"/cases/*.in; \
    test "$#" -eq "${EXPECT_CASES}"; \
    test -f "$root/meta.json"; \
    case "${EXPECT_MODE}" in \
      non_adaptive) test -f "$root/interactor/non_adaptive.cpp" ;; \
      adaptive) test -f "$root/interactor/adaptive.cpp" ;; \
      both) \
        test -f "$root/interactor/non_adaptive.cpp"; \
        test -f "$root/interactor/adaptive.cpp" ;; \
      *) echo "unknown interactor mode ${EXPECT_MODE}" >&2; exit 1 ;; \
    esac; \
    test ! -e "$root/desc.md"; \
    test ! -e "$root/generator"; \
    test ! -e /opt/interactbench/third_party; \
    test -f /opt/interactbench/LICENSE; \
    test -f /opt/interactbench/artifact.json; \
    cd /opt/interactbench; \
    sha256sum -c SHA256SUMS > /dev/null

FROM scratch

ARG TASK_ID
ARG LOCK_DIGEST
ARG SOURCE_REVISION
ARG DATASET_REVISION

LABEL org.opencontainers.image.title="InteractBench task ${TASK_ID}"
LABEL org.opencontainers.image.description="InteractBench judging assets with successfully generated cases"
LABEL org.opencontainers.image.source="https://github.com/xwysyy-studio/InteractBench-Image"
LABEL org.opencontainers.image.url="https://github.com/kmsgk0/InteractBench"
LABEL org.opencontainers.image.version="${TASK_ID}-${LOCK_DIGEST}"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.interactbench.task.id="${TASK_ID}"
LABEL org.interactbench.asset.root="/opt/interactbench/data/problems/${TASK_ID}"
LABEL org.interactbench.source.revision="${SOURCE_REVISION}"
LABEL org.interactbench.dataset.revision="${DATASET_REVISION}"

COPY --from=assets / /

WORKDIR /opt/interactbench
