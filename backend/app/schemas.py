"""Strict Pydantic contracts for the PanelScan damage-assessment handoff."""

from typing import Literal

from pydantic import BaseModel, Field

RecommendedAction = Literal["repair", "replace"]


class DamageItem(BaseModel):
    panel_name: str = Field(..., min_length=1, max_length=200)
    damage_type: str = Field(..., min_length=1, max_length=100)
    recommended_action: RecommendedAction
    ai_confidence_score: float = Field(..., ge=0, le=1)


class QuoteEstimate(BaseModel):
    vehicle_summary: str = Field(..., min_length=1, max_length=300)
    damage_items: list[DamageItem] = Field(..., min_length=1)
    total_parts_estimate_zar: float = Field(..., ge=0)
    total_labor_hours: float = Field(..., ge=0)
