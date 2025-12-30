"""
Database connection and utilities for the Document Intelligence Platform
"""

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DATABASE_NAME

# Global database variables
client = None
db = None

async def connect_to_mongo():
    """Connect to MongoDB"""
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DATABASE_NAME]
    print("✅ Database connected")

async def close_mongo_connection():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        print("✅ Database disconnected")

def get_database():
    """Get the database instance"""
    return db