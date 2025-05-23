from pydantic_settings import BaseSettings
import os
from typing import List
from dotenv import load_dotenv
load_dotenv()

# Workflow configuration
WORKFLOW_CONFIG = {
    "peertube": {
        "steps": [
            {"topic": "peertube_transcribe_and_translate", "response_topic": "peertube_transcribe_and_translate_response"},
            {"topic": "whisper", "response_topic": "whisper_response"},
            {"topic": "generic_translate", "response_topic": "generic_translate_response"},
            {"topic": "peertube_transcribe_and_translate", "response_topic": "peertube_transcribe_and_translate_response"}
        ]
    }
}

class Settings(BaseSettings):

    # Workflow settings
    WORKFLOW_CONFIG: dict = WORKFLOW_CONFIG

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@postgres:5432/transcription_db")
        
    # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-1:9092,kafka-2:9092")
    
    # Topics
    TOPIC_WHISPER: str = "whisper"
    TOPIC_WHISPER_RESPONSE: str = "whisper_response"
    TOPIC_GENERIC_TRANSLATE: str = "generic_translate"
    TOPIC_GENERIC_TRANSLATE_RESPONSE: str = "generic_translate_response"
    TOPIC_PEERTUBE_TRANSCRIBE_TRANSLATE: str = "peertube_transcribe_and_translate"
    TOPIC_PEERTUBE_TRANSCRIBE_TRANSLATE_RESPONSE: str = "peertube_transcribe_and_translate_response"
    
    # Supported languages
    SUPPORTED_LANGUAGES: List[str] = [
        'en', 'de', 'it', 'fr', 'es', 'et', 'hu', 'pl', 
        'nl', 'cs', 'uk', 'ru', 'tr', 'pt', 'sk', 'ar', 'sr'
    ]

settings = Settings()