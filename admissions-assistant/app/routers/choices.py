from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.database import load_programs
from app.services.program_choices import career, recommend
from app.services.policy_sync import read_policy

router = APIRouter(prefix="/choices", tags=["Program choice"])


class Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    interests: str = Field(min_length=3, max_length=500)
    background: str = Field(min_length=2, max_length=500)
    goals: str = Field(min_length=3, max_length=500)


@router.post("/recommend")
def recommendations(profile: Profile):
    return recommend(profile.interests, profile.background, profile.goals)


@router.get("/compare")
def compare(ids: list[str] = Query(min_length=2, max_length=4)):
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Choose distinct programs.")
    catalog = {p["id"]: p for p in load_programs()}
    policy = read_policy()
    rows = []
    for pid in ids:
        p = catalog.get(pid, {})
        rows.append({"id": pid, "name": p.get("name") or pid, "annual_fee": p.get("approx_cost_per_year_kzt"),
                     "years": p.get("duration_years"), "passing_score": p.get("min_unt_score"),
                     "grants": ("State grant competition" if (p.get("code") or "").upper().replace("В", "B")
                                in policy["grant_codes"] else None)})
    return rows


@router.get("/policy")
def official_policy():
    return read_policy()


@router.get("/{program_id}/careers")
def careers(program_id: str, language: Literal["en", "ru", "kk"] = "en"):
    program = next((p for p in load_programs() if p["id"] == program_id), None)
    if not program:
        raise HTTPException(404, "Program not found.")
    return career(program, language)
