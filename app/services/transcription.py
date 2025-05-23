import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.models import TranscriptionJob, JobStatus
from app.services.kafka_service import kafka_service
from app.config import settings

from app.database.db import async_session

logger = logging.getLogger(__name__)

async def start_transcription(session: AsyncSession, job: TranscriptionJob):
    """Start the transcription process using workflow configuration"""
    # Get workflow config for this source type
    workflow = settings.WORKFLOW_CONFIG.get(job.source_type)
    if not workflow:
        # throw an error here
        return
    
    # Get current step (should be 0 for new jobs)
    current_step = int(job.workflow_step)
    steps = workflow["steps"]
    
    if current_step >= len(steps):
        logger.error(f"Invalid workflow step {current_step} for job {job.source_id}")
        return
    
    # Get the topic for current step
    step_config = steps[current_step]
    topic = step_config["topic"]
    
    # Prepare message
    message = {
        "source_id": job.source_id,
        "url": job.url,
        "language": job.language,
        "video_id": job.video_id  # Include video_id for peertube steps
    }
    
    # Send message to the configured topic
    await kafka_service.send_message(topic, message, key=job.source_id)
    logger.info(f"Sent request to {topic} for job {job.source_id} (step {current_step})")


async def progress_workflow(session: AsyncSession, job: TranscriptionJob, response_data: dict = None):
    """Move job to next step in workflow and send message to next topic"""
    logger.info(f"=== WORKFLOW PROGRESS START for job {job.source_id} ===")
    logger.info(f"Current step: {job.workflow_step}, Source type: {job.source_type}")
    
    workflow = settings.WORKFLOW_CONFIG.get(job.source_type)
    if not workflow:
        logger.info(f"No workflow for source_type {job.source_type}, workflow complete")
        return
    
    current_step = int(job.workflow_step)  
    steps = workflow["steps"]
    next_step = current_step + 1
    
    logger.info(f"Total steps in workflow: {len(steps)}, Moving from step {current_step} to {next_step}")
    
    # Check if we're at the end of the workflow
    if next_step >= len(steps):
        logger.info(f"Workflow complete for job {job.source_id}")
        job.source_status = JobStatus.DONE
        await session.commit()
        return
    
    # Move to next step
    job.workflow_step = str(next_step)
    step_config = steps[next_step]
    topic = step_config["topic"]
    
    logger.info(f"Next topic: {topic}")
    
    # Prepare message with all current job data
    message = {
        "source_id": job.source_id,
        "url": job.url,
        "language": job.language,
        "video_id": job.video_id,
        "transcription": job.transcription,
        "translations": job.translations
    }
    
    logger.info(f"Sending message to {topic}: {message}")
    
    # Send to next topic
    await kafka_service.send_message(topic, message, key=job.source_id)
    await session.commit()
    logger.info(f"=== WORKFLOW PROGRESS COMPLETE: Advanced job {job.source_id} to step {next_step}, sent to {topic} ===")


async def handle_transcription_response(data: dict):
    """Handle response from the whisper service"""
    logger.info(f"=== TRANSCRIPTION RESPONSE RECEIVED: {data} ===")
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
        await session.commit()
        
        # Progress to next step in workflow
        await progress_workflow(session, job, data)
        
        logger.info(f"Updated job with transcription and progressed workflow: {source_id}")