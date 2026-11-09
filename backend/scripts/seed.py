import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import Contact, Elder, Medicine
from app.timeutil import utcnow


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.scalar(select(Elder).where(Elder.name == "Kunjamma Menon"))
        if existing is not None:
            elder = existing
        else:
            elder = Elder(
                name="Kunjamma Menon",
                phone="",
                timezone="Asia/Kolkata",
                check_in_times=["08:30", "19:00"],
                consent_at=utcnow(),
            )
            elder.contacts = [
                Contact(
                    name="Anita (daughter, Dubai)",
                    email="",
                    channel="dashboard",
                    priority=1,
                    timezone="Asia/Dubai",
                ),
                Contact(
                    name="Rahul (son, London)",
                    email="",
                    channel="dashboard",
                    priority=2,
                    timezone="Europe/London",
                ),
            ]
            elder.medicines = [
                Medicine(name="Amlodipine", time_of_day="08:00"),
                Medicine(name="Metformin", time_of_day="19:00"),
            ]
            db.add(elder)
            db.commit()
        base = get_settings().frontend_base_url.rstrip("/")
        print(f"Elder id: {elder.id}")
        print(f"Simulator link: {base}/simulator/{elder.access_token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
