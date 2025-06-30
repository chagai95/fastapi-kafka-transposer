from sqlalchemy import Column, String, Text, ARRAY, JSON, DateTime, Enum, ForeignKey, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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

# New model for language configurations
class Language(Base):
    __tablename__ = "languages"
    
    code = Column(String, primary_key=True)  # e.g., "en", "de", "pt-pt"
    name = Column(String, nullable=False)    # e.g., "English", "German"
    translation_target = Column(String, nullable=False)  # "deepl" or "google_translate"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# New models for dynamic workflows
class WorkflowConfiguration(Base):
    __tablename__ = "workflow_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)  # e.g., "peertube", "general", "translation_only"
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to workflow steps
    steps = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, ForeignKey("workflow_configurations.id"), nullable=False)
    step_order = Column(Integer, nullable=False)  # 0, 1, 2, etc.
    topic = Column(String, nullable=False)
    response_topic = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationship back to workflow
    workflow = relationship("WorkflowConfiguration", back_populates="steps")

class RouteConfiguration(Base):
    __tablename__ = "route_configurations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    route_path = Column(String, unique=True, nullable=False)  # e.g., "/transcribe-and-translate/video"
    workflow_name = Column(String, nullable=False)  # Links to WorkflowConfiguration.name
    required_parameters = Column(JSON, nullable=False)  # JSON schema for required parameters
    optional_parameters = Column(JSON, nullable=True)  # JSON schema for optional parameters
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
# Add this to app/database/models.py

class TranslationJob(Base):
    __tablename__ = "translation_jobs"
    
    source_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False, default="translation")
    source_language = Column(String, nullable=False)
    target_language_ids = Column(ARRAY(String), nullable=False)
    input_text = Column(Text, nullable=False)
    format = Column(String, nullable=True)  # Added format field
    translations = Column(JSON, nullable=True)  # {"es": "Hola", "fr": "Bonjour"}
    status = Column(Enum(JobStatus), default=JobStatus.IN_PROGRESS)
    workflow_step = Column(String, default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_language": self.source_language,
            "target_language_ids": self.target_language_ids,
            "input_text": self.input_text,
            "format": self.format,
            "translations": self.translations,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class TranscriptionAndTranslationJob(Base):
    __tablename__ = "transcribe_and_translate"
    
    source_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    video_id = Column(String, nullable=True)  # For PeerTube videos
    peertube_basedomain = Column(String, nullable=True)  # Added PeerTube base domain
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
            "peertube_basedomain": self.peertube_basedomain,
            "language": self.language,
            "source_status": self.source_status,
            "transcription": self.transcription,
            "translations": self.translations,
            "target_language_ids": self.target_language_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }