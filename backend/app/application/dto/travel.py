from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RecommendationRequestDTO(BaseModel):
    mode: str = Field(default="pre_trip_plan")
    days: int = Field(default=3, ge=1, le=21)
    traveler_type: str = Field(default="foodie")
    budget: Optional[float] = Field(default=None, ge=0)
    home_currency: str = Field(default="INR", min_length=3, max_length=3)
    destination_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    user_lat: Optional[float] = None
    user_lon: Optional[float] = None
    is_user_at_airport: bool = False
    flight_delayed: bool = False


class ChatRequestDTO(BaseModel):
    query: Optional[str] = None
    image_path: Optional[str] = None
    city: str = "Chennai"
    destination_currency: Optional[str] = None
    trip_id: Optional[int] = None
    chat_session_id: Optional[int] = None
    new_chat: bool = False
    title: Optional[str] = None
    mode: str = "pre_trip_plan"
    days: int = Field(default=3, ge=1, le=21)
    traveler_type: str = "foodie"
    budget: Optional[float] = Field(default=None, ge=0)
    user_lat: Optional[float] = None
    user_lon: Optional[float] = None
    cuisine: Optional[str] = None
    is_user_at_airport: bool = False
    flight_delayed: bool = False


class RefreshTokenRequestDTO(BaseModel):
    refresh_token: str


class TokenPairDTO(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class AutopilotStatusDTO(BaseModel):
    trip_id: int
    user_id: int
    status: str
    delay_probability: Optional[float] = None
    risk_level: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: Optional[datetime] = None
    recommendation: Optional[str] = None
