from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    origin = Column(String)
    destination = Column(String)
    status = Column(String, default="planned")