"""
Document loading service - handles PDF, DOCX, TXT, etc.
"""

from pathlib import Path
import fitz  # PyMuPDF
from docx import Document


def load_pdf(file_path: str) -> str:
    """Extract text from PDF"""
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text


def load_docx(file_path: str) -> str:
    """Extract text from DOCX"""
    doc = Document(file_path)
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    return text


def load_text(file_path: str) -> str:
    """Load plain text file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def load_document(file_path: str) -> tuple[str, str]:
    """
    Load document and return (content, file_type)

    Args:
        file_path: Path to the document

    Returns:
        Tuple of (text_content, file_type)
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(file_path), "pdf"
    elif suffix == ".docx":
        return load_docx(file_path), "docx"
    elif suffix in [".txt", ".md"]:
        return load_text(file_path), suffix[1:]
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
