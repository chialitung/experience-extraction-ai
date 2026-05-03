from fastapi import APIRouter
from app.api.v1.interviews import router as interviews_router
from app.api.v1.config import router as config_router
from app.api.v1.auth import router as auth_router
from app.api.v1.text_analysis import router as text_analysis_router

router = APIRouter(prefix="/v1")
router.include_router(auth_router)
router.include_router(interviews_router)
router.include_router(text_analysis_router)
router.include_router(config_router)
