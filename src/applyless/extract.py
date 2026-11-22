from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree


MAX_FILE_BYTES = 8_000_000
MAX_DOCX_XML_BYTES = 20_000_000
SUPPORTED_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}


class ExtractionError(ValueError):
    """A user-facing file extraction error."""


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("This text file is not UTF-8 or GB18030 encoded.")


def _extract_docx(data: bytes) -> str:
    word_namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            try:
                info = archive.getinfo("word/document.xml")
            except KeyError as exc:
                raise ExtractionError("This DOCX file does not contain a readable document.") from exc
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise ExtractionError("The DOCX document expands beyond the safe local limit.")
            document_xml = archive.read(info)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ExtractionError("This file is not a valid DOCX document.") from exc

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise ExtractionError("The DOCX document contains unreadable XML.") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{word_namespace}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{word_namespace}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{word_namespace}tab":
                parts.append("\t")
            elif node.tag in {f"{word_namespace}br", f"{word_namespace}cr"}:
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionError(
            'PDF import needs the optional local parser. Install with: pip install -e ".[pdf]"'
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("Password-protected PDFs are not supported.")
        if len(reader.pages) > 80:
            raise ExtractionError("This PDF has too many pages for a resume.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("This PDF could not be read as text.") from exc
    return "\n\n".join(pages)


def extract_resume_file(filename: str, data: bytes) -> str:
    if not data:
        raise ExtractionError("The selected file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise ExtractionError("Files must be 8 MB or smaller.")

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ExtractionError(f"Unsupported file type. Use one of: {supported}.")

    if suffix in {".txt", ".md"}:
        text = _decode_text(data)
    elif suffix == ".docx":
        text = _extract_docx(data)
    else:
        text = _extract_pdf(data)

    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()
    if len(text) < 20:
        raise ExtractionError("Not enough readable text was found in this file.")
    return text
