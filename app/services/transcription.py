import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.models import TranscriptionJob, JobStatus
from app.services.kafka_service import kafka_service
from app.config import settings

from app.database.db import async_session

logger = logging.getLogger(__name__)

async def start_transcription(session: AsyncSession, job: TranscriptionJob):
    """Start the transcription process by sending a request to the whisper topic"""
    message = {
        "source_id": job.source_id,
        "url": job.url,
        "language": job.language
    }
    
    await kafka_service.send_message(settings.TOPIC_WHISPER, message, key=job.source_id)
    logger.info(f"Sent transcription request to Whisper: {job.source_id}")
    
async def handle_transcription_response(data: dict):
    """Handle response from the whisper service"""
    async with async_session() as session:
        source_id = data.get("source_id")
        if not source_id:
            logger.error("Received transcription response without source_id")
            return
            
        # Get the job
        stmt = select(TranscriptionJob).where(TranscriptionJob.source_id == source_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Job not found for source_id: {source_id}")
            return
        
        # Update job with transcription
        job.transcription = data.get("output")
        
        # If this is a peertube or general transcription job that needs translation,
        # start the translation process
        if (job.source_type in ["peertube", "general"]) and job.target_language_ids:
            # Send to translation service
            await start_translation(session, job)
        else:
            # Mark as done
            job.source_status = JobStatus.DONE
        
        await session.commit()
        logger.info(f"Updated job with transcription: {source_id}")