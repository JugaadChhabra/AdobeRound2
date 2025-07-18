import re
from typing import Optional

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters that might interfere
    text = re.sub(r'[^\w\s\-.,;:()!?"]', '', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text

def extract_title_from_text(text: str) -> Optional[str]:
    """Extract potential title from text"""
    if not text:
        return None
    
    lines = text.split('\n')
    for line in lines:
        cleaned = clean_text(line)
        if cleaned and len(cleaned) > 5 and len(cleaned) < 200:
            return cleaned
    
    return None

def is_heading_like(text: str) -> bool:
    """Check if text looks like a heading"""
    if not text or len(text) < 3:
        return False
    
    # Too long to be a heading
    if len(text) > 150:
        return False
    
    # Check for heading patterns
    heading_patterns = [
        r'^\d+\.?\s+[A-Z]',  # Numbered
        r'^[A-Z\s]{4,}$',    # All caps
        r'^(Chapter|Section|Part)\s',  # Keywords
    ]
    
    for pattern in heading_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False