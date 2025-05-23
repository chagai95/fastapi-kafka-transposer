from sqlalchemy import Column, String, Text, ARRAY, JSON, DateTime, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()

class SourceType(str, enum.Enum):
    PEERTUBE = "peertube"
    GENERAL = "general"

class JobStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ERROR = "error"

class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"
    
    source_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    video_id = Column(String, nullable=True)  # For PeerTube videos
    language = Column(String, nullable=True)  # Source language
    source_status = Column(String, default=JobStatus.IN_PROGRESS)
    workflow_step = Column(String, default="0")  # Track which step in workflow we're on
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # JSON fields to store results
    transcription = Column(JSON, nullable=True)
    translations = Column(JSON, nullable=True)  # Store all translations as JSON
    target_language_ids = Column(ARRAY(String), nullable=True)  # Target languages

    
    def to_dict(self):
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "url": self.url,
            "video_id": self.video_id,
            "language": self.language,
            "source_status": self.source_status,
            "transcription": self.transcription,
            "translations": self.translations,
            "target_language_ids": self.target_language_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }