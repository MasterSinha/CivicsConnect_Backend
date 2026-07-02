from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from app.schemas import AuthResponse, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.services.routing import DEFAULT_AUTHORITY_RADIUS_KM, ensure_authority_profile

router = APIRouter(prefix="/auth", tags=["auth"])


def set_auth_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        phone_number=payload.phone_number.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    if user.role in {UserRole.authority, UserRole.admin}:
        profile = ensure_authority_profile(db, user)
        if payload.department:
            profile.department = payload.department
        if payload.zone:
            profile.zone = payload.zone
        if payload.latitude is not None:
            profile.latitude = payload.latitude
        if payload.longitude is not None:
            profile.longitude = payload.longitude
        profile.radius_km = payload.radius_km or DEFAULT_AUTHORITY_RADIUS_KM
    db.commit()
    db.refresh(user)

    minutes = get_settings().jwt_access_token_expire_minutes
    token = create_access_token(user.id, user.role.value, minutes)
    set_auth_cookie(response, token, minutes * 60)
    return AuthResponse(user=UserOut.model_validate(user), access_token=token, token_type="bearer")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    settings = get_settings()
    if payload.remember_me:
        max_age = int(timedelta(days=settings.jwt_remember_me_expire_days).total_seconds())
        minutes = settings.jwt_remember_me_expire_days * 24 * 60
    else:
        max_age = settings.jwt_access_token_expire_minutes * 60
        minutes = settings.jwt_access_token_expire_minutes

    token = create_access_token(user.id, user.role.value, minutes)
    set_auth_cookie(response, token, max_age)
    return AuthResponse(user=UserOut.model_validate(user), access_token=token, token_type="bearer")


def find_user_by_username(db: Session, username: str) -> User | None:
    value = username.strip().lower()
    return db.scalars(
        select(User).where(
            or_(
                func.lower(User.email) == value,
                func.lower(User.name) == value,
                User.phone_number == username.strip(),
            )
        )
    ).first()


@router.post("/forgot-password/check")
def forgot_password_check(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = find_user_by_username(db, payload.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found for this username")
    return {"message": "Account found. Enter a new password.", "user_id": str(user.id), "name": user.name}


@router.post("/forgot-password")
def forgot_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = find_user_by_username(db, payload.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found for this username")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"message": "Password updated successfully. You can sign in with the new password."}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
