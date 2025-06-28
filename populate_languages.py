"""
Script to populate the languages table with existing language configurations.
Run this script after creating the languages table.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.database.models import Language

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Language data from your Node-RED configuration
LANGUAGES_DATA = {
    "he": {"name": "Hebrew", "translationTarget": "google_translate"},
    "sr": {"name": "Serbian", "translationTarget": "google_translate"},
    "hr": {"name": "Croatian", "translationTarget": "google_translate"},
    "bs": {"name": "Bosnian", "translationTarget": "google_translate"},
    "ar": {"name": "Arabic", "translationTarget": "google_translate"},
    "sk": {"name": "Slovak", "translationTarget": "deepl"},
    "et": {"name": "Estonian", "translationTarget": "deepl"},
    "sl": {"name": "Slovenian", "translationTarget": "deepl"},
    "de": {"name": "German", "translationTarget": "deepl"},
    "en": {"name": "English", "translationTarget": "deepl"},
    "cs": {"name": "Czech", "translationTarget": "deepl"},
    "fr": {"name": "French", "translationTarget": "deepl"},
    "hu": {"name": "Hungarian", "translationTarget": "deepl"},
    "it": {"name": "Italian", "translationTarget": "deepl"},
    "pl": {"name": "Polish", "translationTarget": "deepl"},
    "es": {"name": "Spanish", "translationTarget": "deepl"},
    "nl": {"name": "Dutch", "translationTarget": "deepl"},
    "pt": {"name": "Portuguese", "translationTarget": "deepl"},
    "ru": {"name": "Russian", "translationTarget": "deepl"},
    "uk": {"name": "Ukrainian", "translationTarget": "deepl"},
    "tr": {"name": "Turkish", "translationTarget": "deepl"},
    "el": {"name": "Greek", "translationTarget": "deepl"},
    "bg": {"name": "Bulgarian", "translationTarget": "deepl"},
    "ro": {"name": "Romanian", "translationTarget": "deepl"},
    "sv": {"name": "Swedish", "translationTarget": "deepl"},
    "fi": {"name": "Finnish", "translationTarget": "deepl"}
}

async def populate_languages():
    """Populate the database with language configurations"""
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    # Create async session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            logger.info("Starting language population...")
            
            # Optional: Clear existing languages (uncomment if you want to start fresh)
            # from sqlalchemy import text
            # logger.info("Clearing existing languages...")
            # await session.execute(text("DELETE FROM languages"))
            # await session.commit()
            
            # Add each language
            languages_added = 0
            languages_skipped = 0
            
            for code, lang_data in LANGUAGES_DATA.items():
                # Check if language already exists
                existing = await session.get(Language, code)
                if existing:
                    logger.info(f"Language {code} already exists, skipping...")
                    languages_skipped += 1
                    continue
                
                logger.info(f"Adding language: {code} - {lang_data['name']}")
                
                language = Language(
                    code=code,
                    name=lang_data["name"],
                    translation_target=lang_data["translationTarget"],
                    is_active=True
                )
                session.add(language)
                languages_added += 1
            
            # Commit all changes
            await session.commit()
            logger.info(f"Successfully populated database! Added: {languages_added}, Skipped: {languages_skipped}")
            
        except Exception as e:
            logger.error(f"Error populating languages: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()
    
    await engine.dispose()

async def verify_population():
    """Verify that the languages were populated correctly"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        from sqlalchemy import select, func
        
        # Count total languages
        stmt = select(func.count(Language.code)).where(Language.is_active == True)
        result = await session.execute(stmt)
        total_count = result.scalar()
        
        logger.info(f"\n=== VERIFICATION ===")
        logger.info(f"Total active languages: {total_count}")
        
        # Get languages by translation target
        stmt = select(Language.translation_target, func.count(Language.code)).where(
            Language.is_active == True
        ).group_by(Language.translation_target)
        result = await session.execute(stmt)
        
        logger.info("Languages by translation target:")
        for target, count in result.fetchall():
            logger.info(f"  {target}: {count} languages")
        
        # Show first few languages as sample
        stmt = select(Language).where(Language.is_active == True).limit(5)
        result = await session.execute(stmt)
        languages = result.scalars().all()
        
        logger.info("\nSample languages:")
        for lang in languages:
            logger.info(f"  {lang.code}: {lang.name} -> {lang.translation_target}")
    
    await engine.dispose()

if __name__ == "__main__":
    async def main():
        await populate_languages()
        await verify_population()
    
    asyncio.run(main())