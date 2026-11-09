FROM python:3.12-slim
RUN pip install --no-cache-dir platformdirs chardet "click<8.6.0" "colorama>=0.3" "diff-cover>=2.5.0" Jinja2 pathspec \
    "pyyaml>=5.1" regex tblib tqdm "pytest<9" hypothesis
ENV PYTHONPATH=/repo/src
WORKDIR /grader
ENTRYPOINT ["python", "-m", "pytest", "-p", "no:cacheprovider", "-q", "--rootdir=/grader"]
# The source is mounted read-only at /repo/src; give it package metadata (version, plugin entry points)
COPY METADATA entry_points.txt /usr/local/lib/python3.12/site-packages/sqlfluff-4.5.0.dist-info/
