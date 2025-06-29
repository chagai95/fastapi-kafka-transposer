import asyncio
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.database.db import create_tables, async_session
from app.services.kafka_service import kafka_service
from app.services.workflow_service import workflow_service
from app.logging_config import setup_file_logging
from app.config import settings
from app.services.translation_response_handler import translation_response_handler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Transcription and Translation API",
    description="API for transcribing and translating audio/video content",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)

async def create_response_handler(topic: str):
    """Create a response handler for a specific topic"""
    async def handler(data: dict):
        await workflow_service.process_response(topic, data)
    return handler

@app.on_event("startup")
async def startup_event():
    
    setup_file_logging()
    
    # Create database tables
    await create_tables()
    logger.info("Database tables created")
    
    # Start Kafka producer
    await kafka_service.start_producer()
    
    # Start translation response handler
    await translation_response_handler.start()
    logger.info("Translation response handler started")
    
    # Load response topics from database workflows
    async with async_session() as session:
        try:
            response_topics = await workflow_service.get_response_topics(session)
            logger.info(f"Found response topics from database: {response_topics}")
            
            for topic in response_topics:
                # Create and register handler for this topic
                handler = await create_response_handler(topic)
                await kafka_service.register_consumer(topic, handler)
                await kafka_service.start_consumer(topic)
                logger.info(f"Registered consumer for topic: {topic}")
                
        except Exception as e:
            logger.error(f"Error loading workflows from database: {str(e)}")
            logger.info("Application will continue, but workflows may not work until database is populated")
    
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop translation response handler
    await translation_response_handler.stop()
    # Stop Kafka consumers and producer
    await kafka_service.stop_all_consumers()
    await kafka_service.stop_producer()
    logger.info("Application shutdown complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)