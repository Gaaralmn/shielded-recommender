# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Create a non-root user
RUN useradd --create-home appuser

# Copy the dependencies file to the working directory
COPY ./services/trainer/requirements.txt .

# Install uv and then use it to install packages from requirements.txt
RUN pip install --no-cache-dir uv && \
    python -m uv pip install --no-cache-dir -r requirements.txt

# Now, switch to the non-root user for running the application
USER appuser

# Copy the rest of the application's code to the working directory
COPY --chown=appuser:appuser ./services/trainer/src ./src
COPY --chown=appuser:appuser ./recommender_schemas ./recommender_schemas
COPY --chown=appuser:appuser ./services/trainer/dags ./dags

# Run the training script
# Note: This assumes you have a train.py script in the src directory
CMD ["python", "src/train.py"]
