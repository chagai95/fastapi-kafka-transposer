import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import TranscriptionJob, JobStatus
from app.services.kafka_service import kafka_service
from app.config import settings
from app.database.db import async_session

logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self):
        self.workflows = settings.WORKFLOW_CONFIG
        
    async def start_job(self, session: AsyncSession, job: TranscriptionJob):
        """Start a job by sending it to the first step in its workflow"""
        workflow = self.workflows.get(job.source_type)
        if not workflow:
            logger.error(f"No workflow found for source_type: {job.source_type}")
            job.source_status = JobStatus.ERROR
            await session.commit()
            return
            
        # Send to first step
        await self._send_to_step(job, 0)
        logger.info(f"Started job {job.source_id} with workflow '{job.source_type}'")
    
    async def process_response(self, topic: str, data: dict):
        """Process a response from any topic and advance the workflow"""
        logger.info(f"Processing response from topic '{topic}': {data}")
        
        source_id = data.get("source_id")
        if not source_id:
            logger.error("Received response without source_id")
            return
            
        async with async_session() as session:
            # Get the job
            stmt = select(TranscriptionJob).where(TranscriptionJob.source_id == source_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job not found for source_id: {source_id}")
                return
            
            # Update job with response data
            await self._update_job_with_response(job, data)
            await session.commit()
            
            # Move to next step
            await self._advance_workflow(session, job)
    
    async def _update_job_with_response(self, job: TranscriptionJob, data: dict):
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
        
    async def _advance_workflow(self, session: AsyncSession, job: TranscriptionJob):
        """Move job to next step in workflow"""
        workflow = self.workflows.get(job.source_type)
        if not workflow:
            logger.error(f"No workflow found for source_type: {job.source_type}")
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
        await self._send_to_step(job, next_step)
        logger.info(f"Advanced job {job.source_id} to step {next_step}")
    
    async def _send_to_step(self, job: TranscriptionJob, step_index: int):
        """Send job data to a specific workflow step"""
        workflow = self.workflows.get(job.source_type)
        if not workflow or step_index >= len(workflow["steps"]):
            logger.error(f"Invalid step {step_index} for workflow {job.source_type}")
            return
            
        step = workflow["steps"][step_index]
        topic = step["topic"]
        
        # Only send the source_id - services can query the database for full data
        message = {
            "source_id": job.source_id
        }
        
        await kafka_service.send_message(topic, message, key=job.source_id)
        logger.info(f"Sent job {job.source_id} to topic '{topic}' (step {step_index})")
    
    def get_response_topics(self):
        """Get all response topics from all workflows for consumer registration"""
        response_topics = set()
        for workflow_name, workflow in self.workflows.items():
            for step in workflow["steps"]:
                response_topic = step.get("response_topic")
                if response_topic:
                    response_topics.add(response_topic)
        return list(response_topics)

# Create global instance
workflow_service = WorkflowService()