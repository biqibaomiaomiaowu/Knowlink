FROM python:3.12-slim

WORKDIR /workspace

COPY pyproject.toml README.md /workspace/
COPY server /workspace/server
COPY schemas /workspace/schemas

RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install sqlalchemy==2.0.30 -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple

EXPOSE 8000
