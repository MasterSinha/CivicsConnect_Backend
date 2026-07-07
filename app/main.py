import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.core.config import get_settings
from app.database import Base, engine
from app.routers.auth import router as auth_router
from app.routers.authority import router as authority_router
from app.routers.dashboard import router as dashboard_router
from app.routers.ai import router as ai_router
from app.routers.community import router as community_router
from app.routers.issues import router as issues_router
from app.storage import UPLOAD_DIR


settings = get_settings()
logger = logging.getLogger(__name__)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def initialize_database() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS reporter_id UUID REFERENCES users(id) ON DELETE SET NULL'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_summary TEXT'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_public_note TEXT'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_worker VARCHAR(160)'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_date DATE'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_materials VARCHAR(255)'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_before_image TEXT'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_after_image TEXT'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_resolution_resolved BOOLEAN'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_resolution_confidence INTEGER'))
            connection.execute(text('ALTER TABLE issues ADD COLUMN IF NOT EXISTS ai_resolution_remarks TEXT'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_issues_reporter_id ON issues (reporter_id)'))
            connection.execute(text('ALTER TABLE issue_assignments ADD COLUMN IF NOT EXISTS field_worker VARCHAR(160)'))
            connection.execute(text('ALTER TABLE issue_assignments ADD COLUMN IF NOT EXISTS priority VARCHAR(40)'))
            connection.execute(text('ALTER TABLE issue_assignments ADD COLUMN IF NOT EXISTS eta DATE'))
            connection.execute(text('CREATE TABLE IF NOT EXISTS authority_workers (id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), authority_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, department VARCHAR(120) NOT NULL, name VARCHAR(160) NOT NULL, phone_number VARCHAR(32), role_label VARCHAR(120), active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_authority_workers_authority_id ON authority_workers (authority_id)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_authority_workers_department ON authority_workers (department)'))
            
            # Ensure votes table has user_id and index
            connection.execute(text('ALTER TABLE votes ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE'))
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_votes_issue_user_type ON votes (issue_id, user_id, vote_type) WHERE user_id IS NOT NULL'))
    except SQLAlchemyError as exc:
        logger.warning("Database initialization skipped at startup: %s", exc)


app = FastAPI(title="CivicConnect AI API", version="1.0.0")


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(asyncio.to_thread(initialize_database))


# Determine CORS settings based on environment.
# In development, dynamically allow all HTTP/HTTPS origins to completely resolve development CORS blocks,
# since allow_origins=["*"] is incompatible with allow_credentials=True.
if settings.environment.lower() == "development":
    cors_kwargs = {
        "allow_origin_regex": r"https?://.*",
    }
else:
    cors_kwargs = {
        "allow_origins": settings.cors_origins,
    }

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **cors_kwargs,
)

app.include_router(auth_router)
app.include_router(authority_router)
app.include_router(dashboard_router)
app.include_router(ai_router)
app.include_router(community_router)
app.include_router(issues_router)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return {"status": "error", "database": "unavailable"}
    return {"status": "ok", "database": "available"}
