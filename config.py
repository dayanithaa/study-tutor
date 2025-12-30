import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "sample_mflix"
COLLECTION_NAME = "documents"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

CHROMA_DIR = "chroma_db"
