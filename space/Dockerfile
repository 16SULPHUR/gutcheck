FROM python:3.11-slim

ARG GUTCHECK_REF=master

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/user/.cache/huggingface \
    GUTCHECK_CONFIG=/app/space/gutcheck.yaml \
    SITE_ORIGINS=https://gutcheck-blush.vercel.app \
    SITE_ORIGIN_REGEX=^https://gutcheck-[a-z0-9-]+-16sulphurs-projects\\.vercel\\.app$

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install httpx "gutcheck @ git+https://github.com/16SULPHUR/gutcheck@${GUTCHECK_REF}"

RUN useradd --create-home --uid 1000 user
WORKDIR /app
COPY --chown=user . /app/space
USER user

# fetch the models at build time so the first visitor does not wait for a download
RUN cd /app && python -m space.warmup

EXPOSE 7860
CMD ["uvicorn", "space.app:app", "--host", "0.0.0.0", "--port", "7860"]
