FROM python:3.12.10-slim
RUN pip install --no-cache-dir dbt-core==1.9.8 dbt-postgres==1.9.0 && useradd --create-home --uid 10001 dbt \
    && install -d -o dbt -g dbt /app
WORKDIR /app
COPY --chown=dbt:dbt analytics/ .
ENV DBT_PROFILES_DIR=/app
USER dbt
ENTRYPOINT ["dbt"]
CMD ["build"]
