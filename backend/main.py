"""Credit Genie backend entrypoint. Run with: uv run uvicorn main:app --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.policy_routes import router as policy_router
from app.api.routes import router as decide_router

app = FastAPI(title="Credit Genie API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(decide_router)
app.include_router(policy_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
