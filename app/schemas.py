from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import IssueCategory, IssueSeverity, IssueStatus, UserRole


class UserOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    phone_number: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone_number: str = Field(min_length=7, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.citizen
    department: str | None = Field(default=None, max_length=120)
    zone: str | None = Field(default=None, max_length=160)
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float = Field(default=20.0, ge=1, le=100)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info):
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    username: str = Field(min_length=2, max_length=255)


class ResetPasswordRequest(ForgotPasswordRequest):
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def reset_passwords_match(cls, value: str, info):
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"


class AuthorityProfileUpdate(BaseModel):
    department: str | None = Field(default=None, max_length=120)
    zone: str | None = Field(default=None, max_length=160)
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = Field(default=None, ge=1, le=100)


class AuthorityWorkerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    department: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=32)
    role_label: str | None = Field(default=None, max_length=120)


class AuthorityWorkerOut(BaseModel):
    id: UUID
    authority_id: UUID
    department: str
    name: str
    phone_number: str | None
    role_label: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class IssueAssignmentRequest(BaseModel):
    field_worker: str | None = Field(default=None, max_length=160)
    priority: str | None = Field(default=None, max_length=40)
    eta: date | None = None


class DashboardMetric(BaseModel):
    label: str
    value: int
    trend: str


class RecentIssue(BaseModel):
    id: str
    title: str
    category: str
    status: str
    location: str
    reported_at: str


class AiInsight(BaseModel):
    title: str
    summary: str
    confidence: int


class CommunityScore(BaseModel):
    infrastructure: int
    cleanliness: int
    response: int


class LinePoint(BaseModel):
    label: str
    issues: int


class PieSlice(BaseModel):
    label: str
    value: int
    color: str


class DashboardResponse(BaseModel):
    total_issues: int
    resolved_issues: int
    pending_issues: int
    nearby_issues: int
    community_score: int
    recent_issues: list[RecentIssue]
    ai_insights: list[AiInsight]
    community_health: CommunityScore
    line_chart: list[LinePoint]
    pie_chart: list[PieSlice]


class IssueOut(BaseModel):
    id: UUID
    title: str
    description: str
    image_url: str | None
    latitude: float
    longitude: float
    status: IssueStatus
    severity: IssueSeverity
    category: IssueCategory
    ai_category: str | None
    ai_severity: str | None
    ai_department: str | None
    ai_description: str | None
    votes: int
    verified_count: int
    trust_score: int
    resolution_summary: str | None = None
    resolution_public_note: str | None = None
    resolution_worker: str | None = None
    resolution_date: date | None = None
    resolution_materials: str | None = None
    resolution_before_image: str | None = None
    resolution_after_image: str | None = None
    ai_resolution_resolved: bool | None = None
    ai_resolution_confidence: int | None = None
    ai_resolution_remarks: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IssueTimelineStep(BaseModel):
    stage: str
    date: str
    time: str
    department: str
    remarks: str
    completed: bool


class IssueDetail(IssueOut):
    timeline: list[IssueTimelineStep]


class IssueResolutionRequest(BaseModel):
    summary: str = Field(min_length=10, max_length=2000)
    public_note: str | None = Field(default=None, max_length=2000)
    field_worker: str = Field(min_length=2, max_length=160)
    completion_date: date
    materials: str | None = Field(default=None, max_length=255)
    before_image: str | None = None
    after_image: str | None = None
    ai_resolved: bool | None = None
    ai_confidence: int | None = Field(default=None, ge=0, le=100)
    ai_remarks: str | None = Field(default=None, max_length=2000)


class AiResolutionVerificationRequest(BaseModel):
    before_image: str = Field(min_length=10)
    after_image: str = Field(min_length=10)


class AiResolutionVerificationResponse(BaseModel):
    resolved: bool
    confidence: int = Field(ge=0, le=100)
    remarks: str
    visual_improvements: list[str] = []
    requires_rework: bool = False


class VoteOut(BaseModel):
    id: UUID
    issue_id: UUID
    user_id: UUID | None = None
    user_label: str
    vote_type: str
    evidence_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentOut(BaseModel):
    id: UUID
    issue_id: UUID
    user_label: str
    body: str
    evidence_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationResponse(BaseModel):
    issue: IssueOut
    vote: VoteOut


class CommentResponse(BaseModel):
    issue: IssueOut
    comment: CommentOut


class AiAnalysisResponse(BaseModel):
    title: str
    category: str
    severity: str
    department: str
    description: str
    is_civic_issue: bool = True
    rejection_reason: str | None = None


class MapIssue(BaseModel):
    id: UUID
    title: str
    image_url: str | None
    latitude: float
    longitude: float
    status: IssueStatus
    severity: IssueSeverity
    category: IssueCategory
    votes: int
    verified_count: int
    trust_score: int
    distance: float
    created_at: datetime

    model_config = {"from_attributes": True}
