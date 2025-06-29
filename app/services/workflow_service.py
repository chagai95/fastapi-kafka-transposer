import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import TranscriptionAndTranslationJob, TranslationJob, JobStatus
from app.services.kafka_service import kafka_service
from app.services.workflow_db_service import workflow_db_service
from app.database.db import async_session
from app.services.translation_response_handler import translation_response_handler

logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self):
        # Remove the static workflows - now loaded from database
        pass
        
    async def start_job(self, session: AsyncSession, job: TranscriptionAndTranslationJob):
        """Start a job by sending it to the first step in its workflow"""
        workflow = await workflow_db_service.get_workflow_config(session, job.source_type)
        if not workflow:
            logger.error(f"No workflow found for source_type: {job.source_type}")
            job.source_status = JobStatus.ERROR
            await session.commit()
            return
            
        # Send to first step
        await self._send_to_step(job, 0, workflow)
        logger.info(f"Started job {job.source_id} with workflow '{job.source_type}'")
    
    async def process_response(self, topic: str, data: dict):
        """Process a response from any topic and advance the workflow"""
        logger.info(f"Processing response from topic '{topic}': {data}")
        
        source_id = data.get("source_id")
        if not source_id:
            logger.error("Received response without source_id")
            return
            
        async with async_session() as session:
            # First try to find a translation job
            stmt = select(TranslationJob).where(TranslationJob.source_id == source_id)
            result = await session.execute(stmt)
            translation_job = result.scalar_one_or_none()
            
            if translation_job:
                # Handle translation job
                if "translations" in data:
                    translation_job.translations = data["translations"]
                    translation_job.status = JobStatus.DONE
                    await session.commit()
                    
                    # Send response back to waiting HTTP request
                    await translation_response_handler.handle_response(source_id, {
                        "source_id": source_id,
                        "translations": data["translations"],
                        "status": "completed"
                    })
                    logger.info(f"Translation job {source_id} completed and response sent")
                return
            
            # If not a translation job, check transcription job
            stmt = select(TranscriptionAndTranslationJob).where(TranscriptionAndTranslationJob.source_id == source_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job not found for source_id: {source_id}")
                return
            
            # Handle transcription job as before
            await self._update_job_with_response(job, data)
            await session.commit()
            await self._advance_workflow(session, job)

    # Add a new method to start translation jobs
    async def start_translation_job(self, session: AsyncSession, job: TranslationJob):
        """Start a translation-only job"""
        # Send to translation service
        message = {
            "source_id": job.source_id,
            "input": job.input_text,
            "source_language": job.source_language,
            "target_languages": job.target_language_ids
        }
        
        # Get the translation topic from workflow config
        workflow = await workflow_db_service.get_workflow_config(session, "translation")
        if workflow and workflow["steps"]:
            topic = workflow["steps"][0]["topic"]
            await kafka_service.send_message(topic, message, key=job.source_id)
            logger.info(f"Sent translation job {job.source_id} to topic '{topic}'")
    
    async def _update_job_with_response(self, job: TranscriptionAndTranslationJob, data: dict):
        """Update job with response data based on what's in the response"""
        # Update transcription if present
        if "output" in data:
            job.transcription = data["output"]
            logger.info(f"Updated transcription for job {job.source_id}")
            
        # Update translations if present  
        if "translations" in data:
            job.translations = data["translations"]
            logger.info(f"Updated translations for job {job.source_id}")
            
        # You can add more response field mappings here as needed
        
    async def _advance_workflow(self, session: AsyncSession, job: TranscriptionAndTranslationJob):
        """Move job to next step in workflow"""
        workflow = await workflow_db_service.get_workflow_config(session, job.source_type)
        if not workflow:
            logger.error(f"No workflow found for source_type: {job.source_type}")
            job.source_status = JobStatus.ERROR
            await session.commit()
            return
            
        current_step = int(job.workflow_step)
        next_step = current_step + 1
        steps = workflow["steps"]
        
        # Check if workflow is complete
        if next_step >= len(steps):
            logger.info(f"Workflow complete for job {job.source_id}")
            job.source_status = JobStatus.DONE
            await session.commit()
            return
        
        # Move to next step
        job.workflow_step = str(next_step)
        await session.commit()
        
        # Send to next step
        await self._send_to_step(job, next_step, workflow)
        logger.info(f"Advanced job {job.source_id} to step {next_step}")
    
    async def _send_to_step(self, job: TranscriptionAndTranslationJob, step_index: int, workflow: dict):
        """Send job data to a specific workflow step"""
        steps = workflow["steps"]
        if step_index >= len(steps):
            logger.error(f"Invalid step {step_index} for workflow {job.source_type}")
            return
            
        step = steps[step_index]
        topic = step["topic"]
        
        # Only send the source_id - services can query the database for full data
        message = {
            "source_id": job.source_id
        }
        
        await kafka_service.send_message(topic, message, key=job.source_id)
        logger.info(f"Sent job {job.source_id} to topic '{topic}' (step {step_index})")
    
    async def get_response_topics(self, session: AsyncSession):
        """Get all response topics from database workflows for consumer registration"""
        return await workflow_db_service.get_all_response_topics(session)

# Create global instance
workflow_service = WorkflowService()