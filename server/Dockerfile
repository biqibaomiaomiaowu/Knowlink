FROM python:3.12-slim

ARG DEBIAN_MIRROR=https://mirrors.ustc.edu.cn/debian
ARG DEBIAN_SECURITY_MIRROR=https://mirrors.ustc.edu.cn/debian-security

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml README.md /workspace/
COPY server /workspace/server
COPY schemas /workspace/schemas

RUN sed -i \
        -e "s#URIs: http://deb.debian.org/debian-security#URIs: ${DEBIAN_SECURITY_MIRROR}#g" \
        -e "s#URIs: http://deb.debian.org/debian\$#URIs: ${DEBIAN_MIRROR}#g" \
        /etc/apt/sources.list.d/debian.sources && \
    apt-get update -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .[dev] && \
    find /usr/local -name '*.pyc' -delete && \
    find /usr/local -type d -name '__pycache__' -prune -exec rm -rf '{}' +

EXPOSE 8000
