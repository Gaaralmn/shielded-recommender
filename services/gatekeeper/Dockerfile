# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Create a non-root user
RUN useradd --create-home appuser
USER appuser

# Copy the dependencies file to the working directory
COPY --chown=appuser:appuser ./services/gatekeeper/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY --chown=appuser:appuser ./services/gatekeeper/src ./src
COPY --chown=appuser:appuser ./schemas ./schemas

# Expose the port the app runs on
EXPOSE 8000

# Run the application
# Note: This assumes you have a main.py in src with a FastAPI app instance named "app"
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
