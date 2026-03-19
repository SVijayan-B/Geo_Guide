from pydantic import BaseModel


class TripCreate(BaseModel):
    user_id: int
    origin: str
    destination: str


class TripResponse(BaseModel):
    id: int
    user_id: int
    origin: str
    destination: str
    status: str

    class Config:
        from_attributes = True