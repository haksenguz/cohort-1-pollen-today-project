from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from app.core.db import SessionDep
from app.core.enums import Allergen, AllergySeverity
from app.core.security import CurrentUser
from app.models import UserAllergy

router = APIRouter(prefix="/api/allergies", tags=["allergies"])


class AllergyCreateRequest(BaseModel):
    allergen: Allergen
    severity: AllergySeverity


class AllergyResponse(BaseModel):
    id: int
    allergen: str
    severity: str
    created_at: datetime


@router.get("")
async def list_allergies(current_user: CurrentUser, session: SessionDep) -> list[AllergyResponse]:
    result = await session.execute(
        select(UserAllergy).where(UserAllergy.user_id == current_user.id)
    )
    return [
        AllergyResponse.model_validate(row, from_attributes=True) for row in result.scalars().all()
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_allergy(
    body: AllergyCreateRequest, current_user: CurrentUser, session: SessionDep
) -> AllergyResponse:
    allergy = UserAllergy(
        user_id=current_user.id,
        allergen=body.allergen.value,
        severity=body.severity.value,
    )
    session.add(allergy)
    await session.commit()
    await session.refresh(allergy)
    return AllergyResponse.model_validate(allergy, from_attributes=True)


@router.delete("/{allergy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allergy(allergy_id: int, current_user: CurrentUser, session: SessionDep) -> None:
    allergy = await session.get(UserAllergy, allergy_id)
    if allergy is None or allergy.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Allergy not found")
    await session.delete(allergy)
    await session.commit()
