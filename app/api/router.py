from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import logging
from typing import Dict, Any, Optional, List
import asyncio

from app.database.db import get_db
from app.database.models import TranslationJob, TranscriptionAndTranslationJob, JobStatus
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

from app.services.language_service import language_service
from app.services.translation_response_handler import translation_response_handler

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

@router.get("/translation-targets")
async def get_translation_targets(languageId: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    """Get translation targets for languages"""
    try:
        # Get translation targets from database
        translation_targets = await language_service.get_translation_targets(db)
        
        # If specific language requested, return just that target
        if languageId:
            if languageId not in translation_targets:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Language '{languageId}' not found"
                )
            return translation_targets[languageId]
        
        # Return all translation targets
        return translation_targets
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_translation_targets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving translation targets"
        )

@router.get("/supported-languages")
async def get_supported_languages(db: AsyncSession = Depends(get_db)):
    """Get list of supported languages with their translation targets"""
    try:
        # Get languages from database in the expected format
        supported_languages = await language_service.get_supported_languages_format(db)
        return supported_languages
        
    except Exception as e:
        logger.exception(f"Error in get_supported_languages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error retrieving supported languages"
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
    db: AsyncSession = Depends(get_db),
    wait_for_result: bool = Query(True, description="Wait for translation result or return immediately with source_id")
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
        
        # Validate languages against supported languages from database
        language = await language_service.get_language_by_code(db, source_language)
        if not language:
            raise HTTPException(status_code=400, detail="Unsupported source language")
            
        if isinstance(target_langs, str):
            target_langs = [target_langs]
            
        # Validate target languages
        validation_results = await language_service.validate_language_codes(db, target_langs)
        invalid_langs = [lang for lang, valid in validation_results.items() if not valid]
        if invalid_langs:
            raise HTTPException(status_code=400, detail=f"Unsupported target languages: {', '.join(invalid_langs)}")
        
        # Create a translation job
        source_id = str(uuid.uuid4())
        logger.info(f"Created translation job with source_id: {source_id}")
        
        job = TranslationJob(
            source_id=source_id,
            source_type=workflow_name,
            source_language=source_language,
            target_language_ids=target_langs,
            input_text=input_text,
            format=params.get("format", "text"),  # Default to "text" instead of None
            status=JobStatus.IN_PROGRESS
        )
        
        db.add(job)
        await db.commit()
        logger.info(f"Saved translation job to database: {source_id}")
        
        # If wait_for_result is False, return immediately with source_id
        if not wait_for_result:
            await workflow_service.start_translation_job(db, job)
            return {"source_id": source_id}
        
        # CRITICAL: Register the future BEFORE starting the workflow
        logger.info(f"Registering future for {source_id} BEFORE starting workflow")
        future = translation_response_handler.register_request(source_id)
        
        # Now start the workflow
        await workflow_service.start_translation_job(db, job)
        logger.info(f"Started translation workflow for {source_id}, now waiting for response")
        
        # Wait for the future to complete
        logger.info(f"About to wait for future {source_id}")
        try:
            logger.info(f"Calling asyncio.wait_for for {source_id}")
            result = await asyncio.wait_for(future, timeout=30.0)
            logger.info(f"asyncio.wait_for returned for {source_id}: {result}")
            
            if result:
                logger.info(f"Returning translations for {source_id}")
                return {
                    "source_id": source_id,
                    "translations": result.get("translations", {}),
                    "status": "completed"
                }
            else:
                logger.error(f"Empty result received for {source_id}")
                return {
                    "source_id": source_id,
                    "status": "error",
                    "error": "Empty result received"
                }
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response for {source_id}")
            # Remove from pending requests if it exists
            translation_response_handler._pending_requests.pop(source_id, None)
            
            # Re-fetch job to get any partial results
            await db.refresh(job)
            return {
                "source_id": source_id,
                "status": job.status.value,
                "translations": job.translations,
                "message": "Translation is taking longer than expected. Use the status endpoint to check progress."
            }
        except Exception as e:
            logger.exception(f"Exception in asyncio.wait_for for {source_id}: {str(e)}")
            return {
                "source_id": source_id,
                "status": "error",
                "error": f"Internal error: {str(e)}"
            }
        
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