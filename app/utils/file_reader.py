# app/utils/file_reader.py
# Reads a file from disk and extracts its text content.
#
# Supports: .pdf, .csv, .json, .docx, .txt
# Uses a simple if/elif block — no factories, no abstract classes.

import os
import json
import csv


def extract_text_from_file(file_path: str) -> str:

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Grab the extension in lowercase (e.g. ".pdf", ".csv")
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    # PDF
    # We use pdfplumber because it handles complex layouts (tables, multi-column text)
    if ext == ".pdf":
        import pdfplumber

        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # extract_text() returns None for blank pages
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)

        return "\n\n".join(pages_text)

    # CSV
    # Each row is turned into a comma-separated string.
    # The header row is included so the LLM knows what each column means.
    elif ext == ".csv":
        lines = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                lines.append(", ".join(row))

        return "\n".join(lines)

    # JSON
    # We flatten nested JSON into readable lines.
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Recursive flattener — turns nested dicts/lists into
        # dotted key paths with their values.
        flat_lines = []
        _flatten_json(data, prefix="", output=flat_lines)

        return "\n".join(flat_lines)

    # DOCX
    # python-docx reads .docx files.
    # We extract every paragraph's text and skip empty ones.
    elif ext == ".docx":
        from docx import Document

        doc = Document(file_path)
        paragraphs = []
        for para in doc.paragraphs:
            # Skip blank paragraphs (empty lines in the Word doc)
            if para.text.strip():
                paragraphs.append(para.text)

        return "\n\n".join(paragraphs)

    # PLAIN TEXT (.txt, .md, etc.)
    elif ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    # UNSUPPORTED FORMAT
    else:
        raise ValueError(
            f"Unsupported file type: '{ext}'. "
            f"Supported: .pdf, .csv, .json, .docx, .txt, .md"
        )


# Helper: flatten nested JSON into "dotted.key: value" lines

def _flatten_json(obj, prefix: str, output: list[str]):

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            _flatten_json(value, new_prefix, output)

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_prefix = f"{prefix}.{i}" if prefix else str(i)
            _flatten_json(item, new_prefix, output)

    else:
        # Leaf value (string, number, bool, null)
        output.append(f"{prefix}: {obj}")
