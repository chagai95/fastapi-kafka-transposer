import asyncio
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.database.db import create_tables
from app.services.kafka_service import kafka_service
from app.services.transcription import handle_transcription_response
from app.services.translation import handle_translation_response
from app.config import settings

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

@app.on_event("startup")
async def startup_event():
    # Create database tables
    await create_tables()
    logger.info("Database tables created")
    
    # Start Kafka producer
    await kafka_service.start_producer()
    
    # Register Kafka handlers
    await kafka_service.register_consumer(
        settings.TOPIC_WHISPER_RESPONSE,
        handle_transcription_response
    )
    await kafka_service.register_consumer(
        settings.TOPIC_GENERIC_TRANSLATE_RESPONSE,
        handle_translation_response
    )
    
    # Start Kafka consumers
    await kafka_service.start_consumer(settings.TOPIC_WHISPER_RESPONSE)
    await kafka_service.start_consumer(settings.TOPIC_GENERIC_TRANSLATE_RESPONSE)
    
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop Kafka consumers and producer
    await kafka_service.stop_all_consumers()
    await kafka_service.stop_producer()
    logger.info("Application shutdown complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)