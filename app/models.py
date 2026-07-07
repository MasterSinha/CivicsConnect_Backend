import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, enum.Enum):
    citizen = "citizen"
    authority = "authority"
    admin = "admin"


class IssueStatus(str, enum.Enum):
    pending = "pending"
    in_review = "in_review"
    resolved = "resolved"


class IssueSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class IssueCategory(str, enum.Enum):
    pothole = "pothole"
    garbage = "garbage"
    water_leakage = "water_leakage"
    streetlight = "streetlight"
    drainage = "drainage"


class AuthorityDepartment(str, enum.Enum):
    road = "Road Department"
    sanitation = "Sanitation Department"
    water = "Water Department"
    electrical = "Electrical Department"
    drainage = "Drainage Department"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.citizen, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus, name="issue_status"), default=IssueStatus.pending, index=True, nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(Enum(IssueSeverity, name="issue_severity"), default=IssueSeverity.medium, nullable=False)
    category: Mapped[IssueCategory] = mapped_column(Enum(IssueCategory, name="issue_category"), index=True, nullable=False)
    ai_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ai_severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ai_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    votes: Mapped[int] = mapped_column(default=0, nullable=False)
    verified_count: Mapped[int] = mapped_column(default=0, nullable=False)
    trust_score: Mapped[int] = mapped_column(default=72, nullable=False)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_public_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_worker: Mapped[str | None] = mapped_column(String(160), nullable=True)
    resolution_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolution_materials: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_before_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_after_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_resolution_resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_resolution_confidence: Mapped[int | None] = mapped_column(nullable=True)
    ai_resolution_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthorityProfile(Base):
    __tablename__ = "authority_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    zone: Mapped[str] = mapped_column(String(160), default="Central Civic Zone", nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IssueAssignment(Base):
    __tablename__ = "issue_assignments"
    __table_args__ = (UniqueConstraint("issue_id", name="uq_issue_assignment_issue_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), index=True, nullable=False)
    authority_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    authority_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    routed_by_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    field_worker: Mapped[str | None] = mapped_column(String(160), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(40), nullable=True)
    eta: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthorityWorker(Base):
    __tablename__ = "authority_workers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("issue_id", "user_id", "vote_type", name="uq_votes_issue_user_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    user_label: Mapped[str] = mapped_column(String(120), default="Community Member", nullable=False)
    vote_type: Mapped[str] = mapped_column(String(24), default="upvote", nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_label: Mapped[str] = mapped_column(String(120), default="Community Member", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
