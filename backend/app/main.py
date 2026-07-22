from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.core.config import settings
from app.api.v1.router import api_router
from app.middleware.error_handler import setup_error_handlers


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set up global exception handlers
setup_error_handlers(app)

# CORS configurations
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root_endpoint():
    """
    Health check root path.
    """
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "version": "1.0.0",
    }
