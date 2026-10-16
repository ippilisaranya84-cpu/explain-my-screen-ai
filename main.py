
"""
ExplainMyScreen AI — FastAPI backend

Endpoints:
    GET  /         - Welcome message
    GET  /health   - Backend health check
    POST /analyze  - Analyze an uploaded screenshot
"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from models import (
    HealthResponse,
    ScreenshotInfo,
    ScreenAnalysisResponse,
)
from tools import analyze_screen, validate_screenshot, MODEL_NAME


# --------------------------------------------------
# Application setup
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("explainmyscreen")

app = FastAPI(
    title="ExplainMyScreen AI",
    description=(
        "Understand your screen with a locally running "
        "Gemma vision model powered by Ollama."
    ),
    version="1.0.0",
)

# Set FRONTEND_ORIGINS to comma-separated frontend origins if needed.
# Example: http://localhost:3000,http://localhost:5173
frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
)

origins = [
    origin.strip()
    for origin in frontend_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8 MB

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


# --------------------------------------------------
# Welcome endpoint
# --------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "ExplainMyScreen AI",
        "message": "Welcome! Your screen understanding API is ready.",
        "model": MODEL_NAME,
        "docs": "/docs",
        "health": "/health",
    }


# --------------------------------------------------
# Health endpoint
# --------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check that the API is running.

    This checks the API process, not whether Ollama is reachable.
    """

    return HealthResponse(
        status="ok",
        service="ExplainMyScreen AI",
        version="1.0.0",
        model=MODEL_NAME,
    )


# --------------------------------------------------
# Screenshot analysis endpoint
# --------------------------------------------------

@app.post(
    "/analyze",
    response_model=ScreenAnalysisResponse,
)
async def analyze_screenshot(
    file: UploadFile = File(..., description="Screenshot to analyze"),
    user_question: str = Form(
        default="Explain this screen to me."
    ),
    explanation_style: str = Form(default="beginner"),
    language: str = Form(default="English"),
):
    """
    Upload a screenshot and receive an AI-generated explanation.

    Supported formats: PNG, JPEG, WEBP.
    Maximum upload size: 8 MB.
    """

    # Validate the requested explanation settings.
    if explanation_style not in {
        "beginner",
        "concise",
        "technical",
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid explanation_style. Use beginner, "
                "concise, or technical."
            ),
        )

    if not language.strip() or len(language) > 50:
        raise HTTPException(
            status_code=422,
            detail="Language must contain 1–50 characters.",
        )

    if not user_question.strip() or len(user_question) > 1000:
        raise HTTPException(
            status_code=422,
            detail="Question must contain 1–1000 characters.",
        )

    # Validate the uploaded filename and content type.
    filename = Path(file.filename or "").name

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Please provide a screenshot filename.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Upload a PNG, JPG, JPEG, or WEBP screenshot.",
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="The uploaded file must be a supported image type.",
        )

    # Read only up to the limit plus one byte to prevent oversized uploads.
    temporary_path = None

    try:
        image_bytes = await file.read(MAX_UPLOAD_SIZE + 1)

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded screenshot is empty.",
            )

        if len(image_bytes) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Screenshot exceeds the 8 MB upload limit.",
            )

        # Store the screenshot temporarily. It is deleted after analysis.
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=extension,
            prefix="ems_",
            delete=False,
        ) as temp_file:
            temp_file.write(image_bytes)
            temporary_path = temp_file.name

        # Validate the actual image contents, not just its extension.
        image_info = validate_screenshot(temporary_path)

        if not image_info["valid"]:
            raise HTTPException(
                status_code=400,
                detail=image_info["error"] or "Invalid screenshot.",
            )

        logger.info(
            "Analyzing screenshot: %s (%sx%s)",
            filename,
            image_info["width"],
            image_info["height"],
        )

        # Run local AI analysis.
        result = analyze_screen(
            image_path=temporary_path,
            explanation_style=explanation_style,
            language=language,
            user_question=user_question,
        )

        if not result["success"]:
            logger.warning(
                "Screenshot analysis failed: %s",
                result.get("error"),
            )

            # 503 is appropriate for local model/service failures.
            raise HTTPException(
                status_code=503,
                detail=result.get("error") or "AI analysis failed.",
            )

        # Return only the fields accepted by ScreenshotInfo.
        screenshot_data = result["screenshot"]

        screenshot = ScreenshotInfo(
            filename=filename,
            width=screenshot_data["width"],
            height=screenshot_data["height"],
            format=screenshot_data["format"],
        )

        return ScreenAnalysisResponse(
            success=True,
            explanation=result["explanation"],
            error=None,
            style=result["style"],
            language=result["language"],
            screenshot=screenshot,
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception("Unexpected error during screenshot analysis")

        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while analyzing the screenshot.",
        )

    finally:
        await file.close()

        # Remove the temporary screenshot whether analysis succeeds or fails.
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                logger.warning(
                    "Could not delete temporary screenshot: %s",
                    temporary_path,
                )
