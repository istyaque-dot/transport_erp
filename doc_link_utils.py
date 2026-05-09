"""Document link helpers for old/new GR/POD links.

Supports older Owner_Ledger entries like:
- POD Link: <url>
- POD Link 1: <url>
- POD: <url>
- raw Google Drive file id
and newer Documents sheet rows.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Dict, Any

URL_RE = re.compile(r"https?://[^\s|,;<>\)\]]+", re.IGNORECASE)
# Google Drive file IDs are usually 25+ chars; keep this conservative.
DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{25,}$")


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return text.strip().strip('"').strip("'").strip()


def normalize_drive_link(value: Any) -> str:
    """Return a clickable URL if value is a URL or a Drive file id."""
    text = clean_text(value)
    if not text:
        return ""
    # Remove common labels before the real link/id.
    text = re.sub(r"^(POD\s*Link\s*\d*|POD|GR\s*Link\s*\d*|GRD?|Drive\s*URL)\s*[:\-]\s*", "", text, flags=re.I).strip()
    # Trim punctuation that often appears after copy-pasted URLs.
    text = text.rstrip(".,;|)]")
    if text.lower().startswith(("http://", "https://")):
        return text
    if "drive.google.com" in text.lower():
        return text
    if DRIVE_ID_RE.match(text):
        return f"https://drive.google.com/file/d/{text}/view"
    return ""


def extract_links(value: Any) -> List[str]:
    """Extract one or more Drive/web links from a mixed cell value."""
    text = clean_text(value)
    if not text:
        return []

    found: List[str] = []
    for url in URL_RE.findall(text):
        link = normalize_drive_link(url)
        if link and link not in found:
            found.append(link)

    # Also support cells containing only a Drive file id or label + id.
    if not found:
        # Split common separators used in the app: |, comma, newline.
        pieces = re.split(r"[|,;\n]+", text)
        for piece in pieces:
            link = normalize_drive_link(piece)
            if link and link not in found:
                found.append(link)
    else:
        # A cell may contain URLs and raw ids separated with |.
        pieces = re.split(r"[|,;\n]+", text)
        for piece in pieces:
            link = normalize_drive_link(piece)
            if link and link not in found:
                found.append(link)

    return found


def extract_pod_links_from_owner_rows(owner_rows: Iterable[list], trip_id: str | None = None) -> List[str]:
    """Get POD links saved in old/new Owner_Ledger formats."""
    target = clean_text(trip_id)
    links: List[str] = []
    for row in list(owner_rows or [])[1:]:
        if target and (len(row) <= 1 or clean_text(row[1]) != target):
            continue
        # Old app stored link in description column E/index 4.
        cells_to_scan = []
        if len(row) > 4:
            cells_to_scan.append(row[4])
        # Defensive: scan rest of row too, but only if row appears POD-related.
        row_text = " ".join(clean_text(c) for c in row)
        if "pod" in row_text.lower():
            cells_to_scan.extend(row)
        for cell in cells_to_scan:
            if "pod" in clean_text(cell).lower() or "http" in clean_text(cell).lower() or DRIVE_ID_RE.match(clean_text(cell)):
                for link in extract_links(cell):
                    if link and link not in links:
                        links.append(link)
    return links


def header_index(headers: list, *names: str) -> int | None:
    normalized = [clean_text(h).lower() for h in headers]
    for name in names:
        n = clean_text(name).lower()
        if n in normalized:
            return normalized.index(n)
    return None


def extract_document_sheet_links(document_rows: Iterable[list], trip_id: str | None = None, doc_type_contains: str | None = None) -> List[Dict[str, str]]:
    """Return document rows from Documents sheet as dicts with clickable links."""
    rows = list(document_rows or [])
    if len(rows) <= 1:
        return []
    headers = rows[0]
    i_upload = header_index(headers, "Upload DateTime")
    i_type = header_index(headers, "Doc Type")
    i_trip = header_index(headers, "Trip ID")
    i_gr = header_index(headers, "GR No")
    i_truck = header_index(headers, "Truck No")
    i_dest = header_index(headers, "Destination")
    i_date = header_index(headers, "Booking Date")
    i_url = header_index(headers, "Drive URL")
    i_src = header_index(headers, "Source Files")
    i_remark = header_index(headers, "Remark")

    target_trip = clean_text(trip_id)
    target_type = clean_text(doc_type_contains).lower()
    out: List[Dict[str, str]] = []
    for row in rows[1:]:
        def cell(idx: int | None) -> str:
            return clean_text(row[idx]) if idx is not None and len(row) > idx else ""

        if target_trip and cell(i_trip) != target_trip:
            continue
        dtype = cell(i_type)
        if target_type and target_type not in dtype.lower():
            continue
        url_cell = cell(i_url)
        for link in extract_links(url_cell):
            out.append({
                "upload_time": cell(i_upload),
                "doc_type": dtype,
                "trip_id": cell(i_trip),
                "gr_no": cell(i_gr),
                "truck_no": cell(i_truck),
                "destination": cell(i_dest),
                "booking_date": cell(i_date),
                "url": link,
                "source_file": cell(i_src),
                "remark": cell(i_remark),
            })
    return out
