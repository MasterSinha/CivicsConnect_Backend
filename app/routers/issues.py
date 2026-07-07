from math import atan2, cos, radians, sin, sqrt
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Issue, IssueCategory, IssueSeverity, IssueStatus, User
from app.schemas import IssueDetail, IssueOut, MapIssue
from app.services.routing import department_for_issue, route_issue_to_authority
from app.storage import save_upload_file

router = APIRouter(prefix="/issues", tags=["issues"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def infer_severity(category: IssueCategory) -> IssueSeverity:
    if category in {IssueCategory.water_leakage, IssueCategory.drainage}:
        return IssueSeverity.high
    if category in {IssueCategory.pothole, IssueCategory.streetlight}:
        return IssueSeverity.medium
    return IssueSeverity.low


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return earth_radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def save_upload(image: UploadFile | None) -> str | None:
    if image is None or not image.filename:
        return None
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPG, PNG, and WebP images are allowed")

    return save_upload_file(image, prefix="issue-")


@router.post("", response_model=IssueOut, status_code=status.HTTP_201_CREATED)
def create_issue(
    title: str = Form(min_length=3, max_length=180),
    description: str = Form(min_length=1),
    latitude: float = Form(),
    longitude: float = Form(),
    category: IssueCategory = Form(),
    ai_category: str | None = Form(default=None),
    ai_severity: str | None = Form(default=None),
    ai_department: str | None = Form(default=None),
    ai_description: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Issue:
    image_url = save_upload(image)
    issue = Issue(
        title=title.strip(),
        description=description.strip(),
        image_url=image_url,
        latitude=latitude,
        longitude=longitude,
        category=category,
        severity=infer_severity(category),
        ai_category=ai_category,
        ai_severity=ai_severity,
        ai_department=ai_department,
        ai_description=ai_description,
        reporter_id=user.id,
    )

    db.add(issue)
    db.flush()
    route_issue_to_authority(db, issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("", response_model=list[IssueOut])
def list_issues(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Issue]:
    if user.role.value == "citizen":
        return list(db.scalars(select(Issue).where(Issue.reporter_id == user.id).order_by(Issue.created_at.desc())).all())
    return list(db.scalars(select(Issue).order_by(Issue.created_at.desc())).all())


@router.get("/nearby", response_model=list[IssueOut])
def nearby_issues(
    latitude: float = Query(),
    longitude: float = Query(),
    radius_km: float = Query(default=10.0, gt=0, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Issue]:
    issues = list(
        db.scalars(
            select(Issue)
            .where(or_(Issue.reporter_id.is_(None), Issue.reporter_id != user.id))
            .order_by(Issue.created_at.desc())
        ).all()
    )
    return [
        issue
        for issue in issues
        if distance_km(latitude, longitude, issue.latitude, issue.longitude) <= radius_km
    ]


def build_timeline(issue: Issue) -> list[dict]:
    department = department_for_issue(issue)
    stage_offsets = [0, 1, 2, 3, 5]
    completed_until = 1
    if issue.verified_count > 0:
        completed_until = 2
    if issue.status == IssueStatus.in_review:
        completed_until = 4
    if issue.status == IssueStatus.resolved:
        completed_until = 5

    resolution_remark = issue.resolution_public_note or issue.resolution_summary or "Issue resolved and marked closed."
    if issue.resolution_worker:
        resolution_remark = f"{resolution_remark} Completed by {issue.resolution_worker}."

    remarks = [
        "Citizen report received with location and evidence.",
        f"Verified by {issue.verified_count} community users.",
        f"Assigned to {department} for field inspection.",
        "Field team review is in progress.",
        resolution_remark,
    ]
    stages = ["Reported", "Verified", "Assigned", "In Progress", "Resolved"]

    return [
        {
            "stage": stage,
            "date": (issue.resolution_date if stage == "Resolved" and issue.resolution_date else issue.created_at + timedelta(days=stage_offsets[index])).strftime("%d %b %Y"),
            "time": (issue.created_at + timedelta(hours=index * 2)).strftime("%I:%M %p"),
            "department": department,
            "remarks": remarks[index],
            "completed": index < completed_until,
        }
        for index, stage in enumerate(stages)
    ]


@router.get("/map", response_model=list[MapIssue])
def map_issues(db: Session = Depends(get_db)) -> list[dict]:
    issues = list(db.scalars(select(Issue).order_by(Issue.created_at.desc())).all())
    return [
        {
            "id": issue.id,
            "title": issue.title,
            "image_url": issue.image_url,
            "latitude": issue.latitude,
            "longitude": issue.longitude,
            "status": issue.status,
            "severity": issue.severity,
            "category": issue.category,
            "votes": issue.votes,
            "verified_count": issue.verified_count,
            "trust_score": issue.trust_score,
            "distance": round(abs(issue.latitude - 28.6139) * 69 + abs(issue.longitude - 77.2090) * 69, 1),
            "created_at": issue.created_at,
        }
        for issue in issues
    ]


@router.get("/{issue_id}", response_model=IssueDetail)
def get_issue(issue_id: UUID, db: Session = Depends(get_db)) -> dict:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    payload = IssueOut.model_validate(issue).model_dump()
    payload["timeline"] = build_timeline(issue)
    return payload


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issue(
    issue_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if user.role.value == "citizen" and issue.reporter_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can delete only your own report")

    db.delete(issue)
    db.commit()
