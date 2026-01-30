"""
PDF text extraction service using PyPDF2 and pdfplumber.
Extracts text content and metadata from PDF files.
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import PyPDF2
import pdfplumber
from datetime import datetime

logger = logging.getLogger(__name__)


class PDFExtractionService:
    """Service for extracting text and metadata from PDF files."""
    
    async def extract_text(self, file_path: Path) -> Tuple[str, Dict]:
        """
        Extract text content from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, metadata)
        """
        try:
            # Use pdfplumber for better text extraction
            text_content = await self._extract_with_pdfplumber(file_path)
            
            # If pdfplumber fails, fallback to PyPDF2
            if not text_content or len(text_content.strip()) < 100:
                logger.info("Falling back to PyPDF2 for text extraction")
                text_content = await self._extract_with_pypdf2(file_path)
            
            # Extract metadata
            metadata = await self._extract_metadata(file_path)
            
            logger.info(
                f"Extracted {len(text_content)} characters from PDF "
                f"with {metadata.get('pages', 0)} pages"
            )
            
            return text_content, metadata
            
        except Exception as e:
            logger.error(f"Failed to extract PDF content: {e}")
            raise
    
    async def _extract_with_pdfplumber(self, file_path: Path) -> str:
        """Extract text using pdfplumber (better quality)."""
        text_parts = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            # Add page marker
                            text_parts.append(f"\n--- Page {page_num} ---\n")
                            text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {e}")
                        continue
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            return ""
    
    async def _extract_with_pypdf2(self, file_path: Path) -> str:
        """Extract text using PyPDF2 (fallback)."""
        text_parts = []
        
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(reader.pages)):
                    try:
                        page = reader.pages[page_num]
                        text = page.extract_text()
                        if text:
                            text_parts.append(f"\n--- Page {page_num + 1} ---\n")
                            text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num + 1}: {e}")
                        continue
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            return ""
    
    async def _extract_metadata(self, file_path: Path) -> Dict:
        """Extract PDF metadata."""
        metadata = {
            "pages": 0,
            "title": None,
            "author": None,
            "subject": None,
            "creator": None,
            "producer": None,
            "creation_date": None,
        }
        
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                metadata["pages"] = len(reader.pages)
                
                # Extract document info
                if reader.metadata:
                    metadata["title"] = reader.metadata.get('/Title')
                    metadata["author"] = reader.metadata.get('/Author')
                    metadata["subject"] = reader.metadata.get('/Subject')
                    metadata["creator"] = reader.metadata.get('/Creator')
                    metadata["producer"] = reader.metadata.get('/Producer')
                    
                    # Parse creation date
                    creation_date = reader.metadata.get('/CreationDate')
                    if creation_date:
                        try:
                            # PDF date format: D:YYYYMMDDHHmmSS
                            if creation_date.startswith('D:'):
                                date_str = creation_date[2:16]  # YYYYMMDDHHmmSS
                                metadata["creation_date"] = datetime.strptime(
                                    date_str, '%Y%m%d%H%M%S'
                                ).isoformat()
                        except Exception:
                            pass
            
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")
        
        return metadata
    
    async def extract_text_by_pages(self, file_path: Path) -> List[Dict[str, any]]:
        """
        Extract text page by page with metadata.
        
        Returns:
            List of dicts with page_number, text, and metadata
        """
        pages = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            pages.append({
                                "page_number": page_num,
                                "text": text,
                                "width": page.width,
                                "height": page.height,
                            })
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {e}")
                        continue
            
            logger.info(f"Extracted {len(pages)} pages from PDF")
            return pages
            
        except Exception as e:
            logger.error(f"Failed to extract pages: {e}")
            return []


# Singleton instance
pdf_extraction_service = PDFExtractionService()
