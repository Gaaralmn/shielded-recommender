# Use an ARG to make the base image version configurable from docker-compose.yml
ARG MLFLOW_IMAGE_TAG=v2.17.0
FROM ghcr.io/mlflow/mlflow:${MLFLOW_IMAGE_TAG}

# Install the PostgreSQL Python driver
# Using psycopg2-binary is recommended for easier installation in containers
RUN pip install --no-cache-dir psycopg2-binary

# Switch to the root user to bypass any volume permission issues in local dev
USER root