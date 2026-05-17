from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GuardrailPolicy
from app.db.schemas import PolicyCreate, PolicyOut
from app.db.session import get_db

router = APIRouter(prefix="/policies", tags=["policies"])


def _to_out(policy: GuardrailPolicy) -> PolicyOut:
    return PolicyOut(
        id=policy.id,
        name=policy.name,
        min_quality_score=policy.min_quality_score,
        max_hallucination_score=policy.max_hallucination_score,
        max_toxicity_score=policy.max_toxicity_score,
        block_on_fail=policy.block_on_fail,
        active=policy.active,
    )


@router.post("", response_model=PolicyOut)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)) -> PolicyOut:
    exists = db.execute(select(GuardrailPolicy).where(GuardrailPolicy.name == payload.name)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Policy name already exists")

    policy = GuardrailPolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _to_out(policy)


@router.get("", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)) -> list[PolicyOut]:
    policies = db.execute(select(GuardrailPolicy).order_by(GuardrailPolicy.created_at.desc())).scalars().all()
    return [_to_out(p) for p in policies]


@router.post("/seed-default", response_model=PolicyOut)
def seed_default_policy(db: Session = Depends(get_db)) -> PolicyOut:
    existing = db.execute(select(GuardrailPolicy).where(GuardrailPolicy.name == "default-strict")).scalar_one_or_none()
    if existing:
        return _to_out(existing)

    policy = GuardrailPolicy(
        name="default-strict",
        min_quality_score=0.75,
        max_hallucination_score=0.25,
        max_toxicity_score=0.10,
        block_on_fail=True,
        active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _to_out(policy)
