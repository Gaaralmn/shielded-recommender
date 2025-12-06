FROM apache/airflow:2.8.1
USER root
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && apt-get clean
COPY ./airflow/requirements.txt /requirements.txt
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt
