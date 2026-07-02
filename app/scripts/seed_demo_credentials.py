from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password
from app.services.routing import DEFAULT_AUTHORITY_RADIUS_KM, ensure_authority_profile


DEMO_ACCOUNTS = [
    {
        "name": "Normal User",
        "email": "citizen@civicconnect.ai",
        "phone": "+91 90000 00001",
        "password": "citizen123",
        "role": UserRole.citizen,
    },
    {
        "name": "Road Authority Officer",
        "email": "authority@civicconnect.ai",
        "phone": "+91 90000 00002",
        "password": "authority123",
        "role": UserRole.authority,
        "department": "Road Department",
        "zone": "Central Civic Zone",
        "latitude": 28.6139,
        "longitude": 77.2090,
    },
    {
        "name": "Sanitation Authority Officer",
        "email": "sanitation@civicconnect.ai",
        "phone": "+91 90000 00003",
        "password": "authority123",
        "role": UserRole.authority,
        "department": "Sanitation Department",
        "zone": "Central Sanitation Zone",
        "latitude": 28.6200,
        "longitude": 77.2100,
    },
    {
        "name": "Water Authority Officer",
        "email": "water@civicconnect.ai",
        "phone": "+91 90000 00004",
        "password": "authority123",
        "role": UserRole.authority,
        "department": "Water Department",
        "zone": "Central Water Zone",
        "latitude": 28.6030,
        "longitude": 77.2300,
    },
    {
        "name": "Electrical Authority Officer",
        "email": "electrical@civicconnect.ai",
        "phone": "+91 90000 00005",
        "password": "authority123",
        "role": UserRole.authority,
        "department": "Electrical Department",
        "zone": "Central Electrical Zone",
        "latitude": 28.6150,
        "longitude": 77.2200,
    },
    {
        "name": "Drainage Authority Officer",
        "email": "drainage@civicconnect.ai",
        "phone": "+91 90000 00006",
        "password": "authority123",
        "role": UserRole.authority,
        "department": "Drainage Department",
        "zone": "East Drainage Zone",
        "latitude": 28.6270,
        "longitude": 77.2800,
    },
]


def upsert_account(db, account: dict[str, object]) -> str:
    email = str(account["email"]).lower()
    role = account["role"]
    user = db.scalar(select(User).where(User.email == email))

    if user:
        user.name = str(account["name"])
        user.phone_number = str(account["phone"])
        user.password_hash = hash_password(str(account["password"]))
        user.role = role
        action = "updated"
    else:
        user = User(
            name=str(account["name"]),
            email=email,
            phone_number=str(account["phone"]),
            password_hash=hash_password(str(account["password"])),
            role=role,
        )
        db.add(user)
        action = "created"

    db.flush()

    if role in {UserRole.authority, UserRole.admin}:
        profile = ensure_authority_profile(db, user)
        profile.department = str(account["department"])
        profile.zone = str(account["zone"])
        profile.latitude = float(account["latitude"])
        profile.longitude = float(account["longitude"])
        profile.radius_km = float(account.get("radius_km", DEFAULT_AUTHORITY_RADIUS_KM))

    return f"{action}: {email} ({role.value})"


def main() -> None:
    with SessionLocal() as db:
        results = [upsert_account(db, account) for account in DEMO_ACCOUNTS]
        db.commit()

    print("Demo credentials ready:")
    for result in results:
        print(f"- {result}")


if __name__ == "__main__":
    main()
