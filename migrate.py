"""
Migration script to create the new workflow and route configuration tables.
Run this after updating the models.py file.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migration():
    """Create the new tables"""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
    )
    
    async with engine.begin() as conn:
        # Create only the new tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Migration completed - new tables created")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migration())