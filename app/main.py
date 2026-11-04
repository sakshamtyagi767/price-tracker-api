from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.auth import router as auth_router
from app.api.v1.tracked_items import router as tracked_items_router
from app.api.v1.analytics import router as analytics_router

# Create database tables automatically if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Multi-tenant price tracking backend with rate quotas, background scraping, and time-series analytics.",
)

# Set up CORS so a frontend or dashboard can communicate with our API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(tracked_items_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health Check"])
def health_check():
    """Health check endpoint to verify the API service is running."""
    return {"status": "healthy", "service": settings.PROJECT_NAME}
