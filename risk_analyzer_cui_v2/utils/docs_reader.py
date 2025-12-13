import os
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import docx


ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}

class FileReadError(Exception):
    """Custom exception for file reading/processing issues."""

    def __init__(self, message: str, http_status: int = 400, errors=None):
        self.message = message
        self.http_status = http_status
        self.errors = errors or [message]
        super().__init__(message)


def process_file(file_storage) -> str:
    """
    Extract plain text from an uploaded contract file.

    Supports: .txt, .pdf, .docx
    Raises FileReadError on known issues.
    """
    filename = secure_filename(file_storage.filename or "")
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise FileReadError(
            message="Unsupported file type.",
            http_status=415,
            errors=[
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ],
        )

    try:
        text = ""

        if ext == ".txt":
            raw = file_storage.read()
            text = raw.decode("utf-8", errors="ignore")

        elif ext == ".pdf":
            reader = PdfReader(file_storage)
            pages = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                pages.append(page_text)
            text = "\n\n".join(pages)

        elif ext == ".docx":
            doc = docx.Document(file_storage)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)

        text = (text or "").strip()

        if not text:
            raise FileReadError(
                message="File parsed but no text was found.",
                http_status=422,
                errors=["Unable to extract text from the uploaded file."],
            )

        return text

    except FileReadError:
        raise
    except Exception as e:
        raise FileReadError(
            message="Exception while processing file.",
            http_status=500,
            errors=[str(e)],
        ) from e
