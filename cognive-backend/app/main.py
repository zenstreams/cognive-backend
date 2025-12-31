"""Cognive Control Plane API - Main Application Entry Point.

This module configures the FastAPI application with OpenAPI documentation,
security schemes, and core routes for the Cognive agentic AI Ops platform.
"""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPBearer
from pydantic import BaseModel, Field

from app.api.health import router as health_router
from app.core.config import settings
from app.core.storage import init_storage

# =============================================================================
# Response Models
# =============================================================================


class RootResponse(BaseModel):
    """Root endpoint response with service metadata."""

    message: str = Field(..., description="Service greeting confirming API availability")
    version: str = Field(..., description="API version string")
    environment: str = Field(..., description="Deployment environment label (dev, staging, prod)")


# =============================================================================
# Security Schemes
# =============================================================================

API_KEY_DESCRIPTION = "Control plane API key used by agents and SDK calls"
BEARER_DESCRIPTION = "JWT bearer token used by dashboard/authenticated users"

api_key_scheme = APIKeyHeader(name="X-API-Key", description=API_KEY_DESCRIPTION, auto_error=False)
bearer_scheme = HTTPBearer(description=BEARER_DESCRIPTION, auto_error=False)

# =============================================================================
# Constants
# =============================================================================

API_VERSION = "0.1.0"
OPENAPI_VERSION = "3.1.0"
REDOC_VERSION = "2.1.5"  # Pinned version for stability
REDOC_JS_URL = f"https://cdn.jsdelivr.net/npm/redoc@{REDOC_VERSION}/bundles/redoc.standalone.js"

logger = logging.getLogger(__name__)

# =============================================================================
# Application Factory
# =============================================================================


def create_application() -> FastAPI:
    """Create FastAPI application with OpenAPI documentation and security schemes.

    Returns:
        Configured FastAPI application instance.
    """
    description = (
        "Cognive Control Plane API for agent registry, execution tracking, cost governance, "
        "and observability. This service backs the agentic AI Ops platform and is designed "
        "for enterprise-grade security, compliance, and uptime.\n\n"
        "## Authentication\n\n"
        "The API supports two authentication methods:\n\n"
        "- **API Key**: Use `X-API-Key` header for agent and SDK access\n"
        "- **Bearer Token**: Use `Authorization: Bearer <token>` for dashboard access\n\n"
        "## Versioning\n\n"
        "This API uses URL path versioning. All endpoints are prefixed with `/api/v1`."
    )

    tags_metadata = [
        {
            "name": "health",
            "description": "Operational health probes for Kubernetes liveness/readiness checks.",
        },
        {
            "name": "core",
            "description": "Core service metadata and control plane identification endpoints.",
        },
    ]

    app = FastAPI(
        title=settings.app_name,
        description=description,
        version=API_VERSION,
        openapi_version=OPENAPI_VERSION,
        contact={
            "name": "Cognive Engineering",
            "email": "engineering@cognive.io",
        },
        license_info={
            "name": "Proprietary - Cognive",
            "url": "https://cognive.io/terms",
        },
        terms_of_service="https://cognive.io/terms",
        # Disable default docs; we provide custom handlers with caching
        docs_url=None,
        redoc_url=None,
        openapi_url=None,  # We'll handle this manually for caching
        openapi_tags=tags_metadata,
    )

    # -------------------------------------------------------------------------
    # Custom OpenAPI Schema Generator
    # -------------------------------------------------------------------------

    def custom_openapi():
        """Generate OpenAPI schema with security schemes and global security."""
        if app.openapi_schema:
            return app.openapi_schema

        security_schemes = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "name": "X-API-Key",
                "in": "header",
                "description": API_KEY_DESCRIPTION,
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": BEARER_DESCRIPTION,
            },
        }

        try:
            openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=OPENAPI_VERSION,
                description=app.description,
                routes=app.routes,
                tags=tags_metadata,
            )
            openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
                security_schemes
            )
            # Apply API Key auth globally; individual endpoints can override
            openapi_schema["security"] = [{"ApiKeyAuth": []}, {"BearerAuth": []}]
            app.openapi_schema = openapi_schema
            return app.openapi_schema

        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to generate OpenAPI schema: %s", exc)
            info_desc = "OpenAPI generation failed; check server logs for details."
            if settings.environment != "production":
                info_desc += f" Error: {exc}"

            fallback_schema = {
                "openapi": OPENAPI_VERSION,
                "info": {
                    "title": app.title,
                    "version": app.version,
                    "description": info_desc,
                    "x-error": str(exc),
                },
                "paths": {},
                "components": {"securitySchemes": security_schemes},
            }
            app.openapi_schema = fallback_schema
            return fallback_schema

    app.openapi = custom_openapi

    # -------------------------------------------------------------------------
    # Documentation Endpoints with Caching
    # -------------------------------------------------------------------------

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_json():
        """Serve OpenAPI schema with caching headers for performance."""
        return JSONResponse(
            content=app.openapi(),
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Type": "application/json",
            },
        )

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html():
        """Serve Swagger UI documentation."""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        """Serve ReDoc documentation with pinned version."""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - ReDoc",
            redoc_js_url=REDOC_JS_URL,
        )

    return app


# =============================================================================
# Application Instance
# =============================================================================

app = create_application()


# =============================================================================
# Startup & Shutdown Events
# =============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("🚀 Starting Cognive Control Plane API...")
    logger.info(f"   Environment: {settings.environment}")
    logger.info(f"   Version: {API_VERSION}")
    
    # Initialize MinIO object storage
    try:
        logger.info("Initializing object storage...")
        await init_storage()
        logger.info("✅ Object storage ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize storage: {e}")
        # Don't fail startup if storage is unavailable (graceful degradation)
        logger.warning("⚠️  Continuing without object storage")
    
    logger.info("✅ Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("🛑 Shutting down Cognive Control Plane API...")
    logger.info("✅ Shutdown complete")

# =============================================================================
# API Router with Versioning
# =============================================================================

api_v1_router = APIRouter(prefix="/api/v1")

# Mount health routes under versioned API
api_v1_router.include_router(health_router, prefix="/health", tags=["health"])


# =============================================================================
# Core Endpoints
# =============================================================================


@api_v1_router.get(
    "/",
    summary="API version info",
    response_model=RootResponse,
    tags=["core"],
    responses={
        200: {
            "description": "API metadata payload",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Cognive Control Plane API",
                        "version": "0.1.0",
                        "environment": "development",
                    }
                }
            },
        },
    },
)
async def api_v1_root():
    """Return API version metadata for client SDKs and dashboards."""
    return {
        "message": "Cognive Control Plane API",
        "version": API_VERSION,
        "environment": settings.environment,
    }


# Mount versioned router
app.include_router(api_v1_router)


# =============================================================================
# Root Endpoint (Redirect hint to versioned API)
# =============================================================================


class ServiceInfoResponse(BaseModel):
    """Service discovery response."""

    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Current API version")
    docs: str = Field(..., description="Swagger UI documentation URL")
    redoc: str = Field(..., description="ReDoc documentation URL")
    api_base: str = Field(..., description="Versioned API base path")


@app.get(
    "/",
    summary="Service discovery",
    response_model=ServiceInfoResponse,
    tags=["core"],
    responses={
        200: {
            "description": "Service discovery information",
            "content": {
                "application/json": {
                    "example": {
                        "service": "Cognive Control Plane API",
                        "version": "0.1.0",
                        "docs": "/docs",
                        "redoc": "/redoc",
                        "api_base": "/api/v1",
                    }
                }
            },
        },
    },
)
async def root():
    """Service discovery endpoint for clients to find API documentation and base paths."""
    return {
        "service": settings.app_name,
        "version": API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "api_base": "/api/v1",
    }
