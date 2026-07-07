import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"


def _safe_suffix(filename: str) -> str:
    return Path(filename).suffix.lower() or ".jpg"


def _public_gcs_url(bucket_name: str, object_name: str) -> str:
    settings = get_settings()
    if settings.gcs_public_base_url:
        return f"{settings.gcs_public_base_url.rstrip('/')}/{object_name}"
    return f"https://storage.googleapis.com/{bucket_name}/{object_name}"


def save_upload_file(upload: UploadFile, prefix: str = "") -> str:
    settings = get_settings()
    suffix = _safe_suffix(upload.filename or "")
    filename = f"{prefix}{uuid4().hex}{suffix}"

    if settings.upload_storage.lower() == "gcs":
        bucket_name = settings.storage_bucket_name
        if not bucket_name:
            raise RuntimeError("GCP_STORAGE_BUCKET is required when UPLOAD_STORAGE=gcs")
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required when UPLOAD_STORAGE=gcs") from exc

        upload.file.seek(0)
        client = storage.Client(project=settings.storage_project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(upload.file, content_type=upload.content_type or "application/octet-stream")
        return _public_gcs_url(bucket_name, filename)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / filename
    upload.file.seek(0)
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return f"/uploads/{filename}"
