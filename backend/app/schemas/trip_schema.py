from pydantic import BaseModel


class TripCreate(BaseModel):
    origin: str
    destination: str


class TripResponse(BaseModel):
    id: str
    user_id: str
    origin: str
    destination: str
    status: str

    class Config:
        from_attributes = True