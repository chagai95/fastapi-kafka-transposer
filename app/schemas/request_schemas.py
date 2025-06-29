from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Union, Dict
import uuid

class TranscribeVideoRequest(BaseModel):
    videoId: str = Field(alias="videoId")
    url: HttpUrl
    language: Optional[str] = None
    peertubeInstanceBaseDomain: Optional[str] = Field(None, alias="peertubeInstanceBaseDomain")

class GeneralTranscribeRequest(BaseModel):
    url: HttpUrl
    language: Optional[str] = None

class TranslateRequest(BaseModel):
    input: str
    source_language_id: str
    target_language_ids: Union[List[str], str]

class JobStatusResponse(BaseModel):
    status: str
    source_id: str
    transcription: Optional[Dict] = None
    translations: Optional[Dict] = None