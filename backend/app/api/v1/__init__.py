from fastapi import APIRouter
from app.api.v1.routes import (
    complaints,
    pipeline,
    explanation,
    rbi,
    feedback,
    dashboard,
    sla,
)

api_v1_router = APIRouter()

api_v1_router.include_router(
    complaints.router,
    prefix="/complaints",
    tags=["Complaints"],
)
api_v1_router.include_router(
    pipeline.router,
    prefix="/pipeline",
    tags=["Pipeline"],
)
api_v1_router.include_router(
    explanation.router,
    prefix="/complaints",
    tags=["Explanation (XAI)"],
)
api_v1_router.include_router(
    rbi.router,
    prefix="/rbi",
    tags=["RBI Compliance"],
)
api_v1_router.include_router(
    feedback.router,
    prefix="/feedback",
    tags=["Feedback"],
)
api_v1_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"],
)
api_v1_router.include_router(
    sla.router,
    prefix="/sla",
    tags=["SLA Predictor"],
)