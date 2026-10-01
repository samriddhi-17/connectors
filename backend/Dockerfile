FROM docker.io/python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY run.py ./run.py

# Aerospike has manylinux wheels; on Linux it installs fine. On platforms
# where it does not, the connector degrades gracefully at runtime.
RUN pip install --upgrade pip && pip install ".[aerospike]"

EXPOSE 8000

CMD ["python", "run.py"]