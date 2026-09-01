"""
CRUD endpoints for user-defined chat skills (slash commands like /short).
Skills have a name (slug) and an action (LLM instruction).
Built-in names (short, dark, light) are reserved; dark/light are theme shortcuts, not skills.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import require_auth, UserResponse
from app.models import Skill

router = APIRouter()

# Reserved names: /short is the only built-in skill; /dark and /light are theme shortcuts (not skills).
RESERVED_SKILL_NAMES = frozenset({"short", "dark", "light"})


class SkillCreate(BaseModel):
    """Request body for creating a skill."""
    name: str
    action: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip().lower().replace(" ", "_")
        if not v:
            raise ValueError("Skill name cannot be empty")
        if len(v) > 64:
            raise ValueError("Skill name too long (max 64 characters)")
        if not v.replace("_", "").isalnum():
            raise ValueError("Skill name must be alphanumeric (use underscores)")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Action cannot be empty")
        if len(v) > 2000:
            raise ValueError("Action too long (max 2000 characters)")
        return v


class SkillUpdate(BaseModel):
    """Request body for updating a skill."""
    name: Optional[str] = None
    action: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower().replace(" ", "_")
        if not v:
            raise ValueError("Skill name cannot be empty")
        if len(v) > 64:
            raise ValueError("Skill name too long")
        if not v.replace("_", "").isalnum():
            raise ValueError("Skill name must be alphanumeric")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Action cannot be empty")
        if len(v) > 2000:
            raise ValueError("Action too long")
        return v


class SkillResponse(BaseModel):
    """Response body for skill endpoints."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    action: str
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


@router.get("/", response_model=List[SkillResponse])
async def list_skills(
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(require_auth),
):
    """List all skills for the current user."""
    try:
        result = await db.execute(
            select(Skill).where(Skill.user_id == user.id).order_by(Skill.created_at.desc())
        )
        skills = result.scalars().all()
        return [
            SkillResponse(
                id=s.id,
                name=s.name,
                action=s.action,
                createdAt=s.created_at.isoformat() if s.created_at else None,
                updatedAt=s.updated_at.isoformat() if s.updated_at else None,
            )
            for s in skills
        ]
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to list skills for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load skills")


@router.post("/", response_model=SkillResponse)
async def create_skill(
    body: SkillCreate,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(require_auth),
):
    """Create a new skill. Name must be unique per user. Reserved names (built-in skills) are not allowed."""
    name_lower = body.name.lower()
    if name_lower in RESERVED_SKILL_NAMES:
        raise HTTPException(
            status_code=400,
            detail="This name is reserved for a built-in skill. Choose a different name.",
        )
    existing = await db.execute(
        select(Skill).where(
            Skill.user_id == user.id,
            func.lower(Skill.name) == name_lower,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A skill with this name already exists.")
    skill = Skill(
        id=str(uuid.uuid4()),
        name=body.name,
        action=body.action,
        user_id=user.id,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        action=skill.action,
        createdAt=skill.created_at.isoformat() if skill.created_at else None,
        updatedAt=skill.updated_at.isoformat() if skill.updated_at else None,
    )


@router.patch("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    body: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(require_auth),
):
    """Update a skill. Only the owner can update. Cannot rename to a reserved or duplicate name."""
    skill = await db.get(Skill, skill_id)
    if not skill or skill.user_id != user.id:
        raise HTTPException(status_code=404, detail="Skill not found")
    if body.name is not None:
        name_lower = body.name.lower()
        if name_lower in RESERVED_SKILL_NAMES:
            raise HTTPException(
                status_code=400,
                detail="This name is reserved for a built-in skill. Choose a different name.",
            )
        if name_lower != skill.name.lower():
            existing = await db.execute(
                select(Skill).where(
                    Skill.user_id == user.id,
                    func.lower(Skill.name) == name_lower,
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="A skill with this name already exists.")
        skill.name = body.name
    if body.action is not None:
        skill.action = body.action
    await db.commit()
    await db.refresh(skill)
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        action=skill.action,
        createdAt=skill.created_at.isoformat() if skill.created_at else None,
        updatedAt=skill.updated_at.isoformat() if skill.updated_at else None,
    )


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserResponse = Depends(require_auth),
):
    """Delete a skill. Only the owner can delete."""
    skill = await db.get(Skill, skill_id)
    if not skill or skill.user_id != user.id:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(skill)
    await db.commit()
    return {"ok": True}
