FROM apache/airflow:2.10.5-python3.12
RUN pip install --no-cache-dir "apache-airflow==2.10.5" "psycopg[binary]==3.2.9" "pydantic==2.11.5"
COPY --chown=airflow:root banking /opt/banking/banking
COPY --chown=airflow:root airflow/banking_dags.py /opt/airflow/dags/
ENV PYTHONPATH=/opt/banking
