import PyPDF2
import pdfplumber
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from heading_detector import HeadingDetector
from collections import defaultdict
from statistics import quantiles
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PDFProcessor:
    def __init__(self, config: Optional[Dict] = None):
        """Initialize with optional configuration for flexibility."""
        self.heading_detector = HeadingDetector()
        self.config = config or {}
        self.y_tolerance = self.config.get('y_tolerance', 3)
        self.font_size_percentile = self.config.get('font_size_percentile', 75)  # 75th percentile by default

    def extract_outline(self, pdf_path: str) -> Dict[str, Any]:
        """Extract structured outline from PDF with enhanced processing."""
        try:
            pages_data = self._extract_pages_data(pdf_path)
            title = self._extract_title(pages_data)
            headings = self._extract_headings(pages_data)
            
            return {
                "title": title,
                "outline": headings
            }
        except Exception as e:
            logging.error(f"Error processing PDF: {str(e)}")
            return {"title": "", "outline": []}

    def _extract_pages_data(self, pdf_path: str) -> List[Dict]:
        """Extract text and formatting data from all pages with improved filtering."""
        pages_data = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if len(text.split()) < 20:  # Skip pages with little content
                        logging.debug(f"Skipping page {page_num}: insufficient text")
                        continue
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
            logging.warning(f"pdfplumber failed on {pdf_path}: {str(e)}. Falling back to PyPDF2.")
            return self._extract_pages_data_fallback(pdf_path)
        return pages_data

    def _extract_pages_data_fallback(self, pdf_path: str) -> List[Dict]:
        """Fallback extraction using PyPDF2 with basic formatting estimation."""
        pages_data = []
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text() or ""
                    if not text:
                        continue
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    text_blocks = [{'text': line, 'font_size': 12, 'is_bold': False, 'y_position': i} 
                                  for i, line in enumerate(lines)]
                    pages_data.append({
                        'page_number': page_num,
                        'text_blocks': text_blocks,
                        'raw_text': text
                    })
        except Exception as e:
            logging.error(f"Fallback extraction failed: {str(e)}")
        return pages_data

    def _group_chars_into_lines(self, chars: List[Dict]) -> List[List[Dict]]:
        """Group characters into lines with multi-column support."""
        if not chars:
            return []
        
        # Sort by y-position then x-position
        sorted_chars = sorted(chars, key=lambda c: (-c['y0'], c['x0']))
        
        lines = defaultdict(list)
        for char in sorted_chars:
            y_pos = char['y0']
            x_pos = char['x0']
            # Find closest line based on y-position and x-column clustering
            line_key = min(lines.keys(), key=lambda k: abs(k[0] - y_pos) if abs(k[0] - y_pos) <= self.y_tolerance else float('inf'), default=None)
            if line_key is None or abs(line_key[0] - y_pos) > self.y_tolerance:
                lines[(y_pos, x_pos // 100)] = [char]  # Group by approximate column (100px width)
            else:
                lines[line_key].append(char)
        
        return [line for line in lines.values() if line]

    def _extract_text_blocks(self, lines: List[List[Dict]]) -> List[Dict]:
        """Extract text blocks with improved bold detection."""
        text_blocks = []
        for line_chars in lines:
            if not line_chars:
                continue
            text = ''.join(char['text'] for char in line_chars).strip()
            if not text:
                continue
            font_sizes = [char.get('size', 12) for char in line_chars]
            avg_font_size = sum(font_sizes) / len(font_sizes)
            is_bold = any('bold' in char.get('fontname', '').lower() or char.get('weight', 400) > 400 for char in line_chars)
            y_position = line_chars[0]['y0']
            text_blocks.append({
                'text': text,
                'font_size': avg_font_size,
                'is_bold': is_bold,
                'y_position': y_position
            })
        return text_blocks

    def _extract_title(self, pages_data: List[Dict]) -> str:
        """Extract title with enhanced heuristics."""
        if not pages_data:
            return "Untitled Document"
        
        first_page = pages_data[0]
        text_blocks = first_page['text_blocks'][:5]  # Check first 5 blocks
        if not text_blocks:
            return "Untitled Document"
        
        # Use font size distribution
        font_sizes = [block['font_size'] for block in text_blocks]
        size_threshold = quantiles(font_sizes, n=100)[self.font_size_percentile - 1]  # 75th percentile
        
        candidates = []
        for block in text_blocks:
            text = block['text']
            if (len(text) > 5 and block['font_size'] >= size_threshold and 
                not re.search(r'page\s*\d+|confidential|copyright', text.lower())):
                candidates.append((block['font_size'], block['is_bold'], text))
        
        if candidates:
            candidates.sort(key=lambda x: (-x[0], -x[1], -len(x[2])))
            return candidates[0][2]
        
        return first_page['raw_text'].split('\n')[0].strip() or "Untitled Document"

    def _extract_headings(self, pages_data: List[Dict]) -> List[Dict]:
        """Extract headings with TOC filtering and deduplication."""
        all_headings = []
        for page_data in pages_data:
            if self.heading_detector._is_toc_page(page_data['raw_text']):
                logging.debug(f"Skipping TOC page {page_data['page_number']}")
                continue
            headings = self.heading_detector.detect_headings(page_data['text_blocks'], page_data['page_number'])
            all_headings.extend([h for h in headings if len(h['text'].split()) > 1 and not h['text'].isdigit()])
        
        # Deduplicate and sort
        unique_headings = []
        seen = set()
        for heading in sorted(all_headings, key=lambda x: (x['page'], x.get('position', 0))):
            key = (heading['text'], heading['page'])
            if key not in seen:
                seen.add(key)
                unique_headings.append(heading)
        
        return unique_headings

# Example usage
if __name__ == "__main__":
    config = {'y_tolerance': 4, 'font_size_percentile': 80}
    processor = PDFProcessor(config)
    outline = processor.extract_outline("example.pdf")
    import json
    print(json.dumps(outline, indent=2))