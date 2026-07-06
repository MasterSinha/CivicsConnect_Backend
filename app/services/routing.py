import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthorityProfile, Issue, IssueAssignment, IssueCategory, User, UserRole


DEFAULT_AUTHORITY_RADIUS_KM = 20.0

DEPARTMENT_BY_CATEGORY = {
    IssueCategory.pothole: "Road Department",
    IssueCategory.garbage: "Sanitation Department",
    IssueCategory.water_leakage: "Water Department",
    IssueCategory.streetlight: "Electrical Department",
    IssueCategory.drainage: "Drainage Department",
}

DEFAULT_PROFILE_BY_DEPARTMENT = {
    "Road Department": ("Central Road Zone", 28.6139, 77.2090),
    "Sanitation Department": ("Central Sanitation Zone", 28.6200, 77.2100),
    "Water Department": ("Central Water Zone", 28.6030, 77.2300),
    "Electrical Department": ("Central Electrical Zone", 28.6150, 77.2200),
    "Drainage Department": ("East Drainage Zone", 28.6270, 77.2800),
}


def department_for_issue(issue: Issue) -> str:
    return issue.ai_department or DEPARTMENT_BY_CATEGORY[issue.category]


def distance_km(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat_b - lat_a)
    d_lng = math.radians(lng_b - lng_a)
    a_lat = math.radians(lat_a)
    b_lat = math.radians(lat_b)
    haversine = math.sin(d_lat / 2) ** 2 + math.cos(a_lat) * math.cos(b_lat) * math.sin(d_lng / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def default_department_for_user(user: User) -> str:
    email = user.email.lower()
    if "sanitation" in email or "garbage" in email:
        return "Sanitation Department"
    if "water" in email:
        return "Water Department"
    if "electrical" in email or "streetlight" in email:
        return "Electrical Department"
    if "drainage" in email:
        return "Drainage Department"
    return "Road Department"


def ensure_authority_profile(db: Session, user: User) -> AuthorityProfile:
    profile = db.scalar(select(AuthorityProfile).where(AuthorityProfile.user_id == user.id))
    if profile:
        return profile

    department = default_department_for_user(user)
    zone, latitude, longitude = DEFAULT_PROFILE_BY_DEPARTMENT[department]
    profile = AuthorityProfile(
        user_id=user.id,
        department=department,
        zone=zone,
        latitude=latitude,
        longitude=longitude,
        radius_km=DEFAULT_AUTHORITY_RADIUS_KM,
    )
    db.add(profile)
    db.flush()
    return profile


def seed_missing_authority_profiles(db: Session) -> None:
    authorities = list(db.scalars(select(User).where(User.role.in_([UserRole.authority, UserRole.admin]))).all())
    for authority in authorities:
        ensure_authority_profile(db, authority)


def route_issue_to_authority(db: Session, issue: Issue) -> IssueAssignment | None:
    department = department_for_issue(issue)
    seed_missing_authority_profiles(db)
    profiles = list(db.scalars(select(AuthorityProfile).where(AuthorityProfile.department == department)).all())
    if not profiles:
        profiles = list(db.scalars(select(AuthorityProfile)).all())
    if not profiles:
        return None

    ranked = sorted(
        ((profile, distance_km(issue.latitude, issue.longitude, profile.latitude, profile.longitude)) for profile in profiles),
        key=lambda item: item[1],
    )
    in_radius = next((item for item in ranked if item[1] <= item[0].radius_km), None)
    profile, distance = in_radius or ranked[0]

    assignment = db.scalar(select(IssueAssignment).where(IssueAssignment.issue_id == issue.id))
    if assignment is None:
        assignment = IssueAssignment(issue_id=issue.id)
        db.add(assignment)

    assignment.authority_id = profile.user_id
    assignment.authority_profile_id = profile.id
    assignment.department = department
    assignment.distance_km = round(distance, 1)
    assignment.routed_by_fallback = in_radius is None
    return assignment


def route_unassigned_issues(db: Session) -> int:
    seed_missing_authority_profiles(db)
    unassigned_issues = list(
        db.scalars(
            select(Issue)
            .outerjoin(IssueAssignment, IssueAssignment.issue_id == Issue.id)
            .where(IssueAssignment.id.is_(None))
        ).all()
    )
    routed = 0
    for issue in unassigned_issues:
        if route_issue_to_authority(db, issue) is not None:
            routed += 1
    return routed
