import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.models import TranscriptionJob, JobStatus
from app.services.kafka_service import kafka_service
from app.config import settings
from app.database.db import async_session
    
logger = logging.getLogger(__name__)

async def start_translation(session: AsyncSession, job: TranscriptionJob):
    """Start the translation process by sending a request to the generic_translate topic"""
    if not job.transcription:
        logger.error(f"Cannot translate job without transcription: {job.source_id}")
        return
        
    message = {
        "source_id": job.source_id,
        "input": job.transcription,
        "format": "transcription",
        "source_language_id": job.language,
        "target_language_ids": job.target_language_ids
    }
    
    await kafka_service.send_message(settings.TOPIC_GENERIC_TRANSLATE, message, key=job.source_id)
    logger.info(f"Sent translation request for job: {job.source_id}")
    
async def translate_text(text: str, source_lang: str, target_langs: list):
    """Translate text directly (not from a job)"""
    # Generate a unique ID for this translation
    import uuid
    source_id = str(uuid.uuid4())
    
    message = {
        "source_id": source_id,
        "input": text,
        "source_language_id": source_lang,
        "target_language_ids": target_langs
    }
    
    # Create a job record for tracking
    async with async_session() as session:
        job = TranscriptionJob(
            source_id=source_id,
            source_type="translation_only",
            url="direct_text",
            language=source_lang,
            target_language_ids=target_langs,
            source_status=JobStatus.IN_PROGRESS
        )
        session.add(job)
        await session.commit()
    
    # Send to translation service
    await kafka_service.send_message(settings.TOPIC_GENERIC_TRANSLATE, message, key=source_id)
    logger.info(f"Sent direct translation request: {source_id}")
    
    return source_id
 
async def handle_translation_response(data: dict):
    """Handle response from the translation service"""
    logger.info(f"=== TRANSLATION RESPONSE RECEIVED: {data} ===")
    async with async_session() as session:
        source_id = data.get("source_id")
        if not source_id:
            logger.error("Received translation response without source_id")
            return
            
        # Get the job
        stmt = select(TranscriptionJob).where(TranscriptionJob.source_id == source_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Job not found for source_id: {source_id}")
            return
        
        # Update job with translations
        job.translations = data.get("translations", {})
        await session.commit()
        
        # Import and use workflow progression
        from app.services.transcription import progress_workflow
        await progress_workflow(session, job, data)
        
        logger.info(f"Updated job with translations and progressed workflow: {source_id}")