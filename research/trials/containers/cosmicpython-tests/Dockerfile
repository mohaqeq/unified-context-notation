FROM python:3.9-slim
RUN pip install --no-cache-dir "sqlalchemy<2" flask redis psycopg2-binary requests tenacity "pytest<8"
WORKDIR /repo
ENV PYTHONPATH=/repo/src
ENTRYPOINT ["python", "-m", "pytest", "-p", "no:cacheprovider", "-q"]
