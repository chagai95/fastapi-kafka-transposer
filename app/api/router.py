from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.database.db import get_db
from app.database.models import TranscriptionJob, JobStatus
from app.schemas.request_schemas import (
    TranscribeVideoRequest, 
    GeneralTranscribeRequest,
    TranslateRequest,
    JobStatusResponse
)
from app.services.workflow_service import workflow_service
from app.config import settings

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/transcribe-and-translate/video")
async def transcribe_and_translate_video(
    request: TranscribeVideoRequest,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to transcribe and translate a PeerTube video"""
    source_id = str(uuid.uuid4())
    
    # Create new job
    job = TranscriptionJob(
        source_id=source_id,
        source_type="peertube",
        url=str(request.url),
        video_id=request.videoId,
        language=request.language,
        source_status=JobStatus.IN_PROGRESS
    )
    
    db.add(job)
    await db.commit()
    
    # Start workflow
    await workflow_service.start_job(db, job)
    
    return {"source_id": source_id}

@router.post("/transcribe-and-translate")
async def transcribe_and_translate_general(
    request: GeneralTranscribeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint to transcribe and translate a general URL"""
    source_id = str(uuid.uuid4())
    
    # Create new job
    job = TranscriptionJob(
        source_id=source_id,
        source_type="general",  # You'll need to add "general" to WORKFLOW_CONFIG
        url=str(request.url),
        language=request.language,
        source_status=JobStatus.IN_PROGRESS
    )
    
    db.add(job)
    await db.commit()
    
    # Start workflow
    await workflow_service.start_job(db, job)
    
    return {"source_id": source_id}

@router.post("/translate")
async def translate(
    request: TranslateRequest
):
    """Endpoint to translate text directly"""
    # Validate languages
    if request.source_language_id not in settings.SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported source language")
        
    target_langs = request.target_language_ids
    if isinstance(target_langs, str):
        target_langs = [target_langs]
        
    # Validate target languages
    for lang in target_langs:
        if lang not in settings.SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=400, detail=f"Unsupported target language: {lang}")
    
    # Create a translation-only job
    source_id = str(uuid.uuid4())
    
    async with get_db() as db:
        job = TranscriptionJob(
            source_id=source_id,
            source_type="translation_only",  # You'll need to add this to WORKFLOW_CONFIG
            url="direct_text",
            language=request.source_language_id,
            target_language_ids=target_langs,
            transcription=request.input,  # Set the input text as transcription
            source_status=JobStatus.IN_PROGRESS
        )
        
        db.add(job)
        await db.commit()
        
        # Start workflow
        await workflow_service.start_job(db, job)
    
    return {"source_id": source_id}

@router.get("/transcribe-and-translate/{source_id}/status", response_model=JobStatusResponse)
async def get_job_status(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get status of a transcription/translation job"""
    stmt = select(TranscriptionJob).where(TranscriptionJob.source_id == source_id)
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