import os
import json
import time
from pathlib import Path
from pdf_processor import PDFProcessor

def process_pdfs():
    """Main function to process all PDFs in input directory"""
    # Get input and output directories
    input_dir = Path("./input")
    output_dir = Path("./output")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize PDF processor
    processor = PDFProcessor()
    
    # Get all PDF files
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in input directory")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_file in pdf_files:
        print(f"Processing {pdf_file.name}...")
        start_time = time.time()
        
        try:
            # Extract outline from PDF
            result = processor.extract_outline(str(pdf_file))
            
            # Create output JSON file
            output_file = output_dir / f"{pdf_file.stem}.json"
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            processing_time = time.time() - start_time
            print(f"✓ Processed {pdf_file.name} -> {output_file.name} ({processing_time:.2f}s)")
            print(f"  Title: {result['title']}")
            print(f"  Headings found: {len(result['outline'])}")
            
        except Exception as e:
            print(f"✗ Error processing {pdf_file.name}: {str(e)}")
            
            # Create fallback output
            fallback_result = {
                "title": f"Document: {pdf_file.stem}",
                "outline": []
            }
            output_file = output_dir / f"{pdf_file.stem}.json"
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(fallback_result, f, indent=2, ensure_ascii=False)
            
            print(f"  Created fallback output for {pdf_file.name}")

if __name__ == "__main__":
    print("Starting PDF outline extraction...")
    print("=" * 50)
    
    process_pdfs()
    
    print("=" * 50)
    print("Completed PDF outline extraction")