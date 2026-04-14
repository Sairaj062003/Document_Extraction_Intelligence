# AZURE DOCUMENT INTELLIGENCE EXTRACTOR
#
# Install:
#   pip install azure-ai-documentintelligence
#
# Setup — add these to backend/.env:
#   AZURE_DI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
#   AZURE_DI_KEY=your_32_char_key_here
#   AZURE_DI_MODEL=prebuilt-layout   ← optional override (default: prebuilt-layout)
#
# Find credentials:
#   Azure Portal → Your DI Resource → Keys and Endpoint (left sidebar)
#
# Verify install:
#   python -c "from azure.ai.documentintelligence import \
#              DocumentIntelligenceClient; print('Azure DI SDK OK')"
#
# Supported input: PDF only
# Free tier: 500 pages/month
# Models used:
#   prebuilt-layout → printed/digital PDFs with tables and structure
#   prebuilt-read   → handwritten docs and scanned pages (auto-fallback)
# Docs: https://learn.microsoft.com/azure/ai-services/document-intelligence

import os
import time
import asyncio

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential


def _check_credentials() -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    endpoint = os.getenv("AZURE_DI_ENDPOINT", "")
    key = os.getenv("AZURE_DI_KEY", "")
    if not endpoint or "xxxx" in endpoint or not endpoint.startswith("https://"):
        return False, "AZURE_DI_ENDPOINT not configured. Add it to backend/.env"
    if not key or "xxxx" in key or len(key) < 10:
        return False, "AZURE_DI_KEY not configured. Add it to backend/.env"
    return True, ""


def _choose_model() -> str:
    """
    Returns the Azure DI model name to use.
    Can be overridden via AZURE_DI_MODEL env var.
    Default: prebuilt-layout (best for structured printed PDFs)
    Override: prebuilt-read (best for handwriting + scanned text)
    """
    return os.getenv("AZURE_DI_MODEL", "prebuilt-layout")


def _run_azure(client: DocumentIntelligenceClient, file_bytes: bytes, model_name: str):
    """
    Blocking call — must be run inside asyncio.to_thread().
    Returns the raw Azure DI result object.
    """
    poller = client.begin_analyze_document(
        model_name,
        body=AnalyzeDocumentRequest(bytes_source=file_bytes),
    )
    return poller.result()


def _parse_result(result) -> tuple[str, int]:
    """
    Parse Azure DI result into clean text string.
    Returns (text, page_count).

    Extraction order per page:
      1. All text lines in reading order
      2. Tables formatted as proper markdown tables

    Table markdown format:
        | Col1 | Col2 | Col3 |
        |------|------|------|
        | A    | B    | C    |

    Uses cell.row_index and cell.column_index to place cells.
    Marks header rows: checks cell.kind == "columnHeader".
    If a table spans multiple pages, attaches it to the page where it starts
    using table.bounding_regions[0].page_number if available.

    Separates pages with: "\n\n--- Page {n} ---\n\n"

    Returns the combined full text string and total page count.
    """
    if not result or not result.pages:
        return "", 0

    page_count = len(result.pages)

    # ── Collect table markdown per page ──────────────────────────────
    tables_by_page: dict[int, list[str]] = {}
    if result.tables:
        for table in result.tables:
            # Determine which page this table belongs to
            table_page = 1
            if table.bounding_regions:
                table_page = table.bounding_regions[0].page_number

            # Build a 2D grid
            row_count = table.row_count
            col_count = table.column_count
            grid = [["" for _ in range(col_count)] for _ in range(row_count)]
            header_rows = set()

            for cell in table.cells:
                r, c = cell.row_index, cell.column_index
                grid[r][c] = (cell.content or "").replace("\n", " ").strip()
                if getattr(cell, "kind", None) == "columnHeader":
                    header_rows.add(r)

            # Format as markdown table
            md_lines = []
            for ri, row in enumerate(grid):
                md_lines.append("| " + " | ".join(row) + " |")
                # Add separator after header row(s) or after first row
                if ri == 0 or ri in header_rows:
                    md_lines.append("|" + "|".join(["------"] * col_count) + "|")

            tables_by_page.setdefault(table_page, []).append("\n".join(md_lines))

    # ── Build text per page ──────────────────────────────────────────
    page_texts = []
    for page in result.pages:
        pn = page.page_number
        lines = []

        # 1. Text lines in reading order
        if page.lines:
            for line in page.lines:
                lines.append(line.content)

        # 2. Tables for this page
        if pn in tables_by_page:
            lines.append("")  # blank line before tables
            for tbl_md in tables_by_page[pn]:
                lines.append(tbl_md)
                lines.append("")  # blank line after each table

        page_texts.append(f"\n\n--- Page {pn} ---\n\n" + "\n".join(lines))

    full_text = "".join(page_texts).strip()
    return full_text, page_count


async def extract(file_path: str) -> dict:
    """
    Extract text from a document using Azure Document Intelligence.
    Implements smart model fallback: prebuilt-layout → prebuilt-read
    when little text is detected (handwritten / scanned docs).
    """
    start = time.monotonic()

    # Step 1 — check credentials
    is_valid, err_msg = _check_credentials()
    if not is_valid:
        return {
            "model": "azure_di",
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": err_msg,
            "note": None,
        }

    try:
        # Step 2 — read file bytes
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Step 3 — create client
        endpoint = os.getenv("AZURE_DI_ENDPOINT")
        key = os.getenv("AZURE_DI_KEY")
        client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )

        # Step 4 — determine model + fallback strategy
        user_override = os.getenv("AZURE_DI_MODEL")
        if user_override:
            model_to_use = user_override
            do_fallback = False
        else:
            model_to_use = "prebuilt-layout"
            do_fallback = True

        # Step 5 — first attempt
        result = await asyncio.to_thread(
            _run_azure, client, file_bytes, model_to_use,
        )
        extracted_text, page_count = _parse_result(result)
        model_used = model_to_use

        # Step 6 — auto-fallback if text is suspiciously short
        if do_fallback and len(extracted_text.strip()) < 50:
            result2 = await asyncio.to_thread(
                _run_azure, client, file_bytes, "prebuilt-read",
            )
            extracted_text2, page_count2 = _parse_result(result2)

            # Only use fallback result if it actually got more text
            if len(extracted_text2.strip()) > len(extracted_text.strip()):
                extracted_text = extracted_text2
                page_count = page_count2
                model_used = "prebuilt-read (auto — handwriting/scanned detected)"
            else:
                model_used = f"{model_to_use} (prebuilt-read fallback attempted, no improvement)"

        # Step 7 — return result
        return {
            "model": "azure_di",
            "text": extracted_text if extracted_text.strip() else None,
            "pages": page_count,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": None,
            "note": f"Azure DI · {model_used}",
        }

    except Exception as e:
        return {
            "model": "azure_di",
            "text": None,
            "pages": 0,
            "processing_time_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
            "note": None,
        }
