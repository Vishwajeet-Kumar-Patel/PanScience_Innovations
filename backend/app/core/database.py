"""
Database connection and initialization.
Handles MongoDB connection with async support.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB connection lifecycle."""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Establish connection to MongoDB."""
        try:
            # Mask password in logs for security
            masked_url = settings.MONGODB_URL
            if "://" in masked_url and "@" in masked_url:
                protocol_end = masked_url.index("://") + 3
                at_pos = masked_url.index("@", protocol_end)
                username_end = masked_url.rfind(":", protocol_end, at_pos)
                if username_end > protocol_end:
                    masked_url = masked_url[:username_end + 1] + "****" + masked_url[at_pos:]
            
            logger.info(f"Connecting to MongoDB at {masked_url}")
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=30000,  # Increased to 30 seconds
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                maxPoolSize=10,
                minPoolSize=1,
                retryWrites=True,
                retryReads=True,
            )
            self.db = self.client[settings.DATABASE_NAME]
            
            # Verify connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            # Create indexes
            await self._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def _create_indexes(self):
        """Create necessary database indexes for performance."""
        try:
            # Documents collection indexes
            await self.db.documents.create_index("file_id", unique=True)
            await self.db.documents.create_index("user_id")
            await self.db.documents.create_index("created_at")
            await self.db.documents.create_index([("metadata.file_name", "text")])
            
            # Chunks collection indexes
            await self.db.chunks.create_index("document_id")
            await self.db.chunks.create_index("chunk_index")
            
            # Users collection indexes (for future auth)
            await self.db.users.create_index("email", unique=True)
            
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncIOMotorDatabase:
    """Dependency for FastAPI routes."""
    return db_manager.get_database()
