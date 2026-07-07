import base64
import json

import httpx
from fastapi import UploadFile

from app.core.config import get_settings
from app.schemas import AiAnalysisResponse, AiResolutionVerificationResponse


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

FALLBACKS = {
    "pothole": ("Pothole", "High", "Road Department", "Road pothole needs repair", "Large road damage detected."),
    "garbage": ("Garbage", "Medium", "Sanitation Department", "Garbage accumulation needs cleanup", "Garbage accumulation detected in a public area."),
    "water_leakage": ("Water Leakage", "High", "Water Department", "Water leakage needs urgent repair", "Water leakage detected and may require urgent repair."),
    "streetlight": ("Streetlight", "Medium", "Electrical Department", "Streetlight requires maintenance", "Streetlight issue detected near a public route."),
    "drainage": ("Drainage", "High", "Drainage Department", "Drainage blockage needs clearing", "Drainage blockage or overflow detected."),
}

CATEGORY_KEYWORDS = {
    "garbage": ("garbage", "trash", "waste", "bin", "bins", "dump", "dumping", "litter", "clean"),
    "water_leakage": ("water", "leak", "leakage", "pipe", "pipeline"),
    "streetlight": ("streetlight", "street light", "light", "lamp", "pole"),
    "drainage": ("drain", "drainage", "sewer", "gutter", "waterlog", "blocked"),
    "pothole": ("pothole", "road", "asphalt", "crack", "damage"),
}


def infer_category_from_text(value: str | None) -> str | None:
    text = (value or "").replace("_", " ").replace("-", " ").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return None


def fallback_analysis(category_hint: str | None = None, filename: str | None = None) -> AiAnalysisResponse:
    inferred_category = infer_category_from_text(filename) or (category_hint or "").lower()
    category, severity, department, title, description = FALLBACKS.get(inferred_category, FALLBACKS["pothole"])
    return AiAnalysisResponse(
        title=title,
        category=category,
        severity=severity,
        department=department,
        description=description,
        is_civic_issue=True,
        rejection_reason=None,
    )


def clean_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    return json.loads(cleaned)


def data_url_payload(value: str) -> tuple[str, str] | None:
    if not value.startswith("data:") or "," not in value:
        return None
    header, encoded = value.split(",", 1)
    mime_type = header.removeprefix("data:").split(";", 1)[0] or "image/jpeg"
    return mime_type, encoded


async def image_payload(value: str) -> tuple[str, str] | None:
    data_payload = data_url_payload(value)
    if data_payload is not None:
        return data_payload

    if value.startswith("http://") or value.startswith("https://"):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(value)
            response.raise_for_status()
        content_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"
        return content_type, base64.b64encode(response.content).decode("utf-8")

    return None


def fallback_resolution_verification(before_image: str, after_image: str) -> AiResolutionVerificationResponse:
    has_before = len(before_image.strip()) > 20
    has_after = len(after_image.strip()) > 20
    changed = before_image[:160] != after_image[:160] or len(before_image) != len(after_image)
    confidence = 94 if has_before and has_after and changed else 42
    return AiResolutionVerificationResponse(
        resolved=confidence >= 70,
        confidence=confidence,
        remarks=(
            "Before and after evidence show meaningful visual change. Repair can be sent for citizen confirmation."
            if confidence >= 70
            else "Before and after evidence do not show enough visible improvement. Additional work or clearer proof is required."
        ),
        visual_improvements=[
            "Before/after proof pair received",
            "Visible evidence changed between original and completion images" if changed else "Limited visual difference detected",
            "Ready for citizen confirmation" if confidence >= 70 else "Needs supervisor review",
        ],
        requires_rework=confidence < 70,
    )


def openai_model_name() -> str:
    return get_settings().openai_model.strip() or "gpt-4o-mini"


def openai_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().openai_api_key.strip()}",
        "Content-Type": "application/json",
    }


def image_url_content(mime_type: str, encoded: str, detail: str = "low") -> dict:
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{encoded}",
            "detail": detail,
        },
    }


def openai_error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response_text = exc.response.text[:500]
        return f"OpenAI API returned HTTP {exc.response.status_code}: {response_text}"
    if isinstance(exc, httpx.ConnectError):
        return "OpenAI API connection failed. Check backend internet access, DNS, firewall, or VPN."
    if isinstance(exc, httpx.TimeoutException):
        return "OpenAI API request timed out. Check backend internet access or try again."
    return f"OpenAI response parsing failed: {type(exc).__name__}"


async def analyze_issue_image(image: UploadFile, category_hint: str | None = None) -> AiAnalysisResponse:
    settings = get_settings()
    if not settings.openai_api_key:
        return fallback_analysis(category_hint, image.filename)

    image_bytes = await image.read()
    await image.seek(0)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Analyze this image for a civic complaint submission. Return only valid JSON with exactly these keys: "
        "is_civic_issue, title, category, severity, department, description, rejection_reason. "
        "Set is_civic_issue=false when the image is not visual evidence of a real public civic issue, "
        "for example handwritten notes, diagrams, screenshots, documents, memes, selfies, unrelated objects, or private non-public scenes. "
        "When is_civic_issue=false, set category='Invalid', severity='Low', department='Unassigned', "
        "title='Invalid civic evidence', description='Image is not valid civic issue evidence', and provide a short rejection_reason. "
        "When is_civic_issue=true, category must be one of Pothole, Garbage, Water Leakage, Streetlight, Drainage. "
        "Images of dustbins, trash cans, garbage containers, litter, dumping, or waste collection must be categorized as Garbage, not Pothole. "
        "Title must be a concise complaint title under 70 characters based on the visible problem. "
        "Description must be one clear sentence describing the visible issue, likely risk, and needed action. "
        "Severity must be Low, Medium, or High. Department must be Road Department, Sanitation Department, "
        "Water Department, Electrical Department, or Drainage Department. "
        f"User selected category hint: {category_hint or 'none'}. Use visual evidence first and do not copy the hint unless supported."
    )
    payload = {
        "model": openai_model_name(),
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_url_content(image.content_type or "image/jpeg", encoded, "high"),
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(OPENAI_CHAT_COMPLETIONS_URL, headers=openai_headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"]
        parsed = clean_json(text)
        filename_category = infer_category_from_text(image.filename)
        if filename_category and filename_category != infer_category_from_text(str(parsed.get("category", ""))):
            category, severity, department, title, description = FALLBACKS[filename_category]
            parsed.update(
                {
                    "title": title,
                    "category": category,
                    "severity": severity,
                    "department": department,
                    "description": description,
                }
            )
        return AiAnalysisResponse(
            title=str(parsed.get("title") or parsed.get("category") or "Civic issue"),
            category=str(parsed.get("category", "Pothole")),
            severity=str(parsed.get("severity", "High")),
            department=str(parsed.get("department", "Road Department")),
            description=str(parsed.get("description", "Large road damage detected.")),
            is_civic_issue=bool(parsed.get("is_civic_issue", True)),
            rejection_reason=(str(parsed.get("rejection_reason")) if parsed.get("rejection_reason") else None),
        )
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(openai_error_message(exc)) from exc


async def verify_resolution_images(before_image: str, after_image: str) -> AiResolutionVerificationResponse:
    settings = get_settings()
    try:
        before_payload = await image_payload(before_image)
        after_payload = await image_payload(after_image)
    except httpx.HTTPError:
        before_payload = None
        after_payload = None

    if not settings.openai_api_key or before_payload is None or after_payload is None:
        return fallback_resolution_verification(before_image, after_image)

    prompt = (
        "Compare these two civic repair images. Image 1 is the original citizen complaint. "
        "Image 2 is the worker completion proof. Return only valid JSON with exactly these keys: "
        "resolved (boolean), confidence (integer 0-100), remarks (string), visual_improvements (array of strings), "
        "requires_rework (boolean). Judge whether the original civic issue appears actually repaired. "
        "The confidence field means repair completion confidence, not confidence in your analysis. "
        "Use high confidence only when Image 2 clearly resolves the same issue shown in Image 1. "
        "If images show different issue types or different locations, set resolved=false, requires_rework=true, "
        "and confidence between 0 and 20."
    )
    payload = {
        "model": openai_model_name(),
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_url_content(before_payload[0], before_payload[1]),
                    image_url_content(after_payload[0], after_payload[1]),
                ],
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(OPENAI_CHAT_COMPLETIONS_URL, headers=openai_headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        parsed = clean_json(data["choices"][0]["message"]["content"])
        confidence = max(0, min(100, int(parsed.get("confidence", 0))))
        resolved = bool(parsed.get("resolved", confidence >= 70))
        requires_rework = bool(parsed.get("requires_rework", not resolved or confidence < 70))
        remarks = str(parsed.get("remarks", "AI verification completed."))
        mismatch_terms = ("different civic issues", "different issue", "different location", "not been repaired", "not repaired", "not been addressed", "error in providing")
        if not resolved or requires_rework or any(term in remarks.lower() for term in mismatch_terms):
            confidence = min(confidence, 20)
            resolved = False
            requires_rework = True
        return AiResolutionVerificationResponse(
            resolved=resolved,
            confidence=confidence,
            remarks=remarks,
            visual_improvements=[str(item) for item in parsed.get("visual_improvements", [])][:6],
            requires_rework=requires_rework,
        )
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError):
        return fallback_resolution_verification(before_image, after_image)
