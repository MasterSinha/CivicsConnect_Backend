# Deploy CivicConnect Backend on Google Cloud Run

This backend is packaged for Cloud Run. The app keeps the same FastAPI routes and environment-variable based database/JWT/Gemini connections.

## 1. Required GCP services

Enable these APIs in your GCP project:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com
```

Create an Artifact Registry repository:

```bash
gcloud artifacts repositories create civicconnect --repository-format=docker --location=asia-south1
```

## 2. Database

Use Cloud SQL PostgreSQL, or any reachable PostgreSQL database. Set `DATABASE_URL` in Cloud Run using the same SQLAlchemy format already used locally:

```text
postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB_NAME
```

For Cloud SQL private/public IP, use the database host IP. If you use private IP, deploy Cloud Run with the correct VPC connector.

Run `backend/db/init.sql` once on the production database before opening the app.

## 3. Runtime environment variables

Set these in Cloud Run:

```text
DATABASE_URL
JWT_SECRET_KEY
JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRE_MINUTES
JWT_REMEMBER_ME_EXPIRE_DAYS
FRONTEND_ORIGIN
FRONTEND_ORIGINS
ENVIRONMENT=production
GEMINI_API_KEY
GEMINI_MODEL=gemini-1.5-flash
UPLOAD_STORAGE=gcs
GCP_STORAGE_BUCKET=civicscon-uploads
GCP_PROJECT_ID=civicscon
```

Store sensitive values such as `DATABASE_URL`, `JWT_SECRET_KEY`, and `GEMINI_API_KEY` in Secret Manager.

The provided `cloudbuild.yaml` expects these Secret Manager secret names:

```text
DATABASE_URL
JWT_SECRET_KEY
GEMINI_API_KEY
```

Create them before deploying:

```bash
gcloud secrets create DATABASE_URL --replication-policy=automatic
gcloud secrets create JWT_SECRET_KEY --replication-policy=automatic
gcloud secrets create GEMINI_API_KEY --replication-policy=automatic
```

Then add secret versions from the GCP console or with `gcloud secrets versions add`.

Give the Cloud Run runtime service account access to read these secrets:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:YOUR_RUNTIME_SERVICE_ACCOUNT" --role="roles/secretmanager.secretAccessor"
```

Give the same Cloud Run runtime service account access to write/read uploaded images in Cloud Storage:

```bash
gcloud storage buckets add-iam-policy-binding gs://civicscon-uploads --member="serviceAccount:YOUR_RUNTIME_SERVICE_ACCOUNT" --role="roles/storage.objectAdmin"
```

## 4. Build and deploy

From the repository root:

```bash
gcloud builds submit --config cloudbuild.yaml --substitutions _SERVICE=civicconnect-backend,_REGION=asia-south1,_FRONTEND_ORIGIN=https://YOUR_FRONTEND_URL,_FRONTEND_ORIGINS=https://YOUR_FRONTEND_URL
```

The Cloud Build deploy step binds the standard secrets and sets production CORS/frontend environment values.

## 5. Verify

```bash
curl https://YOUR_CLOUD_RUN_URL/health
curl https://YOUR_CLOUD_RUN_URL/readyz
```

Expected:

```json
{"status":"ok"}
{"status":"ok","database":"available"}
```

## Notes

- Cloud Run container listens on `$PORT`, defaulting to `8080`.
- Set `UPLOAD_STORAGE=gcs` with `GCP_STORAGE_BUCKET` to persist citizen complaint images and evidence in Cloud Storage. Local `uploads/` remains available only for development when `UPLOAD_STORAGE=local`.
