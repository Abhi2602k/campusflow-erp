from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.attendance import router as attendance_router
from app.api.dashboard import router as dashboard_router
from app.api.management import router as management_router
from app.api.marks import router as marks_router

from app.core.config import settings

app = FastAPI(title="College Attendance ERP")


origins = [origin.strip() for origin in settings.FRONTEND_CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(attendance_router, prefix="/api/v1/attendance", tags=["attendance"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(management_router, prefix="/api/v1/management", tags=["management"])
app.include_router(management_router, prefix="/api/v1/admin", tags=["admin_alias"])
app.include_router(marks_router, prefix="/api/v1/marks", tags=["marks"])
from app.api.notices import router as notices_router
app.include_router(notices_router, prefix="/api/v1/notices", tags=["notices"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

from fastapi.responses import JSONResponse
import sqlalchemy.exc
import logging

logger = logging.getLogger("uvicorn.error")

@app.exception_handler(sqlalchemy.exc.IntegrityError)
async def sqlalchemy_integrity_exception_handler(request: Request, exc: sqlalchemy.exc.IntegrityError):
    logger.error(f"Integrity error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": "A database integrity error occurred. This is likely due to duplicate data or invalid references."},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}
