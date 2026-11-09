# Hidden-grader runner for saleor (built on the saleor test image). Run with --network container:<postgres>.
FROM ucn-saleor-tests
COPY run.sh /run.sh
RUN sed -i 's/\r$//' /run.sh && chmod +x /run.sh
ENTRYPOINT ["/run.sh"]
