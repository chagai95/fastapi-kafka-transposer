"""
Migration script to add the format column to translation_jobs table.
Run this after updating the models.py file.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def add_format_column():
    """Add format column to translation_jobs table"""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
    )
    
    async with engine.begin() as conn:
        # Add the format column to translation_jobs table
        await conn.execute(text(
            "ALTER TABLE translation_jobs ADD COLUMN IF NOT EXISTS format VARCHAR"
        ))
        logger.info("Added format column to translation_jobs table")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(add_format_column())