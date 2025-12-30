from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from pathlib import Path
import fitz  # PyMuPDF
import pdfplumber
import re
import networkx as nx
import asyncio
import logging
from collections import defaultdict

# Create directories
Path("uploads").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="Document Intelligence Platform", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "document_intelligence"

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
security = HTTPBearer()

# Global database variables
client = None
db = None

# ==================== PYDANTIC MODELS ====================

class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    subjects_uploaded: List[str] = []
    progress_pointer: dict = {}
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class DocumentResponse(BaseModel):
    id: str
    filename: str
    processed: bool
    uploaded_at: datetime
    sections_count: int
    concepts_count: int

# ==================== HELPER FUNCTIONS ====================

def get_password_hash(password):
    # Truncate password to 72 bytes for bcrypt compatibility
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    # Truncate password to 72 bytes for bcrypt compatibility
    if len(plain_password.encode('utf-8')) > 72:
        plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    return user

# ==================== DATABASE STARTUP/SHUTDOWN ====================

@app.on_event("startup")
async def startup_db_client():
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DATABASE_NAME]
    print("✅ Database connected")

@app.on_event("shutdown")
async def shutdown_db_client():
    global client
    if client:
        client.close()
        print("✅ Database disconnected")

# ==================== ADVANCED PDF PROCESSING ====================

class PDFProcessor:
    def __init__(self):
        # Advanced concept patterns with academic precision
        self.concept_patterns = [
            # Definitions and formal concepts
            r'(?:Definition|Define|Def\.?)[:\s]+([A-Z][a-zA-Z\s]{2,40}?)(?:\.|:|;|\n)',
            r'\b([A-Z][a-zA-Z\s]{2,30}?)\s+is\s+(?:defined\s+as|a\s+type\s+of|an?\s+(?:important|key|fundamental|basic|essential))',
            r'(?:The\s+concept\s+of\s+|Key\s+concept[:\s]+)([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            
            # Theorems and principles
            r'(?:Theorem|Lemma|Corollary|Proposition)[:\s]*(\d*\.?\d*\s*)?([A-Z][a-zA-Z\s]{2,40}?)(?:\.|:|;|\n)',
            r'(?:Principle|Law)\s+of\s+([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            r'([A-Z][a-zA-Z\s]{2,30}?)(?:\'s)?\s+(?:Theorem|Principle|Law|Rule)(?:\.|:|;|\n)',
            
            # Methods and algorithms
            r'(?:Algorithm|Method|Technique|Approach)[:\s]+([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            r'([A-Z][a-zA-Z\s]{2,30}?)\s+(?:algorithm|method|technique|approach|procedure)(?:\.|:|;|\n)',
            r'(?:The\s+)?([A-Z][a-zA-Z\s]{2,30}?)\s+(?:method|algorithm)\s+(?:is|works|involves)',
            
            # Mathematical concepts
            r'(?:Formula|Equation)[:\s]+([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            r'([A-Z][a-zA-Z\s]{2,30}?)\s+(?:formula|equation|function|variable)(?:\.|:|;|\n)',
            
            # Academic structures
            r'(?:Chapter|Section)\s+\d+[:\.]?\s*([A-Z][a-zA-Z\s]{2,40}?)(?:\n|\.|$)',
            r'^\s*(\d+\.?\d*\s+[A-Z][a-zA-Z\s]{2,40}?)(?:\n|\.|$)',  # Numbered sections
            
            # Important terms and concepts
            r'(?:Important|Key|Essential|Fundamental|Basic|Core)[:\s]+([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            r'([A-Z][a-zA-Z\s]{2,30}?)\s+(?:is\s+(?:important|essential|fundamental|crucial|vital))',
            
            # Learning objectives
            r'(?:Learn|Study|Understand|Master)[:\s]+([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            r'(?:Introduction\s+to|Overview\s+of)\s+([A-Z][a-zA-Z\s]{2,30}?)(?:\.|:|;|\n)',
            
            # Bold/emphasized text (common in academic PDFs)
            r'\*\*([A-Z][a-zA-Z\s]{2,30}?)\*\*',
            r'__([A-Z][a-zA-Z\s]{2,30}?)__',
            
            # Parenthetical definitions
            r'([A-Z][a-zA-Z\s]{2,30}?)\s*\([^)]{10,100}\)',
            
            # Lists and enumerations
            r'(?:•|\*|-|\d+\.)\s*([A-Z][a-zA-Z\s]{2,30}?)(?:\:|\.|\n)',
        ]
        
        # Enhanced concept validation rules
        self.validation_rules = {
            'min_length': 2,
            'max_length': 60,
            'forbidden_words': {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'this', 'that', 'these', 'those', 'a', 'an', 'is', 'are', 'was', 'were',
                'page', 'figure', 'table', 'chapter', 'section', 'example', 'exercise',
                'problem', 'solution', 'answer', 'question', 'note', 'remark', 'comment',
                'see', 'also', 'can', 'will', 'may', 'should', 'would', 'could', 'must',
                'have', 'has', 'had', 'do', 'does', 'did', 'get', 'got', 'make', 'made',
                'take', 'took', 'give', 'gave', 'put', 'set', 'use', 'used', 'find', 'found'
            },
            'required_patterns': [
                r'^[A-Z]',  # Must start with capital letter
                r'[a-zA-Z]{2,}',  # Must contain at least 2 letters
            ],
            'forbidden_patterns': [
                r'^\d+$',  # Pure numbers
                r'^[^a-zA-Z]*$',  # No letters
                r'http[s]?://',  # URLs
                r'@',  # Email addresses
                r'^\W+$',  # Only special characters
                r'\d{4,}',  # Long numbers (years, IDs, etc.)
                r'^(?:Figure|Fig|Table|Equation|Eq)\s*\d+',  # Figure/table references
                r'^(?:Page|P\.)\s*\d+',  # Page references
                r'^\w{1,2}$',  # Too short abbreviations
            ],
            'academic_indicators': {
                'high_value': {
                    'theorem', 'principle', 'law', 'theory', 'model', 'algorithm', 'method',
                    'formula', 'equation', 'function', 'concept', 'definition', 'axiom',
                    'lemma', 'corollary', 'proposition', 'hypothesis', 'conjecture'
                },
                'medium_value': {
                    'approach', 'technique', 'framework', 'system', 'process', 'procedure',
                    'strategy', 'mechanism', 'structure', 'pattern', 'property', 'characteristic',
                    'feature', 'aspect', 'element', 'component', 'factor', 'parameter'
                },
                'domain_specific': {
                    # Mathematics
                    'calculus', 'algebra', 'geometry', 'statistics', 'probability', 'topology',
                    'analysis', 'differential', 'integral', 'matrix', 'vector', 'polynomial',
                    # Physics
                    'mechanics', 'thermodynamics', 'electromagnetism', 'quantum', 'relativity',
                    'energy', 'force', 'momentum', 'acceleration', 'velocity', 'frequency',
                    # Computer Science
                    'programming', 'software', 'hardware', 'database', 'network', 'security',
                    'artificial', 'intelligence', 'machine', 'learning', 'data', 'structure',
                    # Chemistry
                    'molecular', 'atomic', 'chemical', 'reaction', 'compound', 'element',
                    # Biology
                    'cellular', 'genetic', 'evolution', 'organism', 'protein', 'enzyme',
                    # Economics
                    'market', 'economic', 'financial', 'investment', 'capital', 'revenue',
                    # Psychology
                    'cognitive', 'behavioral', 'psychological', 'mental', 'emotional'
                }
            }
        }
        
        # Enhanced relationship patterns for better accuracy
        self.relationship_patterns = {
            'prerequisite': [
                r'(?:requires?|needs?|depends?\s+on|builds?\s+on|based\s+on|relies\s+on)\s+([^.]{5,50})',
                r'(?:before|prior\s+to|prerequisite\s+for|foundation\s+for)\s+([^,]{5,50})',
                r'(?:assumes?|given|provided)\s+([^.]{5,50})',
                r'(?:first|initially|begin\s+with)\s+([^.]{5,50})',
                r'(?:fundamental|basic|elementary)\s+([^.]{5,50})\s+(?:is\s+needed|required)'
            ],
            'related': [
                r'(?:similar\s+to|related\s+to|connected\s+to|associated\s+with)\s+([^.]{5,50})',
                r'(?:see\s+also|compare\s+with|cf\.|versus|vs\.?)\s+([^.]{5,50})',
                r'(?:analogous\s+to|like|resembles?|corresponds?\s+to)\s+([^.]{5,50})',
                r'(?:in\s+contrast\s+to|unlike|different\s+from)\s+([^.]{5,50})',
                r'(?:together\s+with|along\s+with|combined\s+with)\s+([^.]{5,50})'
            ],
            'contains': [
                r'(?:includes?|contains?|consists?\s+of|comprises?)\s+([^.]{5,50})',
                r'(?:types?\s+of|kinds?\s+of|forms?\s+of|varieties?\s+of)\s+([^.]{5,50})',
                r'(?:examples?\s+of|instances?\s+of|cases?\s+of)\s+([^.]{5,50})',
                r'(?:components?\s+of|parts?\s+of|elements?\s+of)\s+([^.]{5,50})',
                r'(?:subdivided\s+into|categorized\s+as|classified\s+as)\s+([^.]{5,50})'
            ],
            'causes': [
                r'(?:causes?|leads?\s+to|results?\s+in|produces?)\s+([^.]{5,50})',
                r'(?:due\s+to|because\s+of|owing\s+to|as\s+a\s+result\s+of)\s+([^.]{5,50})',
                r'(?:triggers?|initiates?|generates?|creates?)\s+([^.]{5,50})'
            ],
            'applies': [
                r'(?:used\s+in|applied\s+to|employed\s+in|utilized\s+for)\s+([^.]{5,50})',
                r'(?:application\s+of|use\s+of|implementation\s+of)\s+([^.]{5,50})',
                r'(?:solves?|addresses?|handles?|deals\s+with)\s+([^.]{5,50})'
            ]
        }

    def extract_pdf_content(self, pdf_path: str) -> Dict[str, Any]:
        """Enhanced PDF content extraction with better accuracy and structure"""
        try:
            doc = fitz.open(pdf_path)
            plumber_doc = pdfplumber.open(pdf_path)
        except Exception as e:
            print(f"Error opening PDF: {e}")
            return {
                "sections": [{"title": "Document", "content": "Failed to process PDF", "page": 1, "level": 1}],
                "figures": [],
                "concepts": [],
                "relationships": [],
                "total_pages": 1,
                "extraction_metadata": {"error": str(e), "success": False}
            }
        
        sections = []
        figures = []
        all_text = ""
        page_texts = []
        extraction_stats = {
            "pages_processed": 0,
            "text_blocks_found": 0,
            "images_found": 0,
            "tables_found": 0,
            "headings_found": 0
        }
        
        try:
            total_pages = min(len(doc), 50)  # Process up to 50 pages for performance
            
            for page_num in range(total_pages):
                try:
                    page = doc[page_num]
                    plumber_page = plumber_doc.pages[page_num] if page_num < len(plumber_doc.pages) else None
                    
                    # Extract text with better formatting preservation
                    page_text = self._extract_page_text_enhanced(page, plumber_page)
                    page_texts.append({
                        "page": page_num + 1,
                        "text": page_text,
                        "char_count": len(page_text)
                    })
                    
                    if page_text:
                        all_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
                    
                    # Extract structured sections with better detection
                    page_sections = self._extract_page_sections_enhanced(page, page_num, page_text)
                    sections.extend(page_sections)
                    extraction_stats["headings_found"] += len(page_sections)
                    
                    # Extract figures, tables, and images
                    page_figures = self._extract_page_figures_enhanced(page, plumber_page, page_num)
                    figures.extend(page_figures)
                    extraction_stats["images_found"] += len([f for f in page_figures if f["type"] == "image"])
                    extraction_stats["tables_found"] += len([f for f in page_figures if f["type"] == "table"])
                    
                    # Count text blocks
                    blocks = page.get_text("dict")["blocks"]
                    extraction_stats["text_blocks_found"] += len([b for b in blocks if "lines" in b])
                    
                    extraction_stats["pages_processed"] += 1
                        
                except Exception as e:
                    print(f"Error processing page {page_num}: {e}")
                    continue
            
            # Create default section if none found
            if not sections:
                sections = [{
                    "title": "Document Content", 
                    "content": all_text[:1000] + "..." if len(all_text) > 1000 else all_text,
                    "page": 1, 
                    "level": 1,
                    "font_size": 12,
                    "is_bold": False,
                    "word_count": len(all_text.split())
                }]
            
            # Enhanced concept extraction with better accuracy
            try:
                concepts = self._extract_concepts_enhanced(all_text, sections, page_texts)
                extraction_stats["concepts_extracted"] = len(concepts)
            except Exception as e:
                print(f"Error extracting concepts: {e}")
                concepts = []
                extraction_stats["concepts_extracted"] = 0
            
            # Enhanced relationship extraction
            try:
                relationships = self._extract_relationships_enhanced(all_text, concepts, sections)
                extraction_stats["relationships_found"] = len(relationships)
            except Exception as e:
                print(f"Error extracting relationships: {e}")
                relationships = []
                extraction_stats["relationships_found"] = 0
            
            # Calculate document statistics
            doc_stats = {
                "total_characters": len(all_text),
                "total_words": len(all_text.split()),
                "avg_words_per_page": len(all_text.split()) / max(extraction_stats["pages_processed"], 1),
                "language_detected": self._detect_language(all_text),
                "document_type": self._classify_document_type(all_text, sections),
                "reading_level": self._estimate_reading_level(all_text)
            }
            
            return {
                "sections": sections,
                "figures": figures,
                "concepts": concepts,
                "relationships": relationships,
                "total_pages": len(doc),
                "page_texts": page_texts,
                "extraction_metadata": {
                    "success": True,
                    "extraction_stats": extraction_stats,
                    "document_stats": doc_stats,
                    "processing_time": datetime.utcnow().isoformat(),
                    "processor_version": "2.0_enhanced"
                }
            }
            
        except Exception as e:
            print(f"Error in PDF processing: {e}")
            return {
                "sections": [{"title": "Document", "content": "Processing error occurred", "page": 1, "level": 1}],
                "figures": [],
                "concepts": [],
                "relationships": [],
                "total_pages": len(doc) if 'doc' in locals() else 1,
                "page_texts": [],
                "extraction_metadata": {
                    "success": False,
                    "error": str(e),
                    "extraction_stats": extraction_stats
                }
            }
        finally:
            try:
                doc.close()
                plumber_doc.close()
            except:
                pass

    def _extract_page_text_enhanced(self, page, plumber_page) -> str:
        """Extract text with better formatting and structure preservation"""
        try:
            # Try pdfplumber first for better text extraction
            if plumber_page:
                text = plumber_page.extract_text()
                if text and len(text.strip()) > 50:
                    return text
            
            # Fallback to PyMuPDF with better formatting
            text_dict = page.get_text("dict")
            formatted_text = ""
            
            for block in text_dict["blocks"]:
                if "lines" not in block:
                    continue
                
                block_text = ""
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        span_text = span["text"]
                        # Preserve formatting indicators
                        if span.get("flags", 0) & 2**4:  # Bold
                            span_text = f"**{span_text}**"
                        line_text += span_text
                    
                    if line_text.strip():
                        block_text += line_text + "\n"
                
                if block_text.strip():
                    formatted_text += block_text + "\n"
            
            return formatted_text
            
        except Exception as e:
            print(f"Error extracting page text: {e}")
            return page.get_text() if page else ""
    
    def _extract_page_sections_enhanced(self, page, page_num: int, page_text: str) -> List[Dict[str, Any]]:
        """Enhanced section extraction with better heading detection"""
        sections = []
        
        try:
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text or len(text) < 3:
                            continue
                            
                        font_size = span["size"]
                        is_bold = bool(span.get("flags", 0) & 2**4)
                        font_name = span.get("font", "").lower()
                        
                        # Enhanced heading detection
                        if self._is_heading_enhanced(text, font_size, is_bold, font_name, page_text):
                            level = self._determine_heading_level_enhanced(font_size, is_bold, font_name)
                            content = self._get_section_content_enhanced(page_text, text)
                            
                            sections.append({
                                "title": text,
                                "content": content,
                                "page": page_num + 1,
                                "level": level,
                                "font_size": font_size,
                                "is_bold": is_bold,
                                "font_name": font_name,
                                "word_count": len(content.split()) if content else 0,
                                "char_count": len(content) if content else 0
                            })
        
        except Exception as e:
            print(f"Error extracting sections from page {page_num}: {e}")
        
        return sections
    
    def _extract_page_figures_enhanced(self, page, plumber_page, page_num: int) -> List[Dict[str, Any]]:
        """Enhanced figure and table extraction"""
        figures = []
        
        try:
            # Extract tables using pdfplumber
            if plumber_page:
                tables = plumber_page.extract_tables()
                for i, table in enumerate(tables):
                    if table and len(table) > 1:  # Valid table
                        figures.append({
                            "number": str(i + 1),
                            "caption": f"Table {i + 1} on page {page_num + 1}",
                            "page": page_num + 1,
                            "type": "table",
                            "rows": len(table),
                            "columns": len(table[0]) if table else 0,
                            "data": table[:5] if len(table) > 5 else table  # Store sample data
                        })
            
            # Extract images
            images = page.get_images()
            for i, img in enumerate(images):
                try:
                    # Get image properties
                    xref = img[0]
                    base_image = page.parent.extract_image(xref)
                    
                    figures.append({
                        "number": str(i + 1),
                        "caption": f"Image {i + 1} on page {page_num + 1}",
                        "page": page_num + 1,
                        "type": "image",
                        "width": base_image.get("width", 0),
                        "height": base_image.get("height", 0),
                        "format": base_image.get("ext", "unknown"),
                        "size_bytes": len(base_image.get("image", b""))
                    })
                except Exception as e:
                    print(f"Error processing image {i}: {e}")
                    continue
            
            # Extract figure captions from text
            page_text = page.get_text()
            caption_patterns = [
                r'(?:Figure|Fig\.?)\s+(\d+)[:\.]?\s*([^\n]{10,200})',
                r'(?:Table)\s+(\d+)[:\.]?\s*([^\n]{10,200})',
                r'(?:Diagram|Chart|Graph)\s+(\d+)[:\.]?\s*([^\n]{10,200})'
            ]
            
            for pattern in caption_patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    fig_num = match.group(1)
                    caption = match.group(2).strip()
                    
                    # Update existing figure or create new one
                    existing_fig = None
                    for fig in figures:
                        if fig["number"] == fig_num and fig["page"] == page_num + 1:
                            existing_fig = fig
                            break
                    
                    if existing_fig:
                        existing_fig["caption"] = caption
                    else:
                        figures.append({
                            "number": fig_num,
                            "caption": caption,
                            "page": page_num + 1,
                            "type": "figure",
                            "source": "caption_only"
                        })
        
        except Exception as e:
            print(f"Error extracting figures from page {page_num}: {e}")
        
        return figures
    
    def _is_heading_enhanced(self, text: str, font_size: float, is_bold: bool, font_name: str, page_text: str) -> bool:
        """Enhanced heading detection with multiple criteria"""
        # Skip very long text
        if len(text) > 150:
            return False
        
        # Check for obvious heading patterns
        heading_patterns = [
            r'^(?:Chapter|Section|Part)\s+\d+',
            r'^\d+\.?\d*\s+[A-Z]',
            r'^[A-Z][A-Za-z\s]+$',
            r'^(?:Introduction|Conclusion|Summary|Abstract|References|Bibliography)$',
            r'^(?:Definition|Theorem|Lemma|Proof|Example|Exercise)(?:\s+\d+)?$',
            r'^\d+\.\d+(?:\.\d+)?\s+[A-Z]'
        ]
        
        for pattern in heading_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # Font-based detection
        if font_size > 14 and is_bold:
            return True
        
        if font_size > 16:  # Large font likely a heading
            return True
        
        # Check if font name suggests heading
        heading_fonts = ['bold', 'heavy', 'black', 'title', 'heading']
        if any(font_word in font_name for font_word in heading_fonts):
            return True
        
        # Structure-based detection
        if (len(text) < 80 and is_bold and 
            not text.endswith('.') and 
            not text.startswith('•') and
            text.count(' ') < 8):  # Not too many words
            return True
        
        # Check if text appears to be standalone (surrounded by whitespace in page)
        if len(text) < 60 and text in page_text:
            text_pos = page_text.find(text)
            if text_pos > 0:
                before = page_text[max(0, text_pos-50):text_pos]
                after = page_text[text_pos+len(text):text_pos+len(text)+50]
                
                # Check for paragraph breaks around the text
                if '\n\n' in before and '\n' in after:
                    return True
        
        return False
    
    def _determine_heading_level_enhanced(self, font_size: float, is_bold: bool, font_name: str) -> int:
        """Enhanced heading level determination"""
        # Font size based levels
        if font_size > 20:
            return 1  # Main title
        elif font_size > 16:
            return 2  # Major section
        elif font_size > 14:
            return 3  # Subsection
        elif font_size > 12:
            return 4  # Minor heading
        else:
            # Use other indicators
            if is_bold and 'bold' in font_name.lower():
                return 4
            return 5
    
    def _get_section_content_enhanced(self, page_text: str, title: str) -> str:
        """Enhanced section content extraction"""
        try:
            # Find the title in the text
            title_pos = page_text.find(title)
            if title_pos == -1:
                return ""
            
            # Get text after the title
            content_start = title_pos + len(title)
            
            # Find the next heading or end of meaningful content
            remaining_text = page_text[content_start:]
            
            # Look for next heading patterns
            next_heading_patterns = [
                r'\n\n[A-Z][A-Za-z\s]{5,50}\n',
                r'\n\d+\.?\d*\s+[A-Z]',
                r'\n(?:Chapter|Section)\s+\d+'
            ]
            
            end_pos = len(remaining_text)
            for pattern in next_heading_patterns:
                match = re.search(pattern, remaining_text)
                if match:
                    end_pos = min(end_pos, match.start())
            
            # Limit content length
            content = remaining_text[:min(end_pos, 2000)]
            
            # Clean up the content
            content = re.sub(r'\s+', ' ', content).strip()
            
            return content
            
        except Exception as e:
            print(f"Error extracting section content: {e}")
            return ""
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection"""
        if not text:
            return "unknown"
        
        # Simple heuristic based on common words
        english_indicators = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with']
        text_lower = text.lower()
        
        english_count = sum(1 for word in english_indicators if word in text_lower)
        
        if english_count >= 3:
            return "english"
        else:
            return "other"
    
    def _classify_document_type(self, text: str, sections: List[Dict]) -> str:
        """Classify the type of document"""
        text_lower = text.lower()
        
        # Academic paper indicators
        academic_indicators = ['abstract', 'introduction', 'methodology', 'results', 'conclusion', 'references']
        academic_count = sum(1 for indicator in academic_indicators if indicator in text_lower)
        
        if academic_count >= 3:
            return "academic_paper"
        
        # Textbook indicators
        textbook_indicators = ['chapter', 'exercise', 'example', 'definition', 'theorem']
        textbook_count = sum(1 for indicator in textbook_indicators if indicator in text_lower)
        
        if textbook_count >= 2:
            return "textbook"
        
        # Manual/guide indicators
        manual_indicators = ['step', 'procedure', 'instruction', 'guide', 'manual']
        manual_count = sum(1 for indicator in manual_indicators if indicator in text_lower)
        
        if manual_count >= 2:
            return "manual"
        
        return "general"
    
    def _estimate_reading_level(self, text: str) -> str:
        """Estimate reading difficulty level"""
        if not text:
            return "unknown"
        
        words = text.split()
        sentences = text.count('.') + text.count('!') + text.count('?')
        
        if len(words) == 0 or sentences == 0:
            return "unknown"
        
        avg_words_per_sentence = len(words) / sentences
        
        # Simple heuristic
        if avg_words_per_sentence > 25:
            return "advanced"
        elif avg_words_per_sentence > 15:
            return "intermediate"
        else:
            return "basic"
    
    def _extract_concepts_enhanced(self, text: str, sections: List[Dict], page_texts: List[Dict]) -> List[Dict[str, Any]]:
        """Enhanced concept extraction with better accuracy and page tracking"""
        concepts = []
        concept_id = 0
        found_concepts = set()
        
        # Extract from section titles (highest priority)
        for section in sections:
            title = section["title"]
            
            # Skip obvious non-concepts
            if re.match(r'^(?:Chapter|Section|Part|Figure|Table|Page)\s+\d+', title, re.IGNORECASE):
                continue
            if len(title.split()) > 8:
                continue
                
            validation = self._validate_concept(title, section.get("content", ""))
            
            if validation['valid'] and validation['cleaned_name'].lower() not in found_concepts:
                concepts.append({
                    "id": f"concept_{concept_id}",
                    "name": validation['cleaned_name'],
                    "type": validation['type'],
                    "page": section["page"],
                    "description": section["content"][:300] + "..." if len(section.get("content", "")) > 300 else section.get("content", ""),
                    "source": "heading",
                    "importance": min(1.0, validation['score'] + (1.0 - section["level"] * 0.1)),
                    "quality_score": validation['score'],
                    "confidence": "high",
                    "context": f"Section heading: {title}",
                    "extraction_method": "section_title"
                })
                found_concepts.add(validation['cleaned_name'].lower())
                concept_id += 1
        
        # Extract from page content with page tracking
        for page_info in page_texts:
            page_num = page_info["page"]
            page_text = page_info["text"]
            
            if not page_text or len(page_text.strip()) < 100:
                continue
            
            # Process in smaller chunks for better context
            chunks = self._split_text_into_chunks(page_text, 800)
            
            for chunk_idx, chunk in enumerate(chunks):
                for pattern_idx, pattern in enumerate(self.concept_patterns):
                    matches = re.finditer(pattern, chunk, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        try:
                            concept_name = match.group(1).strip()
                            
                            # Skip if too similar to existing concepts
                            if self._is_similar_concept(concept_name, found_concepts):
                                continue
                            
                            # Enhanced context extraction
                            start = max(0, match.start() - 200)
                            end = min(len(chunk), match.end() + 200)
                            context = chunk[start:end]
                            
                            validation = self._validate_concept(concept_name, context)
                            
                            if (validation['valid'] and 
                                validation['cleaned_name'].lower() not in found_concepts):
                                
                                # Calculate importance with page position
                                pattern_importance = self._get_pattern_importance(pattern_idx)
                                page_importance = 1.0 - ((page_num - 1) * 0.05)  # Earlier pages more important
                                chunk_importance = 1.0 - (chunk_idx * 0.1)
                                
                                final_importance = validation['score'] * pattern_importance * page_importance * chunk_importance
                                
                                concepts.append({
                                    "id": f"concept_{concept_id}",
                                    "name": validation['cleaned_name'],
                                    "type": validation['type'],
                                    "page": page_num,
                                    "description": f"Extracted from page {page_num}: {context[:200]}...",
                                    "source": "pattern",
                                    "importance": min(1.0, final_importance),
                                    "quality_score": validation['score'],
                                    "confidence": "high" if validation['score'] > 0.7 else "medium" if validation['score'] > 0.5 else "low",
                                    "context": context[:300] + "..." if len(context) > 300 else context,
                                    "extraction_method": f"pattern_{pattern_idx}",
                                    "pattern_type": self._get_pattern_type(pattern_idx)
                                })
                                found_concepts.add(validation['cleaned_name'].lower())
                                concept_id += 1
                                
                                if concept_id > 150:  # Reasonable limit
                                    break
                        except (IndexError, AttributeError):
                            continue
                    
                    if concept_id > 150:
                        break
                if concept_id > 150:
                    break
            if concept_id > 150:
                break
        
        # Post-processing and quality improvement
        concepts = self._post_process_concepts_enhanced(concepts)
        
        # Sort by combined quality and importance
        concepts.sort(key=lambda x: (x['quality_score'] * x['importance']), reverse=True)
        
        # Keep top concepts with diversity
        final_concepts = self._select_diverse_concepts(concepts, max_concepts=80)
        
        return final_concepts
    
    def _extract_relationships_enhanced(self, text: str, concepts: List[Dict], sections: List[Dict]) -> List[Dict[str, Any]]:
        """Enhanced relationship extraction with section awareness"""
        relationships = []
        concept_names = {c["name"].lower(): c["id"] for c in concepts}
        concept_pages = {c["id"]: c["page"] for c in concepts}
        
        # Use existing relationship extraction as base
        base_relationships = self._extract_relationships(text, concepts)
        relationships.extend(base_relationships)
        
        # Add proximity-based relationships with page awareness
        for i, concept1 in enumerate(concepts):
            for j, concept2 in enumerate(concepts[i+1:], i+1):
                # Skip if concepts are on very different pages
                if abs(concept1["page"] - concept2["page"]) > 3:
                    continue
                
                # Check if concepts appear together in text
                name1 = concept1["name"].lower()
                name2 = concept2["name"].lower()
                
                # Simple co-occurrence check
                text_lower = text.lower()
                pos1 = text_lower.find(name1)
                pos2 = text_lower.find(name2)
                
                if pos1 != -1 and pos2 != -1 and abs(pos1 - pos2) < 500:
                    strength = 0.4 + (0.3 * (1.0 - abs(pos1 - pos2) / 500))
                    
                    relationships.append({
                        "from": concept1["id"],
                        "to": concept2["id"],
                        "relation": "related",
                        "strength": strength,
                        "source": "proximity",
                        "context": "Concepts appear near each other"
                    })
        
        # Remove duplicates and sort
        relationships = self._deduplicate_relationships(relationships)
        relationships.sort(key=lambda x: x['strength'], reverse=True)
        
        return relationships[:100]
    
    def _get_pattern_type(self, pattern_idx: int) -> str:
        """Get the type of pattern used for extraction"""
        pattern_types = {
            0: "definition", 1: "definition", 2: "key_concept",
            3: "theorem", 4: "principle", 5: "named_theorem",
            6: "algorithm", 7: "method", 8: "method_application",
            9: "formula", 10: "mathematical",
            11: "structure", 12: "structure",
            13: "importance", 14: "importance",
            15: "learning", 16: "introduction",
            17: "emphasis", 18: "emphasis",
            19: "parenthetical", 20: "enumeration"
        }
        return pattern_types.get(pattern_idx, "general")
    
    def _post_process_concepts_enhanced(self, concepts: List[Dict]) -> List[Dict]:
        """Enhanced post-processing with better filtering"""
        processed = []
        seen_names = set()
        
        for concept in concepts:
            name = concept['name']
            name_lower = name.lower()
            
            # Skip if already seen
            if name_lower in seen_names:
                continue
            
            # Additional quality filters
            if self._passes_quality_filters(concept):
                processed.append(concept)
                seen_names.add(name_lower)
        
        return processed
    
    def _passes_quality_filters(self, concept: Dict) -> bool:
        """Check if concept passes quality filters"""
        name = concept['name']
        
        # Skip very generic terms
        generic_terms = {
            'introduction', 'overview', 'summary', 'conclusion', 'discussion',
            'background', 'motivation', 'objective', 'goal', 'purpose',
            'result', 'results', 'finding', 'findings', 'observation',
            'analysis', 'evaluation', 'assessment', 'review', 'study'
        }
        
        if name.lower() in generic_terms:
            return False
        
        # Skip very short single words unless high quality
        if len(name.split()) == 1 and len(name) < 4 and concept['quality_score'] < 0.8:
            return False
        
        # Skip very low quality
        if concept['quality_score'] < 0.25:
            return False
        
        return True
    
    def _select_diverse_concepts(self, concepts: List[Dict], max_concepts: int) -> List[Dict]:
        """Select diverse concepts to avoid over-representation of any type"""
        if len(concepts) <= max_concepts:
            return concepts
        
        # Group by type
        type_groups = {}
        for concept in concepts:
            concept_type = concept['type']
            if concept_type not in type_groups:
                type_groups[concept_type] = []
            type_groups[concept_type].append(concept)
        
        # Select concepts from each type proportionally
        selected = []
        concepts_per_type = max_concepts // max(len(type_groups), 1)
        
        for concept_type, type_concepts in type_groups.items():
            # Sort by quality within type
            type_concepts.sort(key=lambda x: x['quality_score'] * x['importance'], reverse=True)
            selected.extend(type_concepts[:concepts_per_type])
        
        # Fill remaining slots with highest quality concepts
        if len(selected) < max_concepts:
            remaining_concepts = [c for c in concepts if c not in selected]
            remaining_concepts.sort(key=lambda x: x['quality_score'] * x['importance'], reverse=True)
            selected.extend(remaining_concepts[:max_concepts - len(selected)])
        
        return selected[:max_concepts]

    def _extract_page_figures(self, page, page_num: int) -> List[Dict[str, Any]]:
        """Extract figures with better caption detection"""
        figures = []
        text = page.get_text()
        
        # Find figure captions
        figure_patterns = [
            r'Figure\s+(\d+)[:\.]?\s*([^\n]+)',
            r'Fig\.\s+(\d+)[:\.]?\s*([^\n]+)',
            r'Diagram\s+(\d+)[:\.]?\s*([^\n]+)',
            r'Chart\s+(\d+)[:\.]?\s*([^\n]+)',
            r'Graph\s+(\d+)[:\.]?\s*([^\n]+)',
            r'Table\s+(\d+)[:\.]?\s*([^\n]+)'
        ]
        
        for pattern in figure_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                figure_num = match.group(1)
                caption = match.group(2).strip()
                
                figures.append({
                    "number": figure_num,
                    "caption": caption,
                    "page": page_num + 1,
                    "type": "figure"
                })
        
        # Also detect images without captions
        images = page.get_images()
        for i, img in enumerate(images):
            if not any(f["page"] == page_num + 1 for f in figures):
                figures.append({
                    "number": str(i + 1),
                    "caption": f"Image on page {page_num + 1}",
                    "page": page_num + 1,
                    "type": "image"
                })
        
        return figures

    def _validate_concept(self, concept_name: str, context: str = "") -> Dict[str, Any]:
        """Advanced concept validation with enhanced scoring"""
        concept_clean = concept_name.strip()
        
        # Remove common prefixes/suffixes
        concept_clean = re.sub(r'^(?:The\s+|A\s+|An\s+)', '', concept_clean, flags=re.IGNORECASE)
        concept_clean = re.sub(r'\s+(?:Method|Algorithm|Approach|Technique|Theory|Model)$', '', concept_clean, flags=re.IGNORECASE)
        concept_clean = concept_clean.strip()
        
        # Basic validation
        if len(concept_clean) < self.validation_rules['min_length']:
            return {'valid': False, 'reason': 'too_short', 'score': 0.0}
        
        if len(concept_clean) > self.validation_rules['max_length']:
            return {'valid': False, 'reason': 'too_long', 'score': 0.0}
        
        # Check forbidden words (entire concept)
        if concept_clean.lower() in self.validation_rules['forbidden_words']:
            return {'valid': False, 'reason': 'forbidden_word', 'score': 0.0}
        
        # Check forbidden patterns
        for pattern in self.validation_rules['forbidden_patterns']:
            if re.search(pattern, concept_clean, re.IGNORECASE):
                return {'valid': False, 'reason': 'forbidden_pattern', 'score': 0.0}
        
        # Check required patterns
        for pattern in self.validation_rules['required_patterns']:
            if not re.search(pattern, concept_clean):
                return {'valid': False, 'reason': 'missing_required_pattern', 'score': 0.0}
        
        # Advanced filtering: check if it's mostly common words
        words = concept_clean.lower().split()
        common_word_ratio = sum(1 for word in words if word in self.validation_rules['forbidden_words']) / len(words)
        if common_word_ratio > 0.6:  # More than 60% common words
            return {'valid': False, 'reason': 'too_many_common_words', 'score': 0.0}
        
        # Calculate concept quality score
        score = self._calculate_concept_score(concept_clean, context)
        
        # Determine concept type based on content
        concept_type = self._determine_concept_type(concept_clean, context)
        
        # Enhanced threshold based on concept type
        min_threshold = 0.4 if concept_type in ['theory', 'method', 'mathematical'] else 0.3
        
        return {
            'valid': score >= min_threshold,
            'score': score,
            'type': concept_type,
            'reason': 'validated' if score >= min_threshold else 'low_quality',
            'cleaned_name': concept_clean
        }
    
    def _calculate_concept_score(self, concept: str, context: str) -> float:
        """Enhanced quality scoring for concepts"""
        score = 0.5  # Base score
        concept_lower = concept.lower()
        
        # Academic indicators boost (enhanced)
        for indicator in self.validation_rules['academic_indicators']['high_value']:
            if indicator in concept_lower:
                score += 0.4
                break
        
        for indicator in self.validation_rules['academic_indicators']['medium_value']:
            if indicator in concept_lower:
                score += 0.25
                break
        
        for indicator in self.validation_rules['academic_indicators']['domain_specific']:
            if indicator in concept_lower:
                score += 0.2
                break
        
        # Length-based scoring (refined)
        word_count = len(concept.split())
        if word_count == 1:
            # Single words can be good if they're technical terms
            if any(indicator in concept_lower for indicator in 
                   self.validation_rules['academic_indicators']['high_value'] |
                   self.validation_rules['academic_indicators']['domain_specific']):
                score += 0.1
            else:
                score -= 0.2
        elif 2 <= word_count <= 4:  # Optimal length
            score += 0.15
        elif word_count > 6:
            score -= 0.1
        
        # Capitalization patterns (enhanced)
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', concept):
            score += 0.15  # Proper title case
        elif re.match(r'^[A-Z]+(?:\s+[A-Z]+)*$', concept):
            score += 0.05  # All caps (common in technical terms)
        
        # Context relevance (enhanced)
        if context:
            context_lower = context.lower()
            concept_words = concept_lower.split()
            
            # Check if concept words appear in context
            context_matches = sum(1 for word in concept_words if word in context_lower)
            if context_matches > 0:
                score += 0.1 * (context_matches / len(concept_words))
            
            # Boost for academic context indicators
            academic_context_indicators = [
                'definition', 'theorem', 'principle', 'method', 'algorithm',
                'theory', 'model', 'concept', 'approach', 'technique'
            ]
            if any(indicator in context_lower for indicator in academic_context_indicators):
                score += 0.1
        
        # Penalize common/generic words more strictly
        common_words = {
            'thing', 'stuff', 'item', 'part', 'way', 'time', 'place', 'work',
            'system', 'process', 'method', 'approach', 'technique', 'strategy',
            'solution', 'problem', 'issue', 'aspect', 'factor', 'element'
        }
        
        concept_words = set(concept_lower.split())
        common_word_count = len(concept_words.intersection(common_words))
        if common_word_count > 0:
            score -= 0.15 * common_word_count
        
        # Boost for mathematical/scientific notation
        if re.search(r'[α-ωΑ-Ω]', concept):  # Greek letters
            score += 0.2
        if re.search(r'\b[A-Z]{2,4}\b', concept):  # Acronyms
            score += 0.1
        
        # Boost for proper nouns (names, places, etc.)
        if re.search(r'\b[A-Z][a-z]+(?:\'s)?\s+(?:Theorem|Law|Principle|Method|Algorithm)', concept):
            score += 0.3
        
        return min(1.0, max(0.0, score))
    
    def _determine_concept_type(self, concept: str, context: str) -> str:
        """Determine the type of concept based on content and context"""
        concept_lower = concept.lower()
        
        # High-level topics
        topic_indicators = ['introduction', 'overview', 'chapter', 'part', 'section']
        if any(indicator in concept_lower for indicator in topic_indicators):
            return 'topic'
        
        # Theoretical concepts
        theory_indicators = ['theorem', 'principle', 'law', 'theory', 'model']
        if any(indicator in concept_lower for indicator in theory_indicators):
            return 'theory'
        
        # Practical methods
        method_indicators = ['algorithm', 'method', 'technique', 'approach', 'procedure']
        if any(indicator in concept_lower for indicator in method_indicators):
            return 'method'
        
        # Mathematical concepts
        math_indicators = ['equation', 'formula', 'function', 'variable', 'constant']
        if any(indicator in concept_lower for indicator in math_indicators):
            return 'mathematical'
        
        # Default to concept
        return 'concept'

    def _extract_concepts(self, text: str, sections: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key concepts using enhanced pattern matching and validation"""
        concepts = []
        concept_id = 0
        found_concepts = set()
        
        # Extract from section titles (high priority concepts) with better filtering
        for section in sections:
            title = section["title"]
            
            # Skip obvious non-concepts
            if re.match(r'^(?:Chapter|Section|Part|Figure|Table|Page)\s+\d+', title, re.IGNORECASE):
                continue
            if len(title.split()) > 8:  # Too long to be a concept
                continue
                
            validation = self._validate_concept(title, section.get("content", ""))
            
            if validation['valid'] and validation['cleaned_name'].lower() not in found_concepts:
                concepts.append({
                    "id": f"concept_{concept_id}",
                    "name": validation['cleaned_name'],
                    "type": validation['type'],
                    "page": section["page"],
                    "description": section["content"][:200] + "..." if len(section["content"]) > 200 else section["content"],
                    "source": "heading",
                    "importance": min(1.0, validation['score'] + (1.0 - section["level"] * 0.15)),
                    "quality_score": validation['score'],
                    "confidence": "high"
                })
                found_concepts.add(validation['cleaned_name'].lower())
                concept_id += 1
        
        # Extract from content using enhanced patterns
        text_chunks = self._split_text_into_chunks(text, 500)  # Process in chunks for better context
        
        for chunk_idx, chunk in enumerate(text_chunks):
            for pattern_idx, pattern in enumerate(self.concept_patterns):
                matches = re.finditer(pattern, chunk, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    try:
                        concept_name = match.group(1).strip()
                        
                        # Skip if too similar to existing concepts
                        if self._is_similar_concept(concept_name, found_concepts):
                            continue
                        
                        # Get enhanced context around the match
                        start = max(0, match.start() - 150)
                        end = min(len(chunk), match.end() + 150)
                        context = chunk[start:end]
                        
                        validation = self._validate_concept(concept_name, context)
                        
                        if (validation['valid'] and 
                            validation['cleaned_name'].lower() not in found_concepts):
                            
                            # Calculate importance based on pattern type and position
                            pattern_importance = self._get_pattern_importance(pattern_idx)
                            position_importance = 1.0 - (chunk_idx * 0.1)  # Earlier chunks are more important
                            
                            concepts.append({
                                "id": f"concept_{concept_id}",
                                "name": validation['cleaned_name'],
                                "type": validation['type'],
                                "page": chunk_idx + 1,  # Approximate page
                                "description": f"Found in context: {context[:150]}...",
                                "source": "pattern",
                                "importance": validation['score'] * pattern_importance * position_importance,
                                "quality_score": validation['score'],
                                "confidence": "medium" if validation['score'] > 0.6 else "low"
                            })
                            found_concepts.add(validation['cleaned_name'].lower())
                            concept_id += 1
                            
                            if concept_id > 100:  # Reasonable limit
                                break
                    except (IndexError, AttributeError):
                        continue
                
                if concept_id > 100:
                    break
            if concept_id > 100:
                break
        
        # Post-processing: remove duplicates and low-quality concepts
        concepts = self._post_process_concepts(concepts)
        
        # Sort by quality score and importance
        concepts.sort(key=lambda x: (x['quality_score'] * x['importance']), reverse=True)
        
        # Keep only top concepts
        return concepts[:50]

    def _extract_relationships(self, text: str, concepts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract relationships between concepts with enhanced accuracy"""
        relationships = []
        concept_names = {c["name"].lower(): c["id"] for c in concepts}
        concept_positions = {}
        
        # Find positions of concepts in text for proximity analysis
        text_lower = text.lower()
        for concept_name, concept_id in concept_names.items():
            positions = []
            start = 0
            while True:
                pos = text_lower.find(concept_name, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            concept_positions[concept_id] = positions
        
        # Extract relationships using patterns
        for relation_type, patterns in self.relationship_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    try:
                        target_text = match.group(1).lower().strip()
                        
                        # Find concepts mentioned in the relationship text
                        mentioned_concepts = []
                        for concept_name, concept_id in concept_names.items():
                            if concept_name in target_text:
                                mentioned_concepts.append((concept_id, concept_name))
                        
                        if not mentioned_concepts:
                            continue
                        
                        # Find the source concept (context-based)
                        source_concept = self._find_context_concept_enhanced(
                            match.start(), text, concept_names, window_size=300
                        )
                        
                        if source_concept:
                            for target_concept, target_name in mentioned_concepts:
                                if source_concept != target_concept:
                                    # Calculate relationship strength
                                    strength = self._calculate_relationship_strength(
                                        source_concept, target_concept, relation_type,
                                        match.start(), text, concept_positions
                                    )
                                    
                                    if strength > 0.3:  # Minimum threshold
                                        relationships.append({
                                            "from": source_concept,
                                            "to": target_concept,
                                            "relation": relation_type,
                                            "strength": strength,
                                            "source": "pattern",
                                            "context": match.group(0)[:100] + "..."
                                        })
                    except (IndexError, AttributeError):
                        continue
        
        # Add proximity-based relationships
        proximity_relationships = self._extract_proximity_relationships(
            concepts, concept_positions, text
        )
        relationships.extend(proximity_relationships)
        
        # Remove duplicate relationships
        relationships = self._deduplicate_relationships(relationships)
        
        # Sort by strength and limit
        relationships.sort(key=lambda x: x['strength'], reverse=True)
        return relationships[:100]  # Limit to top 100 relationships

    def _split_text_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """Split text into overlapping chunks for better context preservation"""
        chunks = []
        words = text.split()
        
        for i in range(0, len(words), chunk_size // 2):  # 50% overlap
            chunk_words = words[i:i + chunk_size]
            chunks.append(' '.join(chunk_words))
            
            if i + chunk_size >= len(words):
                break
        
        return chunks
    
    def _is_similar_concept(self, concept: str, found_concepts: set) -> bool:
        """Check if concept is too similar to existing ones"""
        concept_lower = concept.lower()
        concept_words = set(concept_lower.split())
        
        for existing in found_concepts:
            existing_words = set(existing.split())
            
            # Check for exact substring match
            if concept_lower in existing or existing in concept_lower:
                return True
            
            # Check for high word overlap
            if len(concept_words) > 1 and len(existing_words) > 1:
                overlap = len(concept_words.intersection(existing_words))
                min_length = min(len(concept_words), len(existing_words))
                if overlap / min_length > 0.7:  # 70% word overlap
                    return True
        
        return False
    
    def _get_pattern_importance(self, pattern_idx: int) -> float:
        """Get importance weight based on pattern type"""
        # Higher importance for more specific patterns
        pattern_weights = {
            0: 0.9,   # Definitions
            1: 0.9,   # "X is defined as"
            2: 0.8,   # Key concepts
            3: 0.95,  # Theorems
            4: 0.9,   # Principles/Laws
            5: 0.85,  # Named theorems
            6: 0.8,   # Algorithms/Methods
            7: 0.75,  # Method descriptions
            8: 0.7,   # Method applications
            9: 0.8,   # Formulas/Equations
            10: 0.75, # Mathematical terms
            11: 0.6,  # Chapter/Section titles
            12: 0.5,  # Numbered sections
            13: 0.7,  # Important terms
            14: 0.6,  # Importance indicators
            15: 0.5,  # Learning objectives
            16: 0.5,  # Introductions
            17: 0.6,  # Bold text
            18: 0.6,  # Underlined text
            19: 0.4,  # Parenthetical
            20: 0.3,  # Lists
        }
        return pattern_weights.get(pattern_idx, 0.5)
    
    def _post_process_concepts(self, concepts: List[Dict]) -> List[Dict]:
        """Post-process concepts to remove duplicates and improve quality"""
        processed = []
        seen_names = set()
        
        for concept in concepts:
            name = concept['name']
            name_lower = name.lower()
            
            # Skip if we've seen this exact name
            if name_lower in seen_names:
                continue
            
            # Skip very generic concepts that slipped through
            generic_terms = {
                'introduction', 'overview', 'summary', 'conclusion', 'discussion',
                'background', 'motivation', 'objective', 'goal', 'purpose',
                'result', 'results', 'finding', 'findings', 'observation',
                'analysis', 'evaluation', 'assessment', 'review', 'study'
            }
            
            if name_lower in generic_terms:
                continue
            
            # Additional quality checks
            if len(name.split()) == 1 and len(name) < 4:  # Very short single words
                continue
            
            if concept['quality_score'] < 0.2:  # Very low quality
                continue
            
            processed.append(concept)
            seen_names.add(name_lower)
        
        return processed
    
    def _find_context_concept_enhanced(self, position: int, text: str, concept_names: Dict, window_size: int = 200) -> Optional[str]:
        """Find the most likely source concept based on enhanced context analysis"""
        # Look in the surrounding text
        start = max(0, position - window_size)
        end = min(len(text), position + window_size)
        context = text[start:end].lower()
        
        # Find all concepts in context with their distances
        concept_distances = []
        for concept_name, concept_id in concept_names.items():
            concept_pos = context.find(concept_name)
            if concept_pos != -1:
                # Calculate distance from the relationship mention
                distance = abs(concept_pos - (position - start))
                concept_distances.append((concept_id, distance, len(concept_name)))
        
        if not concept_distances:
            return None
        
        # Sort by distance (closer is better) and concept length (longer is more specific)
        concept_distances.sort(key=lambda x: (x[1], -x[2]))
        return concept_distances[0][0]
    
    def _calculate_relationship_strength(self, source_id: str, target_id: str, 
                                       relation_type: str, position: int, text: str,
                                       concept_positions: Dict) -> float:
        """Calculate the strength of a relationship based on multiple factors"""
        base_strength = 0.6
        
        # Relationship type weights
        type_weights = {
            'prerequisite': 0.9,
            'causes': 0.8,
            'contains': 0.7,
            'applies': 0.6,
            'related': 0.5
        }
        
        strength = base_strength * type_weights.get(relation_type, 0.5)
        
        # Proximity bonus: concepts mentioned close together are more likely related
        source_positions = concept_positions.get(source_id, [])
        target_positions = concept_positions.get(target_id, [])
        
        min_distance = float('inf')
        for s_pos in source_positions:
            for t_pos in target_positions:
                distance = abs(s_pos - t_pos)
                min_distance = min(min_distance, distance)
        
        if min_distance < float('inf'):
            # Closer concepts get higher strength
            if min_distance < 100:
                strength += 0.2
            elif min_distance < 300:
                strength += 0.1
        
        # Context quality bonus
        context_start = max(0, position - 100)
        context_end = min(len(text), position + 100)
        context = text[context_start:context_end].lower()
        
        # Look for academic indicators in context
        academic_indicators = [
            'definition', 'theorem', 'proof', 'example', 'application',
            'method', 'algorithm', 'principle', 'theory', 'model'
        ]
        
        if any(indicator in context for indicator in academic_indicators):
            strength += 0.1
        
        return min(1.0, strength)
    
    def _extract_proximity_relationships(self, concepts: List[Dict], 
                                       concept_positions: Dict, text: str) -> List[Dict]:
        """Extract relationships based on concept proximity in text"""
        relationships = []
        
        # Find concepts that frequently appear near each other
        for i, concept1 in enumerate(concepts):
            for j, concept2 in enumerate(concepts[i+1:], i+1):
                id1, id2 = concept1['id'], concept2['id']
                positions1 = concept_positions.get(id1, [])
                positions2 = concept_positions.get(id2, [])
                
                close_occurrences = 0
                total_occurrences = len(positions1) * len(positions2)
                
                if total_occurrences == 0:
                    continue
                
                for pos1 in positions1:
                    for pos2 in positions2:
                        if abs(pos1 - pos2) < 200:  # Within 200 characters
                            close_occurrences += 1
                
                if close_occurrences > 0:
                    proximity_strength = min(0.8, close_occurrences / max(len(positions1), len(positions2)))
                    
                    if proximity_strength > 0.3:
                        relationships.append({
                            "from": id1,
                            "to": id2,
                            "relation": "related",
                            "strength": proximity_strength,
                            "source": "proximity",
                            "context": "Concepts appear together frequently"
                        })
        
        return relationships
    
    def _deduplicate_relationships(self, relationships: List[Dict]) -> List[Dict]:
        """Remove duplicate relationships, keeping the strongest ones"""
        seen = set()
        deduplicated = []
        
        # Sort by strength first
        relationships.sort(key=lambda x: x['strength'], reverse=True)
        
        for rel in relationships:
            # Create a key that treats bidirectional relationships as the same
            key1 = (rel['from'], rel['to'], rel['relation'])
            key2 = (rel['to'], rel['from'], rel['relation'])
            
            if key1 not in seen and key2 not in seen:
                deduplicated.append(rel)
                seen.add(key1)
        
        return deduplicated
        """Find the most likely source concept based on context"""
        # Look in the surrounding text (previous 200 characters)
        start = max(0, position - 200)
        context = text[start:position].lower()
        
        for concept_name, concept_id in concept_names.items():
            if concept_name in context:
                return concept_id
        
        return None

    def _is_heading(self, text: str, font_size: float, is_bold: bool) -> bool:
        """Enhanced heading detection"""
        heading_patterns = [
            r'^Chapter\s+\d+',
            r'^\d+\.\s+[A-Z]',
            r'^[A-Z][A-Za-z\s]+$',
            r'^Introduction$',
            r'^Conclusion$',
            r'^Summary$',
            r'^Abstract$',
            r'^Definition',
            r'^Theorem\s+\d+',
            r'^Lemma\s+\d+',
            r'^Proof$',
            r'^Example\s+\d+',
            r'^Exercise\s+\d+',
            r'^Problem\s+\d+',
            r'^Solution$'
        ]
        
        # Check patterns
        for pattern in heading_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # Check formatting
        if font_size > 12 and is_bold:
            return True
            
        # Check structure (short, bold, no period)
        if (len(text) < 100 and is_bold and 
            not text.endswith('.') and 
            not text.startswith('•')):
            return True
            
        return False

    def _determine_heading_level(self, font_size: float, is_bold: bool) -> int:
        """Determine heading hierarchy level"""
        if font_size > 18:
            return 1  # Main chapter/section
        elif font_size > 16:
            return 2  # Major subsection
        elif font_size > 14:
            return 3  # Subsection
        elif font_size > 12:
            return 4  # Minor heading
        else:
            return 5  # Smallest heading

    def _get_section_content(self, page, title: str) -> str:
        """Get content following a heading"""
        text = page.get_text()
        
        # Find the title in the text
        title_pos = text.find(title)
        if title_pos == -1:
            return ""
        
        # Get text after the title
        content_start = title_pos + len(title)
        content = text[content_start:content_start + 1000]  # Limit content
        
        # Clean up the content
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    def build_concept_graph(self, concepts: List[Dict], relationships: List[Dict]) -> Dict[str, Any]:
        """Build enhanced NetworkX graph and convert to frontend format"""
        G = nx.DiGraph()
        
        # Add nodes with enhanced attributes
        for concept in concepts:
            G.add_node(concept["id"], **concept)
        
        # Add edges with validation
        valid_relationships = []
        for rel in relationships:
            if G.has_node(rel["from"]) and G.has_node(rel["to"]):
                G.add_edge(rel["from"], rel["to"], **rel)
                valid_relationships.append(rel)
        
        # Convert to enhanced frontend format
        nodes = []
        for node_id, data in G.nodes(data=True):
            # Calculate node centrality for better visualization
            try:
                centrality = nx.degree_centrality(G)[node_id] if len(G.nodes()) > 1 else 0.5
            except:
                centrality = 0.5
            
            nodes.append({
                "id": node_id,
                "name": data["name"],
                "type": data["type"],
                "page": data.get("page", 1),
                "description": data.get("description", ""),
                "importance": data.get("importance", 0.5),
                "quality_score": data.get("quality_score", 0.5),
                "confidence": data.get("confidence", "medium"),
                "source": data.get("source", "unknown"),
                "centrality": centrality,
                "degree": G.degree(node_id)
            })
        
        edges = []
        for source, target, data in G.edges(data=True):
            edges.append({
                "from": source,
                "to": target,
                "relation": data["relation"],
                "strength": data["strength"],
                "source": data.get("source", "unknown"),
                "context": data.get("context", "")
            })
        
        # Calculate enhanced graph statistics
        try:
            density = nx.density(G) if len(nodes) > 1 else 0
            avg_degree = sum(dict(G.degree()).values()) / len(nodes) if len(nodes) > 0 else 0
            
            # Convert to undirected for connectivity analysis
            G_undirected = G.to_undirected() if len(nodes) > 1 else G
            is_connected = nx.is_connected(G_undirected) if len(nodes) > 1 else True
            num_components = nx.number_connected_components(G_undirected) if len(nodes) > 0 else 0
            has_cycles = not nx.is_directed_acyclic_graph(G) if len(nodes) > 0 else False
            
            # Calculate clustering coefficient
            clustering = nx.average_clustering(G_undirected) if len(nodes) > 2 else 0
            
            # Find most important nodes
            if len(nodes) > 0:
                centrality_scores = nx.degree_centrality(G) if len(nodes) > 1 else {nodes[0]["id"]: 1.0}
                most_central = max(centrality_scores.items(), key=lambda x: x[1])
                
                # Find nodes by type
                type_counts = {}
                for node in nodes:
                    node_type = node["type"]
                    type_counts[node_type] = type_counts.get(node_type, 0) + 1
            else:
                most_central = (None, 0)
                type_counts = {}
                
        except Exception as e:
            print(f"Warning: Graph analysis error: {e}")
            density = 0
            avg_degree = 0
            is_connected = True
            num_components = 1
            has_cycles = False
            clustering = 0
            most_central = (None, 0)
            type_counts = {}
        
        # Enhanced statistics
        stats = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "density": round(density, 3),
            "avg_degree": round(avg_degree, 2),
            "clustering_coefficient": round(clustering, 3),
            "is_connected": is_connected,
            "num_components": num_components,
            "has_cycles": has_cycles,
            "most_central_node": most_central[0],
            "max_centrality": round(most_central[1], 3),
            "type_distribution": type_counts,
            "relationship_types": {
                rel_type: len([r for r in valid_relationships if r["relation"] == rel_type])
                for rel_type in set(r["relation"] for r in valid_relationships)
            } if valid_relationships else {}
        }
        
        # Add quality metrics
        if nodes:
            avg_quality = sum(n.get("quality_score", 0.5) for n in nodes) / len(nodes)
            high_quality_nodes = len([n for n in nodes if n.get("quality_score", 0.5) > 0.7])
            stats.update({
                "avg_concept_quality": round(avg_quality, 3),
                "high_quality_concepts": high_quality_nodes,
                "quality_ratio": round(high_quality_nodes / len(nodes), 3)
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": stats,
            "graph_data": {
                "is_connected": is_connected,
                "num_components": num_components,
                "has_cycles": has_cycles,
                "clustering": clustering
            }
        }

# ==================== AUTH ENDPOINTS ====================

@app.post("/auth/signup", response_model=Token)
async def signup(user_data: UserSignup):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user_doc = {
        "name": user_data.name,
        "email": user_data.email,
        "password": hashed_password,
        "subjects_uploaded": [],
        "progress_pointer": {},
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    
    # Create token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(result.inserted_id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    user = await db.users.find_one({"email": user_data.email})
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"])}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserProfile(
        id=str(current_user["_id"]),
        name=current_user["name"],
        email=current_user["email"],
        subjects_uploaded=current_user.get("subjects_uploaded", []),
        progress_pointer=current_user.get("progress_pointer", {}),
        created_at=current_user["created_at"]
    )

# ==================== UPLOAD ENDPOINT ====================

@app.post("/upload", response_model=DocumentResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Validate file type
    allowed_types = ['.pdf', '.ppt', '.pptx', '.zip']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_types):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, PowerPoint, and ZIP files are supported"
        )
    
    # Save file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{file.filename}"
    file_path = f"uploads/{filename}"
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Process file
    try:
        processor = PDFProcessor()
        
        if file.filename.lower().endswith('.pdf'):
            extracted_data = processor.extract_pdf_content(file_path)
        else:
            # For non-PDF files, create basic structure
            extracted_data = {
                "sections": [{"title": f"Content from {file.filename}", "content": "File uploaded", "page": 1, "level": 1}],
                "figures": [],
                "concepts": [],
                "relationships": [],
                "total_pages": 1
            }
        
        # Build concept graph
        graph_data = processor.build_concept_graph(
            extracted_data["concepts"], 
            extracted_data["relationships"]
        )
        
        # Store document with extracted content
        document = {
            "user_id": str(current_user["_id"]),
            "filename": file.filename,
            "stored_filename": filename,
            "file_path": file_path,
            "processed": True,
            "uploaded_at": datetime.utcnow(),
            "file_size": len(content),
            "file_type": file.filename.split('.')[-1].lower(),
            "sections_count": len(extracted_data["sections"]),
            "concepts_count": len(extracted_data["concepts"]),
            "total_pages": extracted_data["total_pages"]
        }
        
        result = await db.documents.insert_one(document)
        document_id = str(result.inserted_id)
        
        print(f"✅ Document stored in MongoDB: {document_id}")
        print(f"📄 Document data: {document}")
        
        # Verify document was stored
        stored_doc = await db.documents.find_one({"_id": result.inserted_id})
        print(f"🔍 Verified document in DB: {stored_doc is not None}")
        
        # Store extracted content (CONTRACT FOR PERSON 2)
        extracted_content = {
            "document_id": document_id,
            "sections": extracted_data["sections"],
            "figures": extracted_data["figures"],
            "page_texts": extracted_data.get("page_texts", []),  # Add page texts
            "processed_at": datetime.utcnow(),
            "extraction_metadata": {
                "total_concepts": len(extracted_data["concepts"]),
                "total_relationships": len(extracted_data["relationships"]),
                "processing_version": "1.0",
                "extraction_stats": extracted_data.get("extraction_metadata", {}).get("extraction_stats", {}),
                "document_stats": extracted_data.get("extraction_metadata", {}).get("document_stats", {})
            }
        }
        content_result = await db.extracted_content.insert_one(extracted_content)
        print(f"✅ Extracted content stored for Person 2: {len(extracted_data['sections'])} sections")
        print(f"📊 Content ID: {content_result.inserted_id}")
        
        # Verify extracted content was stored
        stored_content = await db.extracted_content.find_one({"_id": content_result.inserted_id})
        print(f"🔍 Verified extracted content in DB: {stored_content is not None}")
        
        # Store concept graph (CONTRACT FOR PERSON 3)
        concept_graph = {
            "document_id": document_id,
            "nodes": graph_data["nodes"],
            "edges": graph_data["edges"],
            "stats": graph_data["stats"],
            "graph_data": graph_data["graph_data"],
            "created_at": datetime.utcnow()
        }
        graph_result = await db.concept_graphs.insert_one(concept_graph)
        print(f"✅ Concept graph stored for Person 3: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")
        print(f"🕸️ Graph ID: {graph_result.inserted_id}")
        print(f"📈 Graph stats: {graph_data['stats']}")
        
        # Verify concept graph was stored
        stored_graph = await db.concept_graphs.find_one({"_id": graph_result.inserted_id})
        print(f"🔍 Verified concept graph in DB: {stored_graph is not None}")
        
        # Show sample nodes and edges for debugging
        if graph_data["nodes"]:
            print(f"🔗 Sample nodes: {graph_data['nodes'][:3]}")
        if graph_data["edges"]:
            print(f"🔗 Sample edges: {graph_data['edges'][:3]}")
        
        # Update user's subjects_uploaded
        subject = extracted_data["sections"][0]["title"] if extracted_data["sections"] else file.filename
        await db.users.update_one(
            {"_id": ObjectId(current_user["_id"])},
            {"$addToSet": {"subjects_uploaded": subject}}
        )
        print(f"✅ User subjects updated: {subject}")
        
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            processed=True,
            uploaded_at=document["uploaded_at"],
            sections_count=len(extracted_data["sections"]),
            concepts_count=len(extracted_data["concepts"])
        )
        
    except Exception as e:
        # Clean up file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# ==================== DOCUMENT ENDPOINTS ====================

@app.get("/documents", response_model=List[DocumentResponse])
async def get_user_documents(current_user: dict = Depends(get_current_user)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    documents = await db.documents.find(
        {"user_id": str(current_user["_id"])}
    ).sort("uploaded_at", -1).to_list(100)
    
    return [
        DocumentResponse(
            id=str(doc["_id"]),
            filename=doc["filename"],
            processed=doc.get("processed", False),
            uploaded_at=doc["uploaded_at"],
            sections_count=doc.get("sections_count", 0),
            concepts_count=doc.get("concepts_count", 0)
        )
        for doc in documents
    ]

@app.get("/graph/{document_id}")
async def get_document_graph(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Verify document belongs to user
    try:
        document = await db.documents.find_one({
            "_id": ObjectId(document_id),
            "user_id": str(current_user["_id"])
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID"
        )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get concept graph
    graph = await db.concept_graphs.find_one({"document_id": document_id})
    
    if not graph:
        return {
            "nodes": [],
            "edges": [],
            "processed": False,
            "stats": {"total_nodes": 0, "total_edges": 0, "concepts": 0, "topics": 0}
        }
    
    return {
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "processed": True,
        "stats": graph.get("stats", {})
    }

# ==================== DEBUG ENDPOINTS ====================

@app.get("/debug/collections")
async def debug_collections():
    """Debug endpoint to check MongoDB collections"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Get collection stats
        collections = await db.list_collection_names()
        
        stats = {}
        for collection_name in collections:
            collection = db[collection_name]
            count = await collection.count_documents({})
            stats[collection_name] = count
            
            # Get sample documents (convert ObjectId to string)
            if count > 0:
                sample = await collection.find().limit(1).to_list(1)
                if sample:
                    sample_doc = sample[0]
                    # Convert ObjectId to string for JSON serialization
                    if "_id" in sample_doc:
                        sample_doc["_id"] = str(sample_doc["_id"])
                    stats[f"{collection_name}_sample"] = sample_doc
        
        return {
            "database": DATABASE_NAME,
            "collections": collections,
            "stats": stats
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/graph-test/{document_id}")
async def debug_graph_test(document_id: str):
    """Test endpoint to check graph data structure"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Get concept graph
        graph = await db.concept_graphs.find_one({"document_id": document_id})
        
        if not graph:
            return {"error": "No graph found", "document_id": document_id}
        
        # Convert ObjectId to string
        graph["_id"] = str(graph["_id"])
        
        return {
            "found": True,
            "document_id": document_id,
            "nodes_count": len(graph.get("nodes", [])),
            "edges_count": len(graph.get("edges", [])),
            "sample_nodes": graph.get("nodes", [])[:3],
            "sample_edges": graph.get("edges", [])[:3],
            "stats": graph.get("stats", {}),
            "full_graph": graph
        }
    except Exception as e:
        return {"error": str(e), "document_id": document_id}
async def debug_user_data(user_id: str):
    """Debug endpoint to check specific user's data"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Get user documents
        documents = await db.documents.find({"user_id": user_id}).to_list(100)
        
        # Get extracted content for user's documents
        doc_ids = [str(doc["_id"]) for doc in documents]
        extracted_content = await db.extracted_content.find(
            {"document_id": {"$in": doc_ids}}
        ).to_list(100)
        
        # Get concept graphs for user's documents
        concept_graphs = await db.concept_graphs.find(
            {"document_id": {"$in": doc_ids}}
        ).to_list(100)
        
        return {
            "user_id": user_id,
            "documents_count": len(documents),
            "documents": documents,
            "extracted_content_count": len(extracted_content),
            "extracted_content": extracted_content,
            "concept_graphs_count": len(concept_graphs),
            "concept_graphs": concept_graphs
        }
    except Exception as e:
        return {"error": str(e)}

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow(),
        "database": "connected" if db is not None else "disconnected",
        "services": {
            "document_processing": "online",
            "pdf_extraction": "online", 
            "graph_generation": "online",
            "authentication": "online"
        }
    }

# ==================== SERVE FRONTEND ====================

app.mount("/static", StaticFiles(directory="static"), name="static")

# Note: Separate route files are disabled due to missing module dependencies
# All routes are implemented directly in this file

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
        <body>
        <h1>Frontend file not found</h1>
        <p>The static/index.html file is missing. Please check the file exists.</p>
        </body>
        </html>
        """

if __name__ == "__main__":
    print("🚀 Starting Document Intelligence Platform...")
    print("📍 Server will be available at: http://localhost:8001")
    print("📚 API documentation at: http://localhost:8001/docs")
    print("🔍 Health check at: http://localhost:8001/health")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)