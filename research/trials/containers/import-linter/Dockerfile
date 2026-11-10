FROM python:3.12-slim
RUN pip install --no-cache-dir "import-linter==2.15"
WORKDIR /repo
ENV PYTHONPATH=/repo/src
ENTRYPOINT ["lint-imports"]
