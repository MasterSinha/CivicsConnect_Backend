import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password
from app.services.routing import DEFAULT_AUTHORITY_RADIUS_KM, ensure_authority_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a CivicConnect PostgreSQL user.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", default="+91 00000 00000")
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", choices=[role.value for role in UserRole], default=UserRole.citizen.value)
    parser.add_argument("--department", default=None)
    parser.add_argument("--zone", default=None)
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--longitude", type=float, default=None)
    parser.add_argument("--radius-km", type=float, default=DEFAULT_AUTHORITY_RADIUS_KM)
    args = parser.parse_args()

    with SessionLocal() as db:
        email = args.email.lower()
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.name = args.name
            user.phone_number = args.phone
            user.password_hash = hash_password(args.password)
            user.role = UserRole(args.role)
            action = "updated"
        else:
            user = User(
                name=args.name,
                email=email,
                phone_number=args.phone,
                password_hash=hash_password(args.password),
                role=UserRole(args.role),
            )
            db.add(user)
            action = "created"
        if user.role in {UserRole.authority, UserRole.admin}:
            profile = ensure_authority_profile(db, user)
            if args.department:
                profile.department = args.department
            if args.zone:
                profile.zone = args.zone
            if args.latitude is not None:
                profile.latitude = args.latitude
            if args.longitude is not None:
                profile.longitude = args.longitude
            profile.radius_km = args.radius_km
        db.commit()
        print(f"User {action}: {email} ({args.role})")


if __name__ == "__main__":
    main()
