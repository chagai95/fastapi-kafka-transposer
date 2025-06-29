# create_translation_table.py
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database.models import Base, TranslationJob

async def create_translation_table():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Create the new translation_jobs table
        await conn.run_sync(Base.metadata.create_all, tables=[TranslationJob.__table__])
        
        # Also make the url nullable in the transcribe_and_translate table
        await conn.execute(text("""
            ALTER TABLE transcribe_and_translate 
            ALTER COLUMN url DROP NOT NULL;
        """))
        
    await engine.dispose()
    print("Migration completed - translation_jobs table created and url made nullable")

if __name__ == "__main__":
    asyncio.run(create_translation_table())