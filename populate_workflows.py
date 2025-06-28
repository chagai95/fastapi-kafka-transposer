"""
Script to populate the database with existing workflow configurations from config.py
Run this script to migrate your existing workflows into the database.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings, WORKFLOW_CONFIG
from app.database.models import WorkflowConfiguration, WorkflowStep, RouteConfiguration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Route parameter configurations
ROUTE_CONFIGS = {
    "/transcribe-and-translate/video": {
        "workflow_name": "peertube",
        "description": "Transcribe and translate PeerTube videos",
        "required_parameters": {
            "language": {"type": "string", "description": "Source language code"},
            "videoId": {"type": "string", "description": "PeerTube video ID"},
            "url": {"type": "string", "description": "Video URL"}
        },
        "optional_parameters": {
            "peertubeInstanceBaseDomain": {"type": "string", "description": "PeerTube instance base domain"}
        }
    },
    "/transcribe-and-translate": {
        "workflow_name": "general",
        "description": "Transcribe and translate general media URLs",
        "required_parameters": {
            "url": {"type": "string", "description": "Media URL"}
        },
        "optional_parameters": {
            "language": {"type": "string", "description": "Source language code"}
        }
    },
    "/translate": {
        "workflow_name": "translation_only",
        "description": "Translate text directly without transcription",
        "required_parameters": {
            "input": {"type": "string", "description": "Text to translate"},
            "source_language_id": {"type": "string", "description": "Source language code"},
            "target_language_ids": {"type": "array", "description": "Target language codes"}
        },
        "optional_parameters": {
            "unique_hash": {"type": "string", "description": "Unique hash for the translation"}
        }
    }
}

async def populate_workflows():
    """Populate the database with workflow configurations"""
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    # Create async session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            logger.info("Starting workflow population...")
            
            # Clear existing data (optional - comment out if you want to keep existing data)
            from sqlalchemy import text
            logger.info("Clearing existing workflow and route configurations...")
            await session.execute(text("DELETE FROM workflow_steps"))
            await session.execute(text("DELETE FROM workflow_configurations")) 
            await session.execute(text("DELETE FROM route_configurations"))
            await session.commit()
            
            # Create workflow configurations
            for workflow_name, workflow_config in WORKFLOW_CONFIG.items():
                logger.info(f"Creating workflow: {workflow_name}")
                
                # Create workflow
                workflow = WorkflowConfiguration(
                    name=workflow_name,
                    description=f"Workflow for {workflow_name} processing",
                    is_active=True
                )
                session.add(workflow)
                await session.flush()  # Get the ID
                
                # Create workflow steps
                steps = workflow_config.get("steps", [])
                for step_index, step_config in enumerate(steps):
                    logger.info(f"  Creating step {step_index}: {step_config['topic']}")
                    
                    step = WorkflowStep(
                        workflow_id=workflow.id,
                        step_order=step_index,
                        topic=step_config["topic"],
                        response_topic=step_config["response_topic"],
                        description=f"Step {step_index} - {step_config['topic']}"
                    )
                    session.add(step)
            
            # Create route configurations
            for route_path, route_config in ROUTE_CONFIGS.items():
                logger.info(f"Creating route configuration: {route_path}")
                
                route = RouteConfiguration(
                    route_path=route_path,
                    workflow_name=route_config["workflow_name"],
                    required_parameters=route_config["required_parameters"],
                    optional_parameters=route_config["optional_parameters"],
                    description=route_config["description"],
                    is_active=True
                )
                session.add(route)
            
            # Commit all changes
            await session.commit()
            logger.info("Successfully populated database with workflow configurations!")
            
            # Verify what was created
            from sqlalchemy import text
            
            # Count workflows
            result = await session.execute(text("SELECT COUNT(*) FROM workflow_configurations"))
            workflow_count = result.scalar()
            
            # Count steps
            result = await session.execute(text("SELECT COUNT(*) FROM workflow_steps"))
            step_count = result.scalar()
            
            # Count routes
            result = await session.execute(text("SELECT COUNT(*) FROM route_configurations"))
            route_count = result.scalar()
            
            logger.info(f"Created: {workflow_count} workflows, {step_count} steps, {route_count} routes")
            
        except Exception as e:
            logger.error(f"Error populating workflows: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()
    
    await engine.dispose()

async def verify_population():
    """Verify that the data was populated correctly"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        # Get all workflows with their steps
        stmt = select(WorkflowConfiguration).options(
            selectinload(WorkflowConfiguration.steps)
        ).where(WorkflowConfiguration.is_active == True)
        
        result = await session.execute(stmt)
        workflows = result.scalars().all()
        
        logger.info("\n=== VERIFICATION ===")
        for workflow in workflows:
            logger.info(f"Workflow: {workflow.name}")
            sorted_steps = sorted(workflow.steps, key=lambda s: s.step_order)
            for step in sorted_steps:
                logger.info(f"  Step {step.step_order}: {step.topic} -> {step.response_topic}")
        
        # Get all route configurations
        stmt = select(RouteConfiguration).where(RouteConfiguration.is_active == True)
        result = await session.execute(stmt)
        routes = result.scalars().all()
        
        logger.info("\nRoute Configurations:")
        for route in routes:
            logger.info(f"  {route.route_path} -> {route.workflow_name}")
            logger.info(f"    Required: {list(route.required_parameters.keys())}")
            logger.info(f"    Optional: {list(route.optional_parameters.keys()) if route.optional_parameters else []}")
    
    await engine.dispose()

if __name__ == "__main__":
    async def main():
        await populate_workflows()
        await verify_population()
    
    asyncio.run(main())