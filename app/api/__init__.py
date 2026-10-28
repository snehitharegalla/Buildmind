from fastapi import APIRouter
from app.api.projects import router as projects_router
from app.api.layouts import router as layouts_router
from app.api.generation import router as generation_router
from app.api.validation import router as validation_router
from app.api.copilot import router as copilot_router
from app.api.comparison import router as comparison_router
from app.api.export import router as export_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(layouts_router)
api_router.include_router(generation_router)
api_router.include_router(validation_router)
api_router.include_router(copilot_router)
api_router.include_router(comparison_router)
api_router.include_router(export_router)
