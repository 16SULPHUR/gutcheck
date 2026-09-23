# CPU:  docker build -t gutcheck .
# GPU:  docker build -t gutcheck:gpu --build-arg TORCH_VARIANT=cu126 .
FROM python:3.11-slim

ARG TORCH_VARIANT=cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/data/hf \
    GUTCHECK_HOST=0.0.0.0 \
    GUTCHECK_PORT=8080

# torch first, from the variant-specific index, so the default PyPI build is never pulled
RUN pip install torch --index-url https://download.pytorch.org/whl/${TORCH_VARIANT}

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

RUN useradd --create-home --uid 1000 gutcheck \
    && mkdir -p /data \
    && chown gutcheck:gutcheck /data
USER gutcheck
VOLUME /data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['GUTCHECK_PORT'] + '/healthz', timeout=4)"

CMD ["gutcheck", "serve"]
