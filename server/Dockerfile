FROM python:3.12-slim

WORKDIR /workspace

COPY pyproject.toml README.md /workspace/
COPY server /workspace/server

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .[dev]

EXPOSE 8000
