"""Security sanitization and validation for untrusted file uploads.

Governed by DATA_AND_API.md Section 4.4 and PROJECT_RULES.md (Rules 1, 7).
Enforces file-size limits, zip-bomb defense, directory traversal prevention,
XXE/Billion-Laughs XML entity rejection, and spreadsheet formula detection.
"""

import io
import re
import zipfile
from typing import Any

from opwise.domain.exceptions import DataExchangeError, SecurityError

MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB upload ceiling
MAX_UNCOMPRESSED_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB uncompressed expansion limit
MAX_ZIP_ENTRIES: int = 50
MAX_ROW_COUNT: int = 10_000

XML_ENTITY_DECLARATION_PATTERN = re.compile(rb"<!(?:DOCTYPE|ENTITY)\s", re.IGNORECASE)


def validate_file_size(content: bytes, max_bytes: int = MAX_FILE_SIZE_BYTES) -> None:
    """Enforce strict file upload size limit."""
    if len(content) == 0:
        raise DataExchangeError("Uploaded file is empty (0 bytes).", status_code=400)
    if len(content) > max_bytes:
        raise DataExchangeError(
            f"File size ({len(content)} bytes) exceeds the maximum allowed limit of {max_bytes} bytes.",
            status_code=400,
        )


def inspect_safe_zip(content: bytes, is_xlsx: bool = False) -> zipfile.ZipFile:
    """Inspect and validate a zip archive against path traversal, zip bombs, and XML entities."""
    validate_file_size(content)
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as err:
        raise DataExchangeError("Malformed or corrupt ZIP/XLSX archive.", status_code=400) from err

    entries = zf.infolist()
    if len(entries) > MAX_ZIP_ENTRIES:
        raise SecurityError(
            f"Archive contains {len(entries)} files, exceeding safety limit of {MAX_ZIP_ENTRIES}."
        )

    total_uncompressed = 0
    for info in entries:
        filename = info.filename
        # Path traversal checks
        if filename.startswith(("/", "\\")) or ".." in filename or ":" in filename:
            raise SecurityError(
                f"Potentially unsafe relative or absolute path in archive: '{filename}'."
            )
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_UNCOMPRESSED_SIZE_BYTES:
            raise SecurityError(
                f"Archive uncompressed size exceeds limit of {MAX_UNCOMPRESSED_SIZE_BYTES} bytes."
            )

        # XML entity expansion & XXE defense for Excel files
        if is_xlsx and (filename.endswith(".xml") or filename.endswith(".rels")):
            entry_bytes = zf.read(info)
            if XML_ENTITY_DECLARATION_PATTERN.search(entry_bytes):
                raise SecurityError(
                    f"Malicious XML DTD or entity declaration detected in '{filename}'."
                )

    return zf


def is_formula_cell(value: Any) -> bool:
    """Detect if a raw spreadsheet cell contains formula triggers or computed expressions."""
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        first = stripped[0]
        if first == "=":
            return True
        if first in ("@", "\t", "\r"):
            return True
        if first in ("+", "-"):
            body = stripped[1:].strip()
            # If body is a valid number (e.g. +10, -5), it is not a formula
            return not (body and body.replace(".", "", 1).isdigit())
    return False
