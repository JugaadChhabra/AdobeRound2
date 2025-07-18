import PyPDF2
import pdfplumber
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from heading_detector import HeadingDetector
from utils import clean_text, extract_title_from_text

class PDFProcessor:
    def __init__(self):
        self.heading_detector = HeadingDetector()
        
    def extract_outline(self, pdf_path: str) -> Dict[str, Any]:
        """Extract structured outline from PDF"""
        try:
            # Extract text and formatting info
            pages_data = self._extract_pages_data(pdf_path)
            
            # Extract title
            title = self._extract_title(pages_data)
            
            # Extract headings
            headings = self._extract_headings(pages_data)
            
            return {
                "title": title,
                "outline": headings
            }
            
        except Exception as e:
            print(f"Error in extract_outline: {str(e)}")
            raise
    
    def _extract_pages_data(self, pdf_path: str) -> List[Dict]:
        """Extract text and formatting data from all pages"""
        pages_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text with character-level details
                    chars = page.chars
                    
                    # Group characters into lines
                    lines = self._group_chars_into_lines(chars)
                    
                    # Extract text blocks with formatting
                    text_blocks = self._extract_text_blocks(lines)
                    
                    pages_data.append({
                        'page_number': page_num,
                        'text_blocks': text_blocks,
                        'raw_text': page.extract_text() or ""
                    })
                    
        except Exception as e:
            print(f"Error extracting pages data: {str(e)}")
            # Fallback to PyPDF2
            return self._extract_pages_data_fallback(pdf_path)
            
        return pages_data
    
    def _extract_pages_data_fallback(self, pdf_path: str) -> List[Dict]:
        """Fallback extraction using PyPDF2"""
        pages_data = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    
                    # Simple line splitting
                    lines = text.split('\n')
                    text_blocks = []
                    
                    for line in lines:
                        if line.strip():
                            text_blocks.append({
                                'text': line.strip(),
                                'font_size': 12,  # Default
                                'is_bold': False,
                                'y_position': 0
                            })
                    
                    pages_data.append({
                        'page_number': page_num,
                        'text_blocks': text_blocks,
                        'raw_text': text
                    })
                    
        except Exception as e:
            print(f"Fallback extraction failed: {str(e)}")
            
        return pages_data
    
    def _group_chars_into_lines(self, chars: List[Dict]) -> List[List[Dict]]:
        """Group characters into lines based on y-position"""
        if not chars:
            return []
        
        # Sort by y-position (top to bottom) then x-position (left to right)
        sorted_chars = sorted(chars, key=lambda c: (-c['y0'], c['x0']))
        
        lines = []
        current_line = []
        current_y = None
        y_tolerance = 2  # pixels
        
        for char in sorted_chars:
            if current_y is None or abs(char['y0'] - current_y) <= y_tolerance:
                current_line.append(char)
                current_y = char['y0']
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [char]
                current_y = char['y0']
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _extract_text_blocks(self, lines: List[List[Dict]]) -> List[Dict]:
        """Extract text blocks with formatting information"""
        text_blocks = []
        
        for line_chars in lines:
            if not line_chars:
                continue
                
            # Combine characters into text
            text = ''.join(char['text'] for char in line_chars)
            text = clean_text(text)
            
            if not text:
                continue
            
            # Analyze formatting
            font_sizes = [char.get('size', 12) for char in line_chars]
            avg_font_size = sum(font_sizes) / len(font_sizes)
            
            # Check if bold (this is approximate)
            is_bold = any(char.get('fontname', '').lower().find('bold') != -1 
                         for char in line_chars)
            
            # Y position for ordering
            y_position = line_chars[0]['y0']
            
            text_blocks.append({
                'text': text,
                'font_size': avg_font_size,
                'is_bold': is_bold,
                'y_position': y_position
            })
        
        return text_blocks
    
    def _extract_title(self, pages_data: List[Dict]) -> str:
        """Extract document title"""
        if not pages_data:
            return "Untitled Document"
        
        # Look for title in first page
        first_page = pages_data[0]
        
        # Method 1: Look for largest font size in first few blocks
        text_blocks = first_page['text_blocks'][:10]  # First 10 blocks
        
        if text_blocks:
            # Find block with largest font size
            max_font_size = max(block['font_size'] for block in text_blocks)
            title_candidates = [block for block in text_blocks 
                              if block['font_size'] == max_font_size]
            
            if title_candidates:
                title = title_candidates[0]['text']
                return clean_text(title)
        
        # Method 2: Use first non-empty line
        raw_text = first_page['raw_text']
        if raw_text:
            lines = raw_text.split('\n')
            for line in lines:
                cleaned = clean_text(line)
                if cleaned and len(cleaned) > 5:  # Reasonable title length
                    return cleaned
        
        return "Untitled Document"
    
    def _extract_headings(self, pages_data: List[Dict]) -> List[Dict]:
        """Extract headings from all pages"""
        all_headings = []
        
        for page_data in pages_data:
            page_num = page_data['page_number']
            text_blocks = page_data['text_blocks']
            
            # Detect headings using multiple methods
            headings = self.heading_detector.detect_headings(text_blocks, page_num)
            all_headings.extend(headings)
        
        # Remove duplicates and sort
        seen = set()
        unique_headings = []
        for heading in all_headings:
            key = (heading['text'], heading['page'])
            if key not in seen:
                seen.add(key)
                unique_headings.append(heading)
        
        # Sort by page number and position
        unique_headings.sort(key=lambda x: (x['page'], x.get('position', 0)))
        
        return unique_headings