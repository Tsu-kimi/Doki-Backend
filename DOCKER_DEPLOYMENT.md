# Docker Deployment Guide for Doki Backend

## Overview
This guide covers building and deploying the Doki FastAPI backend using Docker, with specific instructions for Google Cloud Run deployment.

---

## Prerequisites

### Required Tools
- Docker installed locally
- Google Cloud SDK (`gcloud` CLI)
- GCP project with billing enabled
- Poetry (for local development)

### Required Services Enabled
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

---

## Dockerfile Architecture

### Key Design Decisions

1. **Base Image**: `python:3.10-slim` - Minimal Python runtime
2. **Dependency Management**: Poetry for reproducible builds
3. **Layer Caching**: Dependencies installed before code copy
4. **Security**: Non-root user (`appuser`)
5. **Cloud Run Compatibility**: Listens on `$PORT` environment variable
6. **Single Process**: One Uvicorn process (Cloud Run handles replication)

### Environment Variables

The Dockerfile uses these environment variables:
- `PORT`: Port to listen on (Cloud Run injects this, defaults to 8080)
- `PYTHONUNBUFFERED=1`: Immediate log output to stdout
- `PYTHONDONTWRITEBYTECODE=1`: Prevent .pyc file creation

---

## Local Docker Testing

### 1. Build the Docker Image

```bash
# From project root
docker build -t doki-backend:dev .
```

### 2. Run Locally with Environment Variables

```bash
# Create a .env file with your local secrets (DO NOT COMMIT)
# Then run:
docker run -d \
  --name doki-backend-local \
  -p 8080:8080 \
  -e PORT=8080 \
  -e ENVIRONMENT=development \
  -e SUPABASE_URL=your-supabase-url \
  -e SUPABASE_SECRET_KEY=your-secret-key \
  -e GOOGLE_CLIENT_ID_NAME=your-client-id \
  -e GOOGLE_CLIENT_SECRET_NAME=your-client-secret \
  -e SESSION_SECRET_KEY=dev-secret-key \
  -e ENCRYPTION_KEY=your-fernet-key \
  -e ALLOWED_ORIGINS=http://localhost:3000 \
  doki-backend:dev
```

### 3. Test Health Check

```bash
curl http://localhost:8080/
# Expected: {"message": "Doki Backend up"}
```

### 4. Test API Endpoints

```bash
# Check API docs
open http://localhost:8080/docs

# Test connectors endpoint
curl http://localhost:8080/connectors/sheets/schema
```

### 5. View Logs

```bash
docker logs doki-backend-local
```

### 6. Stop and Remove

```bash
docker stop doki-backend-local
docker rm doki-backend-local
```

---

## Google Cloud Run Deployment

### 1. Set Up Environment Variables

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1  # or your preferred region
export SERVICE_NAME=doki-backend
export IMAGE_TAG=gcr.io/$PROJECT_ID/$SERVICE_NAME:latest
```

### 2. Build and Push to Google Container Registry

```bash
# Build and push in one command
gcloud builds submit --tag $IMAGE_TAG

# Or build locally and push
docker build -t $IMAGE_TAG .
docker push $IMAGE_TAG
```

### 3. Create Secrets in Secret Manager

Before deploying, ensure all secrets are stored in Secret Manager:

```bash
# Create secrets (do this once)
echo -n "your-supabase-secret-key" | gcloud secrets create supabase-secret-key --data-file=-
echo -n "your-google-client-id" | gcloud secrets create google-oauth-client-id --data-file=-
echo -n "your-google-client-secret" | gcloud secrets create google-oauth-client-secret --data-file=-
echo -n "your-session-secret" | gcloud secrets create session-secret-key --data-file=-
echo -n "your-fernet-key" | gcloud secrets create encryption-key --data-file=-
echo -n "your-jwt-secret" | gcloud secrets create supabase-jwt-secret --data-file=-
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_TAG \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 300 \
  --set-env-vars "ENVIRONMENT=production,SUPABASE_URL=https://your-project.supabase.co,ALLOWED_ORIGINS=https://your-frontend-domain.com" \
  --set-secrets "SUPABASE_SECRET_KEY=supabase-secret-key:latest,GOOGLE_CLIENT_ID_NAME=google-oauth-client-id:latest,GOOGLE_CLIENT_SECRET_NAME=google-oauth-client-secret:latest,SESSION_SECRET_KEY_NAME=session-secret-key:latest,ENCRYPTION_KEY=encryption-key:latest,SUPABASE_JWT_SECRET=supabase-jwt-secret:latest"
```

### 5. Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/

# Check API docs
open $SERVICE_URL/docs
```

---

## Environment Variables Reference

### Required for Production

| Variable | Description | Source |
|----------|-------------|--------|
| `ENVIRONMENT` | Set to `production` | Cloud Run env var |
| `PORT` | Port to listen on | Cloud Run injects automatically |
| `SUPABASE_URL` | Supabase project URL | Cloud Run env var |
| `SUPABASE_SECRET_KEY` | Service role key | Secret Manager |
| `SUPABASE_JWT_SECRET` | JWT signing secret | Secret Manager |
| `GOOGLE_CLIENT_ID_NAME` | OAuth client ID | Secret Manager |
| `GOOGLE_CLIENT_SECRET_NAME` | OAuth client secret | Secret Manager |
| `SESSION_SECRET_KEY_NAME` | Session encryption key | Secret Manager |
| `ENCRYPTION_KEY` | Fernet encryption key | Secret Manager |
| `ALLOWED_ORIGINS` | CORS allowed origins | Cloud Run env var |
| `GCP_PROJECT_ID` | Your GCP project ID | Cloud Run env var |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI | Auto-generated |

---

## CORS Configuration

The backend is configured to accept requests from origins specified in `ALLOWED_ORIGINS`:

```bash
# Development (multiple origins)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001

# Production (your frontend domain)
ALLOWED_ORIGINS=https://app.doki.com,https://www.doki.com
```

Update this when deploying:
```bash
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars "ALLOWED_ORIGINS=https://your-frontend-domain.com"
```

---

## Health Checks

The Dockerfile includes a health check that verifies the service is responding:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/')"
```

Cloud Run automatically performs health checks on the root endpoint (`/`).

---

## Troubleshooting

### Container Fails to Start

**Error**: "Container failed to start. Failed to start and then listen on the port defined by the PORT environment variable."

**Solution**: Ensure your app listens on `0.0.0.0` and uses `$PORT`:
```python
# In Dockerfile CMD
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
```

### Secret Manager Access Denied

**Error**: "Permission denied when accessing Secret Manager"

**Solution**: Grant the Cloud Run service account access:
```bash
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### CORS Errors

**Error**: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Solution**: Update `ALLOWED_ORIGINS` to include your frontend domain:
```bash
gcloud run services update $SERVICE_NAME \
  --set-env-vars "ALLOWED_ORIGINS=https://your-frontend.com"
```

### Import Errors

**Error**: "ModuleNotFoundError: No module named 'app'"

**Solution**: Ensure you're using `app.main:app` (not `main:app`) in the CMD:
```dockerfile
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
```

---

## Best Practices

### 1. Use Multi-Stage Builds (Optional Optimization)
For smaller images, consider a multi-stage build that separates build dependencies from runtime.

### 2. Pin Dependency Versions
Use `poetry.lock` to ensure reproducible builds across environments.

### 3. Monitor Logs
```bash
# Stream logs
gcloud run services logs tail $SERVICE_NAME --region $REGION

# View logs in Cloud Console
gcloud run services describe $SERVICE_NAME --region $REGION
```

### 4. Set Resource Limits
Adjust memory and CPU based on your needs:
```bash
gcloud run services update $SERVICE_NAME \
  --memory 1Gi \
  --cpu 2
```

### 5. Enable Cloud Run Autoscaling
```bash
gcloud run services update $SERVICE_NAME \
  --min-instances 1 \  # Keep warm instance
  --max-instances 100  # Scale up to 100
```

---

## Security Checklist

- [ ] All secrets stored in Secret Manager (not environment variables)
- [ ] Service account has minimal required permissions
- [ ] CORS configured with specific origins (not `*`)
- [ ] Container runs as non-root user
- [ ] `ENVIRONMENT=production` set in Cloud Run
- [ ] HTTPS enforced (Cloud Run default)
- [ ] `.env` file in `.dockerignore`
- [ ] No credentials in Docker image or Git repository

---

## Continuous Deployment

### Using Cloud Build

Create `cloudbuild.yaml`:

```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/doki-backend:$COMMIT_SHA', '.']
  
  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/doki-backend:$COMMIT_SHA']
  
  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'doki-backend'
      - '--image'
      - 'gcr.io/$PROJECT_ID/doki-backend:$COMMIT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'

images:
  - 'gcr.io/$PROJECT_ID/doki-backend:$COMMIT_SHA'
```

---

## Next Steps

1. ✅ Build Docker image locally
2. ✅ Test container with mock environment variables
3. ✅ Verify all endpoints work (`/`, `/connectors/sheets/list`, etc.)
4. ✅ Create secrets in Secret Manager
5. ✅ Deploy to Cloud Run
6. ✅ Update frontend to use Cloud Run URL
7. ✅ Configure custom domain (optional)
8. ✅ Set up monitoring and alerts

---

## Additional Resources

- [FastAPI Docker Documentation](https://fastapi.tiangolo.com/deployment/docker/)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
