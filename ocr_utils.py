import io
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import streamlit as st
from PIL import Image

try:
    from google.cloud import vision
    from google.oauth2 import service_account
except Exception:  # dependency may not be installed before deploy
    vision = None
    service_account = None

from a4_pdf_utils import is_image_upload, is_pdf_upload, uploaded_file_bytes, render_pdf_bytes_to_images


@dataclass
class OcrFields:
    text: str = ""
    gr_no: str = ""
    truck_no: str = ""
    destination: str = ""
    date: str = ""


def _credentials_dict() -> dict:
    raw = st.secrets.get("gcp_service_account", None)
    if raw is None:
        raise RuntimeError("Streamlit secrets में gcp_service_account missing है।")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


@st.cache_resource(ttl=3600, show_spinner=False)
def get_vision_client():
    if vision is None or service_account is None:
        raise RuntimeError("google-cloud-vision package install नहीं है। requirements.txt update करके app reboot करें।")
    creds = service_account.Credentials.from_service_account_info(_credentials_dict())
    return vision.ImageAnnotatorClient(credentials=creds)


def _image_to_jpeg_bytes(img: Image.Image, max_side: int = 2200, quality: int = 85) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def upload_to_ocr_bytes(uploaded_file: Any) -> bytes:
    """Return bytes suitable for Google Vision OCR. For PDF, first page is rendered."""
    if is_pdf_upload(uploaded_file):
        pdf_bytes = uploaded_file_bytes(uploaded_file)
        pages = render_pdf_bytes_to_images(pdf_bytes, zoom=2.0)
        if not pages:
            return b""
        return _image_to_jpeg_bytes(pages[0])
    if is_image_upload(uploaded_file):
        img = Image.open(io.BytesIO(uploaded_file_bytes(uploaded_file)))
        return _image_to_jpeg_bytes(img)
    return b""


def run_google_vision_ocr(uploaded_file: Any) -> str:
    data = upload_to_ocr_bytes(uploaded_file)
    if not data:
        return ""
    client = get_vision_client()
    image = vision.Image(content=data)
    response = client.document_text_detection(image=image)
    if getattr(response, "error", None) and response.error.message:
        raise RuntimeError(response.error.message)
    return response.full_text_annotation.text or ""


def normalize_basic(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def normalize_number(value: Any) -> str:
    text = str(value or "").strip()
    m = re.search(r"\d+(?:\.0+)?", text)
    if not m:
        return ""
    try:
        return str(int(float(m.group(0))))
    except Exception:
        return re.sub(r"\D", "", m.group(0))


def normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    m = re.search(r"(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{2,4})", text)
    if not m:
        return ""
    d, mo, y = m.groups()
    y = ("20" + y) if len(y) == 2 else y
    return f"{int(d):02d}{int(mo):02d}{y}"


def parse_ocr_fields(text: str) -> OcrFields:
    raw = text or ""
    # OCR often breaks lines; keep both line text and flattened text.
    flat = re.sub(r"[\t\r]+", " ", raw)
    flat = re.sub(r"\s+", " ", flat)
    upper = flat.upper()

    # GR number: accept G.R.No, GR No, G R No, Bilti/LR near a number.
    gr_no = ""
    gr_patterns = [
        r"G\s*\.?\s*R\s*\.?\s*(?:NO|N0|NUMBER)?\s*[:\-]?\s*(\d{1,6})",
        r"GR\s*(?:NO|N0|NUMBER)?\s*[:\-]?\s*(\d{1,6})",
        r"(?:BILTI|BILTY|LR|L\.R\.)\s*(?:NO|N0|NUMBER)?\s*[:\-]?\s*(\d{1,6})",
    ]
    for pat in gr_patterns:
        m = re.search(pat, upper)
        if m:
            gr_no = normalize_number(m.group(1))
            break

    # Truck/vehicle number: Indian registration formats.
    truck_no = ""
    truck_patterns = [
        r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{3,4})\b",
        r"\b([A-Z]{2}\d{1,2}[A-Z]{1,3}\d{3,4})\b",
    ]
    for pat in truck_patterns:
        m = re.search(pat, upper)
        if m:
            truck_no = normalize_basic(m.group(1))
            break

    # Destination / To: prefer value after TO, up to next known field or line break.
    destination = ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for ln in lines:
        u = ln.upper()
        # common printed form: To Katlan / To: Katlan / TO KATLAN
        m = re.search(r"\bTO\b\s*[:\-]?\s*([A-Z][A-Z0-9 .\-/]{2,30})", u)
        if m:
            cand = re.split(r"\b(FROM|DATE|VEHICLE|TRUCK|WEIGHT|GST|G\.R|GR|LORRY)\b", m.group(1))[0]
            cand = re.sub(r"[^A-Z0-9 ]", " ", cand).strip()
            if cand and cand not in {"PAY", "BE", "THE"}:
                destination = cand.title()
                break
    if not destination:
        m = re.search(r"\bTO\b\s*[:\-]?\s*([A-Z][A-Z0-9 .\-/]{2,30})", upper)
        if m:
            cand = re.split(r"\b(FROM|DATE|VEHICLE|TRUCK|WEIGHT|GST|G\s*R|GR|LORRY|PARTY|CONSIGNOR)\b", m.group(1))[0]
            cand = re.sub(r"[^A-Z0-9 ]", " ", cand).strip()
            destination = cand.title()

    date = ""
    dm = re.search(r"\b(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})\b", upper)
    if dm:
        date = dm.group(1)

    return OcrFields(text=raw, gr_no=gr_no, truck_no=truck_no, destination=destination, date=date)


def _contains_match(a: str, b: str) -> bool:
    a2, b2 = normalize_basic(a), normalize_basic(b)
    if not a2 or not b2:
        return False
    return a2 in b2 or b2 in a2


def score_booking_match(fields: OcrFields, booking_row: Any, safe_cell_func) -> Dict[str, Any]:
    b_date = safe_cell_func(booking_row, 0, "")
    b_truck = safe_cell_func(booking_row, 6, "")
    b_dest = safe_cell_func(booking_row, 7, "")
    b_gr = safe_cell_func(booking_row, 8, "")
    b_trip = safe_cell_func(booking_row, 14, "")

    gr_ok = normalize_number(fields.gr_no) and normalize_number(fields.gr_no) == normalize_number(b_gr)
    truck_ok = normalize_basic(fields.truck_no) and normalize_basic(fields.truck_no) == normalize_basic(b_truck)
    dest_ok = fields.destination and _contains_match(fields.destination, b_dest)
    date_ok = normalize_date(fields.date) and normalize_date(fields.date) == normalize_date(b_date)

    score = (40 if gr_ok else 0) + (30 if truck_ok else 0) + (20 if dest_ok else 0) + (10 if date_ok else 0)
    return {
        "score": score,
        "gr_ok": bool(gr_ok),
        "truck_ok": bool(truck_ok),
        "dest_ok": bool(dest_ok),
        "date_ok": bool(date_ok),
        "trip_id": b_trip,
        "gr_no": b_gr,
        "truck_no": b_truck,
        "destination": b_dest,
        "booking_date": b_date,
    }


def best_booking_match(fields: OcrFields, bookings_df, safe_cell_func) -> Dict[str, Any]:
    best = {"score": 0, "row_index": None, "match": None, "needs_confirm": True, "status": "Manual check"}
    if bookings_df is None or bookings_df.empty:
        return best
    for idx, row in bookings_df.iterrows():
        match = score_booking_match(fields, row, safe_cell_func)
        if match["score"] > best["score"]:
            best = {"score": match["score"], "row_index": idx, "match": match, "needs_confirm": match["score"] < 90, "status": "Auto matched" if match["score"] >= 90 else "Confirm needed"}
    return best
