import os
import csv
import logging
from typing import Dict, Any

logger = logging.getLogger("DocumentReaderTool")

TOOL_SPEC = {
    "name": "document_reader_tool",
    "description": "Reads and extracts plain text from attached local files (.pdf, .docx, .csv, .txt, .md).",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the document file to read."
            }
        },
        "required": ["file_path"]
    }
}

def extract_pdf_text(file_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(text).strip()
    except Exception as e:
        return f"[Error reading PDF: {e}]"

def extract_docx_text(file_path: str) -> str:
    try:
        import docx
        doc = docx.Document(file_path)
        full_text = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(full_text).strip()
    except Exception as e:
        return f"[Error reading DOCX: {e}]"

def extract_csv_text(file_path: str) -> str:
    try:
        rows = []
        with open(file_path, mode="r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(" | ".join(row))
        return "\n".join(rows).strip()
    except Exception as e:
        return f"[Error reading CSV: {e}]"

def extract_plain_text(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception as e:
        return f"[Error reading text file: {e}]"

def run(file_path: str) -> str:
    """Main execution function called by ToolRegistry."""
    if not os.path.exists(file_path):
        return f"Error: File not found at path '{file_path}'."

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        text = extract_pdf_text(file_path)
    elif ext == ".docx":
        text = extract_docx_text(file_path)
    elif ext in [".csv", ".tsv"]:
        text = extract_csv_text(file_path)
    elif ext in [".txt", ".md", ".json", ".py", ".log"]:
        text = extract_plain_text(file_path)
    else:
        return f"Unsupported file format '{ext}'."

    if not text:
        return f"Warning: No readable text extracted from {os.path.basename(file_path)}."

    # Truncate text if massive to preserve GGUF context limit
    max_char_limit = 12000
    if len(text) > max_char_limit:
        text = text[:max_char_limit] + "\n\n[...Content truncated due to context size limits...]"

    return text