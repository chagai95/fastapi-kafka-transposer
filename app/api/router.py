from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import logging
from typing import Dict, Any

from app.database.db import get_db
from app.database.models import TranscriptionAndTranslationJob, JobStatus
from app.schemas.request_schemas import (
    TranscribeVideoRequest, 
    GeneralTranscribeRequest,
    TranslateRequest,
    JobStatusResponse
)
from app.services.workflow_service import workflow_service
from app.services.workflow_db_service import workflow_db_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

async def validate_and_extract_parameters(request: Request, route_path: str, db: AsyncSession) -> Dict[str, Any]:
    """Validate request parameters against database configuration"""
    try:
        # Get request body as dict
        body = await request.json()
        
        # Validate against database configuration
        validation_result = await workflow_db_service.validate_route_parameters(
            db, route_path, body
        )
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Parameter validation failed: {validation_result['error']}"
            )
        
        return {
            "parameters": body,
            "workflow_name": validation_result["workflow_name"]
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Error validating parameters for {route_path}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request format: {str(e)}"
        )

@router.post("/transcribe-and-translate/video")
async def transcribe_and_translate_video(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to transcribe and translate a PeerTube video"""
    logger.info("/transcribe-and-translate/video called")
    
    try:
        # Validate parameters against database configuration
        validation_result = await validate_and_extract_parameters(
            request, "/transcribe-and-translate/video", db
        )
        
        params = validation_result["parameters"]
        workflow_name = validation_result["workflow_name"]
        
        source_id = str(uuid.uuid4())
        
        # Create new job using validated parameters
        job = TranscriptionAndTranslationJob(
            source_id=source_id,
            source_type=workflow_name,  # Use workflow name from database
            url=str(params["url"]),
            video_id=params.get("videoId"),
            peertube_basedomain=params.get("peertubeInstanceBaseDomain"),
            language=params.get("language"),
            source_status=JobStatus.IN_PROGRESS
        )
        
        db.add(job)
        await db.commit()
        
        # Start workflow
        await workflow_service.start_job(db, job)
        
        return {"source_id": source_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in transcribe_and_translate_video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing video transcription request"
        )

@router.post("/transcribe-and-translate")
async def transcribe_and_translate_general(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to transcribe and translate a general URL"""
    logger.info("/transcribe-and-translate called")
    
    try:
        # Validate parameters against database configuration
        validation_result = await validate_and_extract_parameters(
            request, "/transcribe-and-translate", db
        )
        
        params = validation_result["parameters"]
        workflow_name = validation_result["workflow_name"]
        
        source_id = str(uuid.uuid4())
        
        # Create new job using validated parameters
        job = TranscriptionAndTranslationJob(
            source_id=source_id,
            source_type=workflow_name,  # Use workflow name from database
            url=str(params["url"]),
            language=params.get("language"),
            source_status=JobStatus.IN_PROGRESS
        )
        
        db.add(job)
        await db.commit()
        
        # Start workflow
        await workflow_service.start_job(db, job)
        
        return {"source_id": source_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in transcribe_and_translate_general: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing general transcription request"
        )

@router.post("/translate")
async def translate(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to translate text directly"""
    logger.info("/translate called")
    
    try:
        # Validate parameters against database configuration
        validation_result = await validate_and_extract_parameters(
            request, "/translate", db
        )
        
        params = validation_result["parameters"]
        workflow_name = validation_result["workflow_name"]
        
        # Additional validation for translation-specific logic
        source_language = params.get("source_language_id")
        target_langs = params.get("target_language_ids")
        input_text = params.get("input")
        
        if not source_language or not target_langs or not input_text:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: source_language_id, target_language_ids, or input"
            )
        
        # Validate languages against supported languages
        if source_language not in settings.SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=400, detail="Unsupported source language")
            
        if isinstance(target_langs, str):
            target_langs = [target_langs]
            
        # Validate target languages
        for lang in target_langs:
            if lang not in settings.SUPPORTED_LANGUAGES:
                raise HTTPException(status_code=400, detail=f"Unsupported target language: {lang}")
        
        # Create a translation-only job
        source_id = str(uuid.uuid4())
        
        job = TranscriptionAndTranslationJob(
            source_id=source_id,
            source_type=workflow_name,  # Use workflow name from database
            url="direct_text",
            language=source_language,
            target_language_ids=target_langs,
            transcription=input_text,  # Set the input text as transcription
            source_status=JobStatus.IN_PROGRESS
        )
        
        db.add(job)
        await db.commit()
        
        # Start workflow
        await workflow_service.start_job(db, job)
        
        return {"source_id": source_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in translate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing translation request"
        )

@router.get("/transcribe-and-translate/{source_id}/status", response_model=JobStatusResponse)
async def get_job_status(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get status of a transcription/translation job"""
    try:
        stmt = select(TranscriptionAndTranslationJob).where(TranscriptionAndTranslationJob.source_id == source_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        return {
            "status": job.source_status,
            "source_id": job.source_id,
            "transcription": job.transcription,
            "translations": job.translations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in get_job_status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving job status"
        )