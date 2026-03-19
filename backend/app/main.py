from fastapi import FastAPI
from app.routes import router

app = FastAPI(title="AURA Travel AI")

app.include_router(router)

@app.get("/")
def root():
    return {"message": "AURA backend running 🚀"}