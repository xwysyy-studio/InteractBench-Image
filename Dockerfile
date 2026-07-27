FROM debian:bookworm-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818

LABEL org.opencontainers.image.title="InteractBench task cf1486_c1"
LABEL org.opencontainers.image.description="Tool-independent InteractBench task assets with the complete generated case pool"
LABEL org.opencontainers.image.source="https://github.com/xwysyy-studio/InteractBench-Image"
LABEL org.opencontainers.image.url="https://github.com/kmsgk0/InteractBench"
LABEL org.opencontainers.image.version="cf1486_c1-a8228209"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.interactbench.task.id="cf1486_c1"
LABEL org.interactbench.asset.root="/opt/interactbench/data/problems/cf1486_c1"
LABEL org.interactbench.source.revision="555a1c66babfc89abc22c19ede54a48652a417f5"
LABEL org.interactbench.dataset.revision="a82282090288a7d28b9905d7064ece53c489b33a"

COPY build/rootfs/ /

WORKDIR /opt/interactbench
