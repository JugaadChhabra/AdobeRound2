import PyPDF2
import pdfplumber
import re
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

class HeadingDetector:
    def __init__(self):
        # More precise patterns for heading detection
        self.heading_patterns = [
            # Numbered headings with strict patterns
            (r'^\d+\.\s+[A-Z][a-zA-Z0-9_ ]+$', 'H1'),  # 1. Introduction
            (r'^\d+\.\d+\s+[A-Z][a-zA-Z0-9_ ]+$', 'H2'),  # 1.1 Subsection
            (r'^\d+\.\d+\.\d+\s+[A-Z][a-zA-Z0-9_ ]+$', 'H3'),  # 1.1.1 Detail
            
            # Chapter/Section keywords with stricter patterns
            (r'^(Chapter|Section|Part)\s+\d+[:.]?\s+[A-Z][a-zA-Z ]+$', 'H1'),
            (r'^(Appendix|Annex)\s+[A-Z]?\d*[:.]?\s+[A-Z][a-zA-Z ]+$', 'H1'),
            
            # Strict TOC/reference patterns
            (r'^(Table of Contents|References|Bibliography|Index)$', 'H1'),
        ]
        
        # Common heading words (more restrictive)
        self.important_heading_words = {
            'introduction', 'background', 'methodology', 'results', 
            'discussion', 'conclusion', 'recommendations', 'abstract',
            'executive summary', 'literature review', 'findings',
            'limitations', 'future work'
        }
        
        # Words that indicate NOT a heading
        self.non_heading_indicators = {
            'form', 'application', 'date', 'name', 'address', 'phone', 'email',
            'signature', 'declaration', 'particulars', 'required', 'closed',
            'parents', 'guardians', 'waiver', 'page', 'continued', 'note:'
        }
        
        # Patterns that indicate TOC entries
        self.toc_patterns = [
            r'\.{3,}\s*\d+$',
            r'^\d+\s+[A-Z]',
            r'^[A-Z]\s+\d+$',
        ]
    
    def _is_toc_page(self, raw_text):
        """More accurate TOC detection"""
        if not raw_text:
            return False
            
        text = raw_text.lower()
        toc_indicators = ['contents', 'page', 'chapter', 'section']
        has_toc_title = any(indicator in text for indicator in ['table of contents', 'contents'])
        has_page_refs = sum(1 for _ in re.finditer(r'\.{3,}\s*\d+', text)) > 3
        
        return has_toc_title or has_page_refs

    def detect_headings(self, text_blocks: List[Dict], page_num: int) -> List[Dict]:
        """Detect headings with much stricter criteria"""
        headings = []
        
        if not text_blocks:
            return headings
        
        # Calculate font size statistics
        font_sizes = [block['font_size'] for block in text_blocks if block.get('font_size')]
        if not font_sizes:
            return headings
            
        avg_font_size = sum(font_sizes) / len(font_sizes)
        max_font_size = max(font_sizes)
        
        # More restrictive font size threshold
        font_size_threshold = avg_font_size * 1.5
        
        for i, block in enumerate(text_blocks):
            text = block.get('text', '').strip()
            if not text or len(text) < 4 or len(text) > 120:
                continue
                
            font_size = block.get('font_size', avg_font_size)
            is_bold = block.get('is_bold', False)
            
            # Skip if contains non-heading indicators
            if self._contains_non_heading_indicators(text):
                continue
            
            # Method 1: Strict pattern matching (highest priority)
            pattern_level = self._analyze_patterns(text)
            if pattern_level:
                headings.append({
                    'level': pattern_level,
                    'text': self._clean_heading_text(text),
                    'page': page_num,
                    'position': i
                })
                continue
                
            # Method 2: Font size and formatting analysis (only if very clear)
            if (font_size >= font_size_threshold and 
                is_bold and 
                self._looks_like_proper_heading(text)):
                level = 'H1' if font_size >= max_font_size * 0.9 else 'H2'
                headings.append({
                    'level': level,
                    'text': self._clean_heading_text(text),
                    'page': page_num,
                    'position': i
                })
                continue
                
            # Method 3: Important heading words (only for clear cases)
            if (self._contains_important_heading_word(text) and 
                not self._is_toc_entry(text) and
                font_size > avg_font_size * 1.2):
                headings.append({
                    'level': 'H2',
                    'text': self._clean_heading_text(text),
                    'page': page_num,
                    'position': i
                })
        
        return headings
    
    def _contains_non_heading_indicators(self, text: str) -> bool:
        """Strict check for non-heading indicators"""
        text_lower = text.lower()
        
        # Check for form field patterns
        if re.search(r'^\d+\.?\s*(name|date|designation|whether|amount|address)', text_lower):
            return True
            
        # Check for specific non-heading words
        for indicator in self.non_heading_indicators:
            if indicator in text_lower:
                return True
                
        # Check for email/URL patterns
        if '@' in text or 'www.' in text_lower or '.com' in text_lower:
            return True
            
        # Check for page numbers or references
        if re.search(r'^(page|pp?\.?)\s*\d+', text_lower):
            return True
            
        return False
    
    def _analyze_patterns(self, text: str) -> Optional[str]:
        """Strict pattern matching for headings"""
        for pattern, level in self.heading_patterns:
            if re.match(pattern, text):
                return level
        return None
    
    def _looks_like_proper_heading(self, text: str) -> bool:
        """Strict check for proper heading characteristics"""
        # Must be proper title case or all caps (for short headings)
        if not (text.istitle() or (text.isupper() and len(text) < 30)):
            return False
            
        # Must not contain certain punctuation patterns
        if re.search(r'[;,]', text):
            return False
            
        # Must not end with certain punctuation
        if text.endswith(('.', ':', '-', '_')):
            return False
            
        return True
    
    def _contains_important_heading_word(self, text: str) -> bool:
        """Check if text contains important heading words"""
        text_lower = text.lower()
        return any(word in text_lower for word in self.important_heading_words)
    
    def _is_toc_entry(self, text: str) -> bool:
        """Check if text looks like a TOC entry"""
        for pattern in self.toc_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _clean_heading_text(self, text: str) -> str:
        """Clean heading text while preserving important content"""
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        # Remove trailing page numbers from TOC entries
        text = re.sub(r'\s*\.{3,}\s*\d+$', '', text)
        text = re.sub(r'\s+\d+$', '', text)
        
        # Remove leading numbers/dots if they don't look like proper numbering
        if not re.match(r'^\d+\.\d', text):
            text = re.sub(r'^\d+[\s.)]*', '', text)
        
        return text.strip()


class PDFProcessor:
    def __init__(self):
        self.heading_detector = HeadingDetector()
        
    def extract_outline(self, pdf_path: str) -> Dict[str, Any]:
        """Extract structured outline from PDF with better filtering"""
        try:
            pages_data = self._extract_pages_data(pdf_path)
            title = self._extract_title(pages_data)
            headings = self._extract_headings(pages_data)
            
            # Post-process headings to remove duplicates and unimportant entries
            filtered_headings = self._filter_headings(headings)
            
            return {
                "title": title,
                "outline": filtered_headings
            }
            
        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            return {
                "title": "",
                "outline": []
            }
    
    def _extract_pages_data(self, pdf_path: str) -> List[Dict]:
        """Extract text and formatting data from all pages"""
        pages_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Skip pages with very little text
                    text = page.extract_text()
                    if not text or len(text.split()) < 20:
                        continue
                        
                    # Extract characters and group into lines
                    chars = page.chars
                    if not chars:
                        continue
                        
                    lines = self._group_chars_into_lines(chars)
                    text_blocks = self._extract_text_blocks(lines)
                    
                    pages_data.append({
                        'page_number': page_num,
                        'text_blocks': text_blocks,
                        'raw_text': text
                    })
                    
        except Exception as e:
            print(f"Error using pdfplumber: {str(e)}")
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
                    if not text:
                        continue
                        
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    text_blocks = []
                    
                    for i, line in enumerate(lines):
                        text_blocks.append({
                            'text': line,
                            'font_size': 12,  # Default
                            'is_bold': False,
                            'y_position': i
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
        sorted_chars = sorted(chars, key=lambda c: (-c['top'], c['x0']))
        
        lines = []
        current_line = []
        current_y = None
        y_tolerance = 3  # pixels
        
        for char in sorted_chars:
            if current_y is None or abs(char['top'] - current_y) <= y_tolerance:
                current_line.append(char)
                current_y = char['top']
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [char]
                current_y = char['top']
        
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
            text = self._clean_text(text)
            
            if not text:
                continue
            
            # Analyze formatting
            font_sizes = [char.get('size', 12) for char in line_chars]
            avg_font_size = sum(font_sizes) / len(font_sizes)
            
            # Check if bold (this is approximate)
            is_bold = any('bold' in char.get('fontname', '').lower() for char in line_chars)
            
            text_blocks.append({
                'text': text,
                'font_size': avg_font_size,
                'is_bold': is_bold,
                'y_position': line_chars[0]['top']
            })
        
        return text_blocks
    
    def _extract_title(self, pages_data: List[Dict]) -> str:
        """Extract document title from first meaningful text"""
        if not pages_data:
            return ""
        
        first_page = pages_data[0]
        text_blocks = first_page.get('text_blocks', [])
        
        # Look for the largest, boldest text that isn't obviously a header/footer
        candidates = []
        for block in text_blocks[:10]:  # Only check first few blocks
            text = block['text'].strip()
            if (len(text) > 5 and 
                not self._looks_like_header_footer(text) and
                not self._looks_like_form_content(text)):
                candidates.append((block['font_size'], block['is_bold'], text))
        
        if candidates:
            # Sort by font size (desc), then bold status, then text length
            candidates.sort(key=lambda x: (-x[0], -x[1], -len(x[2])))
            return candidates[0][2]
        
        return ""
    
    def _looks_like_header_footer(self, text: str) -> bool:
        """Check if text looks like a header or footer"""
        text_lower = text.lower()
        header_footer_indicators = [
            'page', 'confidential', 'copyright', '©', 
            'proprietary', 'draft', 'version', 'date:'
        ]
        return any(indicator in text_lower for indicator in header_footer_indicators)
    
    def _looks_like_form_content(self, text: str) -> bool:
        """Check if text looks like form content"""
        form_indicators = [
            r'^\d+\.?\s*(name|date|designation|whether|amount|address)',
            'rsvp:', 'signature', 'form', 'application', 'required'
        ]
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in form_indicators)
    
    def _extract_headings(self, pages_data: List[Dict]) -> List[Dict]:
        """Extract headings with deduplication and filtering"""
        all_headings = []
        seen_text = set()
        
        for page_data in pages_data:
            page_num = page_data['page_number']
            text_blocks = page_data.get('text_blocks', [])
            raw_text = page_data.get('raw_text', '')
            
            # Skip pages that are mostly TOC or references
            if self._is_junk_page(raw_text):
                continue
                
            headings = self.heading_detector.detect_headings(text_blocks, page_num)
            
            for heading in headings:
                clean_text = heading['text']
                if (clean_text and 
                    len(clean_text.split()) >= 2 and
                    clean_text.lower() not in seen_text):
                    
                    all_headings.append(heading)
                    seen_text.add(clean_text.lower())
        
        return all_headings
    
    def _is_junk_page(self, text: str) -> bool:
        """Check if page is TOC, references, or other non-content"""
        if not text:
            return True
            
        text_lower = text.lower()
        junk_indicators = [
            'table of contents', 'contents', 'references', 'bibliography',
            'index', 'acknowledgements', 'revision history'
        ]
        
        # Page is mostly junk if it contains many junk indicators
        matches = sum(1 for indicator in junk_indicators if indicator in text_lower)
        return matches >= 2
    
    def _filter_headings(self, headings: List[Dict]) -> List[Dict]:
        """Filter headings to keep only the most important ones"""
        if not headings:
            return []
        
        # Remove duplicate headings at different levels
        unique_headings = []
        seen_text = set()
        
        for heading in headings:
            clean_text = self._normalize_heading_text(heading['text'])
            if clean_text not in seen_text:
                unique_headings.append(heading)
                seen_text.add(clean_text)
        
        # Remove headings that are too short or generic
        filtered = []
        for heading in unique_headings:
            text = heading['text']
            words = text.split()
            
            # Skip if too short or too generic
            if (len(words) < 2 or 
                len(text) < 5 or
                text.lower() in {'overview', 'introduction', 'conclusion'}):
                continue
                
            filtered.append(heading)
        
        # Ensure logical hierarchy (H1 should not follow H2 without another H1)
        final_headings = []
        current_h1 = None
        
        for heading in filtered:
            if heading['level'] == 'H1':
                current_h1 = heading['text']
                final_headings.append(heading)
            elif current_h1:  # Only include H2/H3 if we have a parent H1
                final_headings.append(heading)
        
        return final_headings
    
    def _normalize_heading_text(self, text: str) -> str:
        """Normalize heading text for comparison"""
        return re.sub(r'[^a-zA-Z0-9]', '', text.lower())
    
    def _clean_text(self, text: str) -> str:
        """Clean text while preserving important content"""
        if not text:
            return ""
        
        # Normalize whitespace and remove some special chars
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\-.,;:()\u2019]', '', text)
        return text.strip()


# Example usage:
# processor = PDFProcessor()
# outline = processor.extract_outline("your_file.pdf")
# print(json.dumps(outline, indent=2))