# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Create a non-root user
RUN useradd --create-home appuser

# Copy the dependencies file to the working directory
COPY ./services/data_pipeline_worker/requirements.txt .

# Install uv and then use it to install packages from requirements.txt
RUN pip install --no-cache-dir uv && \
    python -m uv pip install --no-cache-dir -r requirements.txt

# Now, switch to the non-root user
USER appuser

# Copy the application's code to the working directory
COPY --chown=appuser:appuser ./services/data_pipeline_worker/src ./src
COPY --chown=appuser:appuser ./recommender_schemas ./recommender_schemas
