#!/bin/sh
set -e

# Wait for MinIO to be ready
until /usr/bin/mc config host add myminio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}; do
  echo "Waiting for MinIO..."
  sleep 1
done

/usr/bin/mc mb myminio/clean-events || true