"""Security-hardened file and domain field validators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
PDF_MAGIC_BYTES = b"%PDF-"


def validate_pdf_file(uploaded_file: Any) -> None:
    """Validate that an uploaded file is a genuine PDF under 5 MB."""
    if not uploaded_file:
        return

    filename = getattr(uploaded_file, "name", "")
    extension = Path(filename).suffix.lower()
    if extension != ".pdf":
        raise ValidationError("Only PDF files (.pdf) are allowed for resume uploads.")

    file_size = getattr(uploaded_file, "size", 0)
    if file_size > MAX_RESUME_SIZE_BYTES:
        raise ValidationError("Resume file size must not exceed 5 MB.")

    # Inspect magic bytes to prevent renamed non-PDF uploads
    try:
        current_pos = uploaded_file.tell()
    except Exception:
        current_pos = None

    try:
        header = uploaded_file.read(len(PDF_MAGIC_BYTES))
    finally:
        if current_pos is not None:
            uploaded_file.seek(current_pos)
        else:
            uploaded_file.seek(0)

    if header != PDF_MAGIC_BYTES:
        raise ValidationError("Invalid PDF file header. Please upload a valid PDF document.")
