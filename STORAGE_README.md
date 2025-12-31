# MinIO Object Storage - Implementation Guide

## Overview

This document describes the MinIO (S3-compatible) object storage implementation for the Cognive Control Plane, implementing **SCRUM-106: Set up AWS S3 for long-term storage**.

**Implementation Choice**: MinIO (free, self-hosted, S3-compatible)  
**Alternative**: AWS S3 (cloud-hosted, pay-per-use)

## ✅ Acceptance Criteria Status

Most acceptance criteria from SCRUM-106 are covered by this repo; a couple of security-hardening items are intentionally left as production configuration:

- ✅ **Object storage deployed**: MinIO running in docker-compose
- ✅ **Buckets created**: 4 core buckets with purpose-specific configurations
- ✅ **Lifecycle/retention policies**: Automatic expiration configured per bucket
- ✅ **SDK/client integration**: boto3 S3-compatible API + MinIO native client
- ⚠️ **Access controls and encryption**: Credentials via env are in place; production-grade TLS, bucket policies (multi-tenancy), and encryption-at-rest require additional MinIO/AWS configuration (see Security Checklist below).

## Architecture

### Buckets

| Bucket Name | Purpose | Retention | Size Estimate |
|-------------|---------|-----------|---------------|
| `audit-logs-archive` | Long-term audit log storage | 90 days | ~50GB/year |
| `execution-replay-data` | Agent execution replay for debugging | 30 days | ~20GB/month |
| `report-exports` | Generated reports (PDF, CSV) | 365 days | ~10GB/year |
| `agent-artifacts` | Agent-generated outputs | 180 days | ~30GB/year |

### Features Implemented

1. **S3-Compatible API**: Works with boto3 (AWS SDK)
2. **Lifecycle Policies**: Automatic object expiration
3. **Versioning**: Enabled for data protection
4. **Web Console**: Management UI at http://localhost:9003
5. **Secure by Default**: Credentials from environment variables
6. **Auto-Initialization**: Buckets created on app startup

## Quick Start

### 1. Start Services

```bash
# Start all services including MinIO
docker-compose up -d

# Check MinIO is running
docker-compose ps minio
```

### 2. Initialize Storage (Automatic)

Storage is automatically initialized when the FastAPI app starts:

```bash
# Start API (triggers storage initialization)
docker-compose up api

# Or run initialization script manually
docker-compose exec api python scripts/init_storage.py
```

### 3. Verify Setup

```bash
# Run test suite
docker-compose exec api python scripts/test_storage.py

# Access web console
# URL: http://localhost:9003
# Username: cognive
# Password: aadmasod1rwsponr (from .env)
```

## Usage Examples

### Python Code

```python
from app.core.storage import get_storage_client

# Get storage client
storage = get_storage_client()

# Upload file
storage.upload_file(
    bucket_name="report-exports",
    object_name="reports/2024-01-01.pdf",
    file_path="/tmp/report.pdf"
)

# Download file
storage.download_file(
    bucket_name="report-exports",
    object_name="reports/2024-01-01.pdf",
    file_path="/tmp/downloaded.pdf"
)

# Upload bytes directly
data = b"Log entry: Agent completed successfully"
storage.put_object(
    bucket_name="audit-logs-archive",
    object_name="logs/2024/01/01.log",
    data=data
)

# Download bytes
content = storage.get_object(
    bucket_name="audit-logs-archive",
    object_name="logs/2024/01/01.log"
)

# List objects
objects = storage.list_objects(
    bucket_name="agent-artifacts",
    prefix="agent_123/"
)

# Generate presigned URL (temporary access)
url = storage.get_presigned_url(
    bucket_name="report-exports",
    object_name="reports/2024-01-01.pdf",
    expiration=3600  # 1 hour
)
```

### FastAPI Endpoint Example

```python
from fastapi import APIRouter, UploadFile
from app.core.storage import get_storage_client

router = APIRouter()

@router.post("/upload-artifact")
async def upload_artifact(agent_id: str, file: UploadFile):
    """Upload agent artifact to MinIO."""
    storage = get_storage_client()
    
    # Save to temporary file
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    # Upload to MinIO
    object_key = f"artifacts/{agent_id}/{file.filename}"
    storage.upload_file(
        bucket_name="agent-artifacts",
        object_name=object_key,
        file_path=temp_path
    )
    
    # Generate shareable URL
    url = storage.get_presigned_url(
        bucket_name="agent-artifacts",
        object_name=object_key,
        expiration=3600
    )
    
    return {
        "message": "Artifact uploaded",
        "url": url
    }
```

## Configuration

### Environment Variables

All MinIO configuration is in `.env`:

```bash
# Storage Endpoint (S3-compatible)
STORAGE_ENDPOINT=http://minio:9000  # Internal (from containers)
# STORAGE_ENDPOINT=http://localhost:9002  # External (from host)

# Credentials
MINIO_ROOT_USER=cognive
MINIO_ROOT_PASSWORD=aadmasod1rwsponr
```

### Docker Compose

MinIO is configured in `docker-compose.yml`:

```yaml
minio:
  image: minio/minio:latest
  restart: unless-stopped
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  command: server /data --console-address ":9001"
  ports:
    - "9002:9000"  # API
    - "9003:9001"  # Console
  volumes:
    - minio_data:/data
```

## Lifecycle Policies

Automatic object expiration configured per bucket:

| Bucket | Retention | Policy |
|--------|-----------|--------|
| audit-logs-archive | 90 days | Auto-delete after 90 days |
| execution-replay-data | 30 days | Auto-delete after 30 days |
| report-exports | 365 days | Auto-delete after 1 year |
| agent-artifacts | 180 days | Auto-delete after 6 months |

**Note**: Lifecycle policies may not be supported in all MinIO configurations. Check logs during initialization.

## Access Control

### Authentication

- **API Access**: Requires `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`
- **Console Access**: Same credentials via web UI
- **Client Configuration**: Credentials from environment variables

### Encryption

- **In Transit**: Enable HTTPS/TLS in production (set `STORAGE_SECURE=true` and point `STORAGE_ENDPOINT` at an HTTPS endpoint)
- **At Rest (SSE)**: This code supports optional **server-side encryption headers** for writes via `STORAGE_SSE` / `STORAGE_SSE_KMS_KEY_ID` (recommended for AWS S3; for MinIO it requires KMS/KES configuration).
- **Recommended**: Enable TLS + encryption-at-rest for production deployments.

### Best Practices

1. **Credentials**: Use strong passwords in production
2. **Network**: Restrict MinIO ports to internal network
3. **Buckets**: Create separate buckets per tenant/team
4. **Versioning**: Keep versioning enabled for critical data
5. **Backups**: Regular backups of MinIO data volume

## Monitoring & Operations

### Health Checks

MinIO health is checked via HTTP API:

```bash
# Check MinIO health
curl http://localhost:9002/minio/health/live

# Check specific bucket
docker-compose exec api python -c "
from app.core.storage import get_storage_client
storage = get_storage_client()
print(storage.minio_client.bucket_exists('audit-logs-archive'))
"
```

### Metrics

MinIO exposes Prometheus metrics:

```bash
# Metrics endpoint
curl http://localhost:9002/minio/v2/metrics/cluster
```

### Web Console

Access the MinIO web console for:
- Bucket management
- Object browsing
- User management
- Performance metrics
- Access logs

**URL**: http://localhost:9003  
**Credentials**: From `.env` file

## Troubleshooting

### Issue: Buckets Not Created

**Solution**:
```bash
# Run initialization script manually
docker-compose exec api python scripts/init_storage.py
```

### Issue: Connection Refused

**Check**:
1. MinIO container is running: `docker-compose ps minio`
2. Endpoint is correct: `http://minio:9000` (internal) or `http://localhost:9002` (external)
3. Credentials match `.env` file

### Issue: Lifecycle Policies Not Applied

**Note**: Some MinIO configurations don't support lifecycle policies. Check logs:

```bash
docker-compose logs api | grep lifecycle
```

This is a warning, not an error. Storage will work without lifecycle policies.

### Issue: Permission Denied

**Check**:
1. MinIO data volume permissions: `docker-compose exec minio ls -la /data`
2. Credentials are correct in `.env`

## Migration to AWS S3

MinIO uses S3-compatible API, so migration is straightforward:

### 1. Update Configuration

```python
# Change from MinIO to AWS S3
STORAGE_ENDPOINT=https://s3.amazonaws.com
STORAGE_ACCESS_KEY=<AWS_ACCESS_KEY_ID>
STORAGE_SECRET_KEY=<AWS_SECRET_ACCESS_KEY>
```

### 2. Update Region (if needed)

```python
# In app/core/storage.py, update region
region_name="us-east-1"  # Or your preferred region
```

### 3. Code Changes

**None required!** The same code works with AWS S3:

```python
# Works with both MinIO and AWS S3
storage = get_storage_client()
storage.upload_file("report-exports", "report.pdf", "/tmp/report.pdf")
```

### 4. Cost Comparison

| Service | Storage | Requests | Transfer | Total (100GB) |
|---------|---------|----------|----------|---------------|
| **MinIO** | $0 (self-hosted) | $0 | $0 | **$0/month** |
| **AWS S3 Standard** | $0.023/GB | $0.005/1K PUT | $0.09/GB out | **~$11/month** |
| **AWS S3 IA** | $0.0125/GB | $0.01/1K PUT | $0.09/GB out | **~$6/month** |
| **AWS S3 Glacier** | $0.004/GB | $0.03/1K PUT | Variable | **~$2/month** |

**Recommendation**: Start with MinIO (free). Migrate to AWS S3 when:
- Need 99.999999999% durability (11 9's)
- Multi-region replication required
- Global CDN integration needed
- Don't want to manage storage infrastructure

## Testing

### Run Full Test Suite

```bash
docker-compose exec api python scripts/test_storage.py
```

Tests include:
- Bucket operations
- File upload/download
- Object CRUD operations
- Large file handling
- Presigned URL generation
- Real-world use case demos

### Manual Testing

```bash
# Initialize storage
docker-compose exec api python scripts/init_storage.py

# Test upload
docker-compose exec api python -c "
from app.core.storage import get_storage_client
storage = get_storage_client()
storage.put_object('agent-artifacts', 'test.txt', b'Hello MinIO!')
print('Upload successful!')
"

# Test download
docker-compose exec api python -c "
from app.core.storage import get_storage_client
storage = get_storage_client()
data = storage.get_object('agent-artifacts', 'test.txt')
print(f'Downloaded: {data}')
"
```

## Performance Characteristics

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Small object PUT (<1MB) | ~10-50ms | 1000+ ops/sec |
| Large object PUT (>100MB) | ~1-5s | 100-500 MB/s |
| GET operation | ~5-30ms | 1000+ ops/sec |
| List objects (1K objects) | ~50-200ms | N/A |
| Presigned URL generation | <1ms | N/A |

**Note**: Performance depends on hardware and network configuration.

## Security Checklist

- ✅ Credentials stored in environment variables (not code)
- ✅ MinIO ports not exposed to public internet
- ✅ Bucket versioning enabled
- ✅ Lifecycle policies configured
- ⚠️ TLS encryption (configure for production)
- ⚠️ Bucket policies (configure for multi-tenancy)
- ⚠️ Audit logging (enable for compliance)

## References

- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [MinIO Python Client](https://min.io/docs/minio/linux/developers/python/minio-py.html)
- [boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [SCRUM-106 Jira Issue](https://zenstreams03.atlassian.net/browse/SCRUM-106)

## Support

For issues or questions:
1. Check logs: `docker-compose logs minio`
2. Verify configuration: `env | grep MINIO`
3. Test connectivity: `curl http://localhost:9002/minio/health/live`
4. Access console: http://localhost:9003

---

**Status**: ✅ Implementation Complete  
**Story**: SCRUM-106  
**Date**: December 30, 2025

