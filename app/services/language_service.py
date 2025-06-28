import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Language

logger = logging.getLogger(__name__)

class LanguageService:
    def __init__(self):
        self._language_cache = {}
        self._translation_targets_cache = None
        
    async def get_all_languages(self, session: AsyncSession) -> List[Language]:
        """Get all active languages from database"""
        stmt = select(Language).where(Language.is_active == True).order_by(Language.code)
        result = await session.execute(stmt)
        return result.scalars().all()
    
    async def get_language_by_code(self, session: AsyncSession, code: str) -> Optional[Language]:
        """Get a specific language by code"""
        # Check cache first
        if code in self._language_cache:
            return self._language_cache[code]
            
        language = await session.get(Language, code)
        if language and language.is_active:
            self._language_cache[code] = language
            return language
        return None
    
    async def get_translation_targets(self, session: AsyncSession) -> Dict[str, str]:
        """Get translation targets for all languages"""
        # Check cache first
        if self._translation_targets_cache:
            return self._translation_targets_cache
            
        languages = await self.get_all_languages(session)
        targets = {lang.code: lang.translation_target for lang in languages}
        
        # Cache the result
        self._translation_targets_cache = targets
        logger.debug(f"Loaded {len(targets)} translation targets from database")
        
        return targets
    
    async def get_supported_languages_format(self, session: AsyncSession) -> List[Dict]:
        """Get languages in the format expected by the frontend"""
        languages = await self.get_all_languages(session)
        
        # Get all language codes as targets
        all_codes = [lang.code for lang in languages]
        
        # Build response format
        supported_languages = [
            {
                "code": lang.code,
                "name": lang.name,
                "targets": all_codes
            }
            for lang in languages
        ]
        
        return supported_languages
    
    async def validate_language_codes(self, session: AsyncSession, codes: List[str]) -> Dict[str, bool]:
        """Validate if language codes exist and are active"""
        validation_results = {}
        
        for code in codes:
            language = await self.get_language_by_code(session, code)
            validation_results[code] = language is not None
            
        return validation_results
    
    def clear_cache(self):
        """Clear the language cache"""
        self._language_cache.clear()
        self._translation_targets_cache = None
        logger.info("Language cache cleared")

# Create global instance
language_service = LanguageService()