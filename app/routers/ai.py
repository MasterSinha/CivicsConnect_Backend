from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas import AiAnalysisResponse, AiResolutionVerificationRequest, AiResolutionVerificationResponse
from app.services.openai import analyze_issue_image, verify_resolution_images

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status() -> dict[str, str | bool | int]:
    from app.core.config import get_settings

    settings = get_settings()
    key = settings.openai_api_key.strip()
    return {
        "openai_configured": bool(key),
        "openai_model": settings.openai_model,
        "key_length": len(key),
        "key_prefix": f"{key[:4]}..." if key else "",
        "looks_like_openai_key": key.startswith("sk-"),
    }


@router.post("/analyze", response_model=AiAnalysisResponse)
async def analyze(image: UploadFile = File(...), category_hint: str | None = Form(default=None)) -> AiAnalysisResponse:
    try:
        return await analyze_issue_image(image, category_hint)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/verify-resolution", response_model=AiResolutionVerificationResponse)
async def verify_resolution(payload: AiResolutionVerificationRequest) -> AiResolutionVerificationResponse:
    return await verify_resolution_images(payload.before_image, payload.after_image)
