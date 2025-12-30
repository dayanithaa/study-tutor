"""
Configuration settings for the Document Intelligence Platform
"""

import os

# Security
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Database
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "document_intelligence"

# File upload settings
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = ['.pdf', '.ppt', '.pptx', '.zip']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB