from fastapi import FastAPI
from app.routes import router
from app.config import APP_NAME
from app.db.database import engine, Base

# Import models (IMPORTANT)
from app.models import user, trip, chat

# Create tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(title=APP_NAME)


# Include routes
app.include_router(router)


@app.get("/")
def root():
    return {
        "message": f"{APP_NAME} is live 🚀"
    }