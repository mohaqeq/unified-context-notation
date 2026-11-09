#!/bin/sh
# Copy the (read-only) workspace, drop the hidden tests into saleor/hidden_tests, run them. Extra args go to pytest.
set -e
mkdir -p /work && (cd /repo && tar --exclude=.git -cf - .) | (cd /work && tar -xf -)
mkdir -p /work/saleor/hidden_tests && cp /grader/*.py /work/saleor/hidden_tests/ && touch /work/saleor/hidden_tests/__init__.py
cd /work && exec pytest -p no:cacheprovider -n 0 -q saleor/hidden_tests "$@"
