from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/livez")
def livez() -> dict:
    return {"ok": True}


@router.get("/readyz")
def readyz() -> dict:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    finally:
        db.close()
