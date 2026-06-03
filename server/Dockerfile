FROM python:3.12-slim

ARG DEBIAN_MIRROR=https://mirrors.ustc.edu.cn/debian
ARG DEBIAN_SECURITY_MIRROR=https://mirrors.ustc.edu.cn/debian-security
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml /workspace/

RUN sed -i \
        -e "s#URIs: http://deb.debian.org/debian-security#URIs: ${DEBIAN_SECURITY_MIRROR}#g" \
        -e "s#URIs: http://deb.debian.org/debian\$#URIs: ${DEBIAN_MIRROR}#g" \
        /etc/apt/sources.list.d/debian.sources && \
    apt-get update -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    find /usr/local -name '*.pyc' -delete && \
    find /usr/local -type d -name '__pycache__' -prune -exec rm -rf '{}' + && \
    pip install --index-url "${PIP_INDEX_URL}" --no-cache-dir --no-compile --upgrade pip setuptools wheel && \
    python -c "import pathlib, tomllib; data = tomllib.load(open('pyproject.toml', 'rb')); deps = list(data['project']['dependencies']) + list(data.get('project', {}).get('optional-dependencies', {}).get('dev', [])); pathlib.Path('/tmp/requirements.txt').write_text('\n'.join(deps) + '\n')" && \
    pip install --index-url "${PIP_INDEX_URL}" --no-cache-dir --no-compile -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt && \
    find /usr/local -name '*.pyc' -delete && \
    find /usr/local -type d -name '__pycache__' -prune -exec rm -rf '{}' +

COPY README.md /workspace/
COPY server /workspace/server
COPY schemas /workspace/schemas

RUN find /workspace -name '*.pyc' -delete && \
    find /workspace -type d -name '__pycache__' -prune -exec rm -rf '{}' +

EXPOSE 8000
