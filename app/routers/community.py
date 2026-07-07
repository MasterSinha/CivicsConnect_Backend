from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Comment, Issue, User, Vote
from app.schemas import CommentResponse, IssueOut, VerificationResponse
from app.storage import save_upload_file

router = APIRouter(tags=["community"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def save_evidence(evidence: UploadFile | None) -> str | None:
    if evidence is None or not evidence.filename:
        return None
    if evidence.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPG, PNG, and WebP evidence is allowed")

    try:
        return save_upload_file(evidence, prefix="evidence-")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/verify", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
def verify_issue(
    issue_id: UUID = Form(),
    user_label: str = Form(default="Community Member"),
    vote_type: str = Form(default="verify"),
    evidence: UploadFile | None = File(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerificationResponse:
    if vote_type not in {"upvote", "verify"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported verification action")

    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if issue.reporter_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot verify your own report")
    existing_vote = db.scalar(
        select(Vote).where(
            Vote.issue_id == issue.id,
            Vote.user_id == user.id,
            Vote.vote_type == vote_type,
        )
    )
    if existing_vote is not None:
        action = "verified" if vote_type == "verify" else "upvoted"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"You already {action} this report")

    evidence_url = save_evidence(evidence)
    vote = Vote(issue_id=issue.id, user_id=user.id, user_label=user.name, vote_type=vote_type, evidence_url=evidence_url)
    issue.votes += 1
    if vote_type == "verify":
        issue.verified_count += 1
    issue.trust_score = min(99, 72 + issue.verified_count + min(issue.votes, 20))

    db.add(vote)
    db.commit()
    db.refresh(issue)
    db.refresh(vote)
    return VerificationResponse(issue=IssueOut.model_validate(issue), vote=vote)


@router.post("/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    issue_id: UUID = Form(),
    body: str = Form(min_length=2),
    user_label: str = Form(default="Community Member"),
    evidence: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> CommentResponse:
    evidence_url = save_evidence(evidence)
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    comment = Comment(issue_id=issue.id, user_label=user_label.strip() or "Community Member", body=body.strip(), evidence_url=evidence_url)
    issue.trust_score = min(99, issue.trust_score + 1)

    db.add(comment)
    db.commit()
    db.refresh(issue)
    db.refresh(comment)
    return CommentResponse(issue=IssueOut.model_validate(issue), comment=comment)
