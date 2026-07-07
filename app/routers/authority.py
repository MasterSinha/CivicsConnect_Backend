from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import AuthorityProfile, Issue, IssueAssignment, IssueSeverity, IssueStatus, User, UserRole
from app.schemas import AuthorityProfileUpdate, IssueResolutionRequest
from app.services.routing import ensure_authority_profile, route_eligible_issues_to_profile, route_unassigned_issues

router = APIRouter(tags=["authority"])


def status_label(issue: Issue) -> str:
    if issue.status == IssueStatus.resolved:
        return "Resolved"
    if issue.status == IssueStatus.in_review:
        return "In Progress"
    return "Reported"


def severity_label(issue: Issue) -> str:
    if issue.severity == IssueSeverity.high:
        return "Critical"
    if issue.severity == IssueSeverity.medium:
        return "High"
    return "Medium"


def display_issue_id(issue: Issue) -> str:
    return f"C{1000 + (int(issue.id.hex[-6:], 16) % 9000)}"


def relative_time(value: datetime) -> str:
    now = datetime.now(value.tzinfo)
    delta = now - value
    if delta < timedelta(minutes=1):
        return "Just now"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)} min ago"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)} hr ago"
    return value.strftime("%d %b, %H:%M")


def issue_payload(issue: Issue, assignment: IssueAssignment) -> dict:
    return {
        "id": str(issue.id),
        "display_id": display_issue_id(issue),
        "title": issue.title,
        "category": issue.ai_category or issue.category.value.replace("_", " ").title(),
        "severity": severity_label(issue),
        "citizen": "Registered Citizen",
        "department": assignment.department,
        "status": status_label(issue),
        "created_date": issue.created_at.strftime("%d %b %Y"),
        "created_time": issue.created_at.strftime("%I:%M %p"),
        "location": f"{issue.latitude:.4f}, {issue.longitude:.4f}",
        "votes": issue.votes,
        "verification_count": issue.verified_count,
        "distance": assignment.distance_km,
        "image_url": issue.image_url,
        "reporter_phone": "+91 98765 43210",
        "description": issue.description,
        "resolution_summary": issue.resolution_summary,
        "resolution_public_note": issue.resolution_public_note,
        "resolution_worker": issue.resolution_worker,
        "resolution_date": issue.resolution_date.isoformat() if issue.resolution_date else None,
        "resolution_materials": issue.resolution_materials,
        "resolution_before_image": issue.resolution_before_image,
        "resolution_after_image": issue.resolution_after_image,
        "ai_resolution_resolved": issue.ai_resolution_resolved,
        "ai_resolution_confidence": issue.ai_resolution_confidence,
        "ai_resolution_remarks": issue.ai_resolution_remarks,
        "latitude": issue.latitude,
        "longitude": issue.longitude,
        "assigned_authority_id": str(assignment.authority_id),
        "assigned_department": assignment.department,
        "authority_distance_km": assignment.distance_km,
        "routed_by_fallback": assignment.routed_by_fallback,
    }


def assigned_issue_rows(db: Session, user: User) -> list[tuple[Issue, IssueAssignment]]:
    return list(
        db.execute(
            select(Issue, IssueAssignment)
            .join(IssueAssignment, IssueAssignment.issue_id == Issue.id)
            .where(IssueAssignment.authority_id == user.id)
            .order_by(Issue.created_at.desc())
        ).all()
    )


def profile_payload(profile: AuthorityProfile, user: User) -> dict:
    return {
        "id": str(profile.id),
        "user_id": str(user.id),
        "name": user.name,
        "department": profile.department,
        "zone": profile.zone,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
        "radius_km": profile.radius_km,
    }


@router.get("/authority/profile")
def authority_profile(
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    profile = ensure_authority_profile(db, user)
    db.commit()
    return profile_payload(profile, user)


@router.put("/authority/profile")
def update_authority_profile(
    payload: AuthorityProfileUpdate,
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    profile = ensure_authority_profile(db, user)
    if payload.department is not None:
        profile.department = payload.department.strip()
    if payload.zone is not None:
        profile.zone = payload.zone.strip()
    if payload.latitude is not None:
        profile.latitude = payload.latitude
    if payload.longitude is not None:
        profile.longitude = payload.longitude
    if payload.radius_km is not None:
        profile.radius_km = payload.radius_km
    route_unassigned_issues(db)
    route_eligible_issues_to_profile(db, profile)
    db.commit()
    return profile_payload(profile, user)


@router.get("/authority/dashboard")
def authority_dashboard(
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    profile = ensure_authority_profile(db, user)
    route_unassigned_issues(db)
    route_eligible_issues_to_profile(db, profile)
    rows = assigned_issue_rows(db, user)
    issues = [issue for issue, _ in rows]
    total = len(issues)
    pending = len([issue for issue in issues if issue.status == IssueStatus.pending])
    in_progress = len([issue for issue in issues if issue.status == IssueStatus.in_review])
    resolved = len([issue for issue in issues if issue.status == IssueStatus.resolved])
    critical = len([issue for issue in issues if issue.severity == IssueSeverity.high])
    fallback_count = len([assignment for _, assignment in rows if assignment.routed_by_fallback])
    today = date.today()
    resolution_rate = []
    for months_back in range(4, -1, -1):
        month = today.month - months_back
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        month_issues = [issue for issue in issues if issue.created_at.year == year and issue.created_at.month == month]
        resolution_rate.append(
            {
                "month": date(year, month, 1).strftime("%b"),
                "resolved": len([issue for issue in month_issues if issue.status == IssueStatus.resolved]),
                "pending": len([issue for issue in month_issues if issue.status != IssueStatus.resolved]),
            }
        )
    db.commit()

    return {
        "kpis": {
            "total_issues": {"count": total, "change": 0},
            "open_issues": {"count": pending, "change": 0},
            "in_progress": {"count": in_progress, "change": 0},
            "resolved_issues": {"count": resolved, "change": 0},
            "critical": {"count": critical, "change": 0},
        },
        "resolution_rate": resolution_rate,
        "department_performance": [
            {
                "department": profile.department,
                "total": max(total, 1),
                "resolved": resolved,
                "avg_response": f"{fallback_count} fallback" if fallback_count else "direct",
            }
        ],
        "notifications": [
            {
                "title": "New routed complaint",
                "detail": f"{assignment.department} received {display_issue_id(issue)}{' by nearest-authority fallback' if assignment.routed_by_fallback else ''}",
                "time": relative_time(issue.created_at),
            }
            for index, (issue, assignment) in enumerate(rows[:3])
        ],
    }


@router.get("/authority/issues")
def authority_issues(
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[dict]:
    profile = ensure_authority_profile(db, user)
    route_unassigned_issues(db)
    route_eligible_issues_to_profile(db, profile)
    rows = assigned_issue_rows(db, user)
    db.commit()
    return [issue_payload(issue, assignment) for issue, assignment in rows]


@router.put("/issues/{issue_id}/assign")
def assign_issue(
    issue_id: UUID,
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    assignment = db.scalar(select(IssueAssignment).where(IssueAssignment.issue_id == issue_id, IssueAssignment.authority_id == user.id))
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned issue not found")
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if issue.status != IssueStatus.resolved:
        issue.status = IssueStatus.in_review
    db.commit()
    return {"issue_id": str(issue_id), "message": "Issue assignment updated successfully"}


@router.put("/issues/{issue_id}/status")
def update_issue_status(
    issue_id: UUID,
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    return assign_issue(issue_id, user, db)


@router.post("/issues/{issue_id}/resolution")
def create_resolution(
    issue_id: UUID,
    payload: IssueResolutionRequest,
    user: User = Depends(require_roles(UserRole.authority, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict:
    assignment = db.scalar(select(IssueAssignment).where(IssueAssignment.issue_id == issue_id, IssueAssignment.authority_id == user.id))
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned issue not found")
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    issue.status = IssueStatus.resolved
    issue.resolution_summary = payload.summary.strip()
    issue.resolution_public_note = (payload.public_note or "").strip() or None
    issue.resolution_worker = payload.field_worker.strip()
    issue.resolution_date = payload.completion_date
    issue.resolution_materials = (payload.materials or "").strip() or None
    issue.resolution_before_image = payload.before_image
    issue.resolution_after_image = payload.after_image
    issue.ai_resolution_resolved = payload.ai_resolved
    issue.ai_resolution_confidence = payload.ai_confidence
    issue.ai_resolution_remarks = (payload.ai_remarks or "").strip() or None
    db.commit()
    return {
        "issue_id": str(issue_id),
        "message": "Resolution proof uploaded successfully",
        "completion_date": payload.completion_date.isoformat(),
        "ai_confidence": payload.ai_confidence,
    }
