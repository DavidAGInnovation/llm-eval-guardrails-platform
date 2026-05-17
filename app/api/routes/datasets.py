from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Dataset, PromptSample
from app.db.schemas import DatasetCreate, DatasetOut
from app.db.session import get_db

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetOut)
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db)) -> DatasetOut:
    exists = db.execute(select(Dataset).where(Dataset.name == payload.name)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Dataset name already exists")

    dataset = Dataset(name=payload.name, description=payload.description)
    db.add(dataset)
    db.flush()

    for p in payload.prompts:
        db.add(
            PromptSample(
                dataset_id=dataset.id,
                input_text=p.input_text,
                expected_output=p.expected_output,
                metadata_json=p.metadata_json,
            )
        )

    db.commit()
    db.refresh(dataset)
    return DatasetOut(id=dataset.id, name=dataset.name, description=dataset.description)


@router.get("", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetOut]:
    datasets = db.execute(select(Dataset).order_by(Dataset.created_at.desc())).scalars().all()
    return [DatasetOut(id=d.id, name=d.name, description=d.description) for d in datasets]
