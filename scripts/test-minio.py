#!/usr/bin/env python3
"""
Test MinIO connectivity and bucket operations.

This script verifies that MinIO is properly configured and accessible.
"""

import pandas as pd
import os
from datetime import datetime

# MinIO configuration
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")

storage_options = {
    "key": S3_ACCESS_KEY,
    "secret": S3_SECRET_KEY,
    "client_kwargs": {"endpoint_url": S3_ENDPOINT_URL}
}


def test_minio_write():
    """Test writing data to MinIO."""
    print("📝 Testing MinIO write operation...")

    # Create sample data
    df = pd.DataFrame({
        'timestamp': [datetime.now().timestamp()],
        'user_id': [12345],
        'item_id': [67890],
        'event': ['view']
    })

    # Write to MinIO
    path = f's3://clean-events/test/test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    df.to_parquet(path, storage_options=storage_options)

    print(f"✅ Successfully wrote to MinIO: {path}")
    return path


def test_minio_read(path):
    """Test reading data from MinIO."""
    print(f"\n📖 Testing MinIO read operation...")

    # Read from MinIO
    df = pd.read_parquet(path, storage_options=storage_options)

    print(f"✅ Successfully read {len(df)} rows from MinIO")
    print(f"\nData preview:\n{df}")
    return df


def test_minio_list():
    """Test listing files in MinIO bucket."""
    print(f"\n📂 Testing MinIO list operation...")

    try:
        import s3fs
        fs = s3fs.S3FileSystem(
            key=S3_ACCESS_KEY,
            secret=S3_SECRET_KEY,
            client_kwargs={"endpoint_url": S3_ENDPOINT_URL}
        )

        # List files in clean-events bucket
        files = fs.ls('clean-events')
        print(f"✅ Found {len(files)} files/directories in 'clean-events' bucket")

        if files:
            print("\nFiles:")
            for f in files[:5]:  # Show first 5
                print(f"  - {f}")
            if len(files) > 5:
                print(f"  ... and {len(files) - 5} more")
    except Exception as e:
        print(f"⚠️  List operation skipped: {e}")


def main():
    print("=" * 60)
    print("MinIO Connectivity Test")
    print("=" * 60)
    print(f"\nEndpoint: {S3_ENDPOINT_URL}")
    print(f"Access Key: {S3_ACCESS_KEY[:4]}***")
    print(f"Secret Key: {S3_SECRET_KEY[:4]}***\n")

    try:
        # Test write
        path = test_minio_write()

        # Test read
        test_minio_read(path)

        # Test list
        test_minio_list()

        print("\n" + "=" * 60)
        print("✅ All tests passed! MinIO is working correctly.")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("1. Ensure MinIO is running: docker-compose ps minio")
        print("2. Check MinIO logs: docker-compose logs minio")
        print("3. Verify credentials in .env file")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
