import base64
import datetime
import io
import re
import time
from typing import List, Tuple

import pandas as pd
import requests
import streamlit as st
from PIL import Image, ImageOps
from crop_utils import get_processed_image, get_processed_pdf_bytes, render_crop_tool
from a4_pdf_utils import build_single_upload_as_a4_pdf
from doc_link_utils import extract_links, extract_pod_links_from_owner_rows, extract_document_sheet_links

from sheet_utils import (
    connect_to_sheet,
    ensure_headers,
    format_trip_label,
    invalidate_sheet_cache,
    safe_cell,
)

# Current Google Apps Script upload endpoint used in existing Booking/POD modules.
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

DOCUMENT_HEADERS = [
    "Upload DateTime", "Doc Type", "Trip ID", "GR No", "Truck No", "Destination",
    "Booking Date", "Drive URL", "Files Count", "Source Files", "Remark"
]

A4_W, A4_H = 1240, 1754  # 150 DPI A4. Smaller than 300 DPI, faster upload and enough for POD/GR view.


def _clean_file_part(value: str) -> str:
    text = str(value or "NA").strip()
    text = re.sub(r"[^A-Za-z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "NA"


def _number_keys(value: str) -> set[str]:
    """Normalize GR/truck numbers for strict exact search.

    Rules:
    - spaces / hyphen / slash / dot separators are ignored for truck numbers.
    - numeric sheet values like 45.0 are treated as 45.
    - partial numbers never match: 45 will not match 145, 450, 45A.
    """
    text = str(value or "").strip().upper()
    if not text:
        return set()

    keys = {re.sub(r"[^A-Z0-9]", "", text)}

    # Google Sheets sometimes returns numeric GR values as 45.0.
    compact = re.sub(r"[^0-9.]", "", text)
    if re.fullmatch(r"\d+(?:\.0+)?", compact or ""):
        try:
            keys.add(str(int(float(compact))))
        except Exception:
            pass

    # Also support plain numeric strings mixed with labels like GR: 45.0.
    m = re.search(r"\b(\d+)\.0+\b", text)
    if m:
        keys.add(m.group(1))

    return {k for k in keys if k}


def _number_key(value: str) -> str:
    # Backward-compatible helper: first normalized key only.
    keys = sorted(_number_keys(value), key=len, reverse=True)
    return keys[0] if keys else ""


def _exact_gr_or_truck_match(gr_no: str, truck_no: str, query: str) -> bool:
    q_keys = _number_keys(query)
    if not q_keys:
        return False
    gr_keys = _number_keys(gr_no)
    truck_keys = _number_keys(truck_no)
    return bool(q_keys & gr_keys) or bool(q_keys & truck_keys)


def _exact_token_match(value: str, query: str) -> bool:
    """Token-safe fallback for old rows where GR/truck is stored as text labels.

    Allows: GR:45, GR 45.0, truck UP18CA9128
    Blocks: 45 matching 145/450 and 9128 matching UP18CA9128.
    """
    q_keys = _number_keys(query)
    if not q_keys:
        return False
    text = str(value or "").upper()
    compact_text = re.sub(r"[^A-Z0-9]", "", text)
    for q in q_keys:
        if not q:
            continue
        # Full vehicle number style match, ignoring spaces/hyphen.
        if any(ch.isalpha() for ch in q) and compact_text == q:
            return True
        # Numeric GR token match only. This avoids 45 matching 145/450.
        if q.isdigit():
            if re.search(rf"(?<![A-Z0-9]){re.escape(q)}(?:\.0+)?(?![A-Z0-9])", text):
                return True
    return False


def _old_row_gr_truck_match(row, query: str) -> bool:
    """Match old Owner_Ledger/Document rows by GR or truck only, not date/destination/trip id.

    Some old rows may have GR/truck in dedicated columns, while some have text like
    'GR: 45' inside description. This fallback is intentionally token-safe.
    """
    if not _number_keys(query):
        return False

    gr_no = safe_cell(row, 2, "")
    truck_no = safe_cell(row, 3, "")
    if _exact_gr_or_truck_match(gr_no, truck_no, query):
        return True

    # Old/manual rows sometimes place these labels in free text.
    row_text = " ".join(str(c or "") for c in list(row or []))
    q_keys = _number_keys(query)
    for q in q_keys:
        if not q:
            continue
        if q.isdigit():
            # Search numeric query only near GR labels, not anywhere in row.
            pattern = rf"\b(?:GR|G\.?R\.?|GR\s*NO|GR\s*NUMBER|BILTY|LR)\s*[:#\-]?\s*{re.escape(q)}(?:\.0+)?\b"
            if re.search(pattern, row_text, flags=re.I):
                return True
        else:
            # Vehicle number labels / dedicated compact full-token match.
            compact = re.sub(r"[^A-Z0-9]", "", row_text.upper())
            if q in {re.sub(r"[^A-Z0-9]", "", truck_no.upper())}:
                return True
            pattern = rf"\b(?:TRUCK|VEHICLE|GAADI|GADI|गाड़ी)\s*[:#\-]?\s*{re.escape(q)}\b"
            if re.search(pattern, compact, flags=re.I):
                return True
    return False


def _booking_gr_truck_match(row, query: str) -> bool:
    # Bookings sheet expected columns: truck index 6, GR index 8.
    return _exact_gr_or_truck_match(safe_cell(row, 8, ""), safe_cell(row, 6, ""), query)


def _is_image(uploaded_file) -> bool:
    return uploaded_file.name.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".heif"))


def _is_pdf(uploaded_file) -> bool:
    return uploaded_file.name.lower().endswith(".pdf")


def image_to_a4(img: Image.Image) -> Image.Image:
    """Fit photo on white A4 canvas without stretching. EXIF rotation is respected."""
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")

    img_w, img_h = img.size
    canvas_w, canvas_h = (A4_H, A4_W) if img_w > img_h else (A4_W, A4_H)
    scale = min(canvas_w / img_w, canvas_h / img_h)
    new_w, new_h = int(img_w * scale), int(img_h * scale)

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    canvas.paste(img_resized, ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2))
    return canvas


def build_a4_pdf_from_images(image_files) -> bytes | None:
    pages = []
    for uploaded_file in image_files:
        if not _is_image(uploaded_file):
            continue
        try:
            uploaded_file.seek(0)
            img = Image.open(uploaded_file)
            pages.append(image_to_a4(img))
        except Exception:
            continue

    if not pages:
        return None

    pdf_buffer = io.BytesIO()
    if len(pages) == 1:
        pages[0].save(pdf_buffer, format="PDF", resolution=150)
    else:
        pages[0].save(
            pdf_buffer,
            format="PDF",
            resolution=150,
            save_all=True,
            append_images=pages[1:],
        )
    return pdf_buffer.getvalue()


def image_to_jpeg_bytes(uploaded_file, crop_map=None, file_index: int = 0) -> bytes | None:
    """Compress one image as one separate JPEG file. No multi-image merge."""
    try:
        img = get_processed_image(uploaded_file, crop_map, file_index)
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Limit very large phone photos to reduce Drive upload time and Apps Script payload size.
        max_side = 2200
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        return None


def upload_to_drive(file_bytes: bytes, file_name: str, mime_type: str) -> str | None:
    payload = {
        "fileName": file_name,
        "mimeType": mime_type,
        "fileData": base64.b64encode(file_bytes).decode("utf-8"),
    }
    try:
        res = requests.post(WEB_APP_URL, data=payload, timeout=90)
        result = res.text.strip()
        if not result or "Error" in result:
            return None
        return result if result.startswith("http") else f"https://drive.google.com/file/d/{result}/view"
    except Exception:
        return None


def upload_document_files(files, doc_code: str, gr_no: str, truck_no: str, trip_id: str, crop_map=None) -> Tuple[List[str], str]:
    """
    Separate-file + print-ready mode:
    - हर uploaded JPG/PNG/HEIC/PDF अलग PDF बनेगी.
    - हर PDF A4 full-page normalize होगी ताकि print में GR/POD छोटा न आए.
    - कोई multiple file merge नहीं होगी.
    Returns: (urls, source_names)
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{doc_code}_{_clean_file_part(gr_no)}_{_clean_file_part(truck_no)}_{_clean_file_part(trip_id)}_{timestamp}"
    urls: List[str] = []
    source_names = ", ".join([f.name for f in files])

    for zero_index, uploaded_file in enumerate(files):
        i = zero_index + 1
        idx = f"{i:02d}"
        original_part = _clean_file_part(uploaded_file.name.rsplit('.', 1)[0])
        try:
            if not (_is_image(uploaded_file) or _is_pdf(uploaded_file)):
                continue
            pdf_bytes = build_single_upload_as_a4_pdf(
                uploaded_file,
                crop_map=crop_map or {},
                index=zero_index,
                get_processed_image_func=get_processed_image,
                get_processed_pdf_func=get_processed_pdf_bytes,
            )
            if not pdf_bytes:
                continue
            file_name = f"{base_name}_{idx}_{original_part}.pdf"
            url = upload_to_drive(pdf_bytes, file_name, "application/pdf")
            if url:
                urls.append(url)
        except Exception:
            continue

    return urls, source_names

def get_bookings_df() -> pd.DataFrame:
    try:
        values = connect_to_sheet().worksheet("Bookings").get_all_values()
        if len(values) <= 1:
            return pd.DataFrame()
        max_cols = max(len(row) for row in values)
        rows = [row + [""] * (max_cols - len(row)) for row in values]
        return pd.DataFrame(rows[1:], columns=rows[0])
    except Exception as exc:
        st.error(f"Bookings load error: {exc}")
        return pd.DataFrame()


def find_booking_row_index(trip_id: str) -> int | None:
    try:
        ws = connect_to_sheet().worksheet("Bookings")
        ids = [str(x).strip() for x in ws.col_values(15)]
        tid = str(trip_id).strip()
        if tid in ids:
            return ids.index(tid) + 1
    except Exception:
        return None
    return None


def _join_links(urls: List[str]) -> str:
    return " | ".join([str(u).strip() for u in urls if str(u).strip()])


def save_gr_links(trip_id: str, urls: List[str], overwrite: bool = True) -> bool:
    try:
        ws = connect_to_sheet().worksheet("Bookings")
        row_index = find_booking_row_index(trip_id)
        if not row_index:
            st.error("Trip ID Bookings sheet में नहीं मिला।")
            return False

        new_links = _join_links(urls)
        if not new_links:
            st.error("GR/GRD link empty है।")
            return False

        existing = ""
        try:
            row_values = ws.row_values(row_index)
            existing = row_values[16] if len(row_values) > 16 else ""
        except Exception:
            existing = ""

        final_url = new_links if overwrite or not existing else f"{existing} | {new_links}"
        ws.update_cell(row_index, 17, final_url)
        invalidate_sheet_cache()
        return True
    except Exception as exc:
        st.error(f"GR link save error: {exc}")
        return False


def save_gr_link(trip_id: str, url: str, overwrite: bool = True) -> bool:
    # Backward compatible wrapper.
    return save_gr_links(trip_id, [url], overwrite=overwrite)


def save_pod_links(trip_id: str, gr_no: str, truck_no: str, urls: List[str]) -> bool:
    try:
        rows = []
        today = str(datetime.date.today())
        for i, url in enumerate(urls, start=1):
            if not str(url).strip():
                continue
            rows.append([today, str(trip_id), str(gr_no), str(truck_no), f"POD Link {i}: {url}", 0])
        if not rows:
            st.error("POD link empty है।")
            return False
        connect_to_sheet().worksheet("Owner_Ledger").append_rows(rows, table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as exc:
        st.error(f"POD link save error: {exc}")
        return False


def save_pod_link(trip_id: str, gr_no: str, truck_no: str, url: str) -> bool:
    # Backward compatible wrapper.
    return save_pod_links(trip_id, gr_no, truck_no, [url])


def append_documents_log(doc_type: str, trip_id: str, gr_no: str, truck_no: str, dest: str, booking_date: str,
                         urls: List[str], files_count: int, source_files: str, remark: str) -> None:
    try:
        ensure_headers("Documents", DOCUMENT_HEADERS)
        rows = []
        upload_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for url in urls:
            rows.append([
                upload_time, doc_type, trip_id, gr_no, truck_no, dest, booking_date,
                url, files_count, source_files, remark,
            ])
        if rows:
            connect_to_sheet().worksheet("Documents").append_rows(rows, table_range="A1")
            invalidate_sheet_cache()
    except Exception as exc:
        st.warning(f"Documents log save नहीं हुआ: {exc}")




@st.cache_data(ttl=300)
def get_documents_sheet_values():
    try:
        return connect_to_sheet().worksheet("Documents").get_all_values()
    except Exception:
        return []

@st.cache_data(ttl=300)
def get_owner_ledger_values_for_docs():
    try:
        return connect_to_sheet().worksheet("Owner_Ledger").get_all_values()
    except Exception:
        return []


def _doc_search_match(row, query: str, extra_text: str = "") -> bool:
    # Docs Upload search is intentionally restricted to exact GR No / exact Truck No only.
    # Destination, date, Trip ID and file name are not used for matching in this tab.
    return _booking_gr_truck_match(row, query)


def render_documents_download_search(bookings_df: pd.DataFrame):
    """Search/download panel that supports old POD links and new separate uploads."""
    st.divider()
    st.subheader("📥 Old/New POD-GR Download Search")
    st.caption("Search GR number या पूरी गाड़ी number से होगा। Destination/Date/Trip ID से search नहीं होगा। Partial number block रहेगा।")

    q = st.text_input(
        "🔍 Download search",
        placeholder="Exact GR number या exact गाड़ी number लिखें",
        key="docs_download_search",
    )
    doc_filter = st.selectbox("Document filter", ["All", "POD", "GR / GRD"], key="docs_download_filter")

    if not _number_keys(q):
        st.info("Download result देखने के लिए exact GR number या exact गाड़ी number डालें।")
        return

    booking_map = {}
    for _, bk in bookings_df.iterrows():
        tid = safe_cell(bk, 14, "")
        if tid:
            booking_map[tid] = bk

    results = []
    seen = set()

    def add_result(doc_type, trip_id, gr_no, truck_no, dest, date_val, url, source, file_name="", force_match=False):
        if not url:
            return
        # Gate: Docs search must be GR/truck based. Old rows can pass force_match only after
        # _old_row_gr_truck_match confirms a GR/truck token match.
        if not force_match and not _exact_gr_or_truck_match(gr_no, truck_no, q):
            return
        if doc_filter == "POD" and "pod" not in str(doc_type).lower():
            return
        if doc_filter == "GR / GRD" and not any(x in str(doc_type).lower() for x in ["gr", "grd"]):
            return
        key = (str(trip_id), str(doc_type), str(url))
        if key in seen:
            return
        seen.add(key)
        results.append({
            "doc_type": str(doc_type or ""),
            "trip_id": str(trip_id or ""),
            "gr_no": str(gr_no or ""),
            "truck_no": str(truck_no or ""),
            "destination": str(dest or ""),
            "booking_date": str(date_val or "")[:10],
            "url": url,
            "source": source,
            "file_name": str(file_name or ""),
        })

    # 1) New Documents sheet rows.
    doc_rows = get_documents_sheet_values()
    for item in extract_document_sheet_links(doc_rows, None, None):
        tid = item.get("trip_id", "")
        bk = booking_map.get(tid)
        extra = " ".join([item.get("source_file", ""), item.get("remark", ""), item.get("doc_type", "")])
        if bk is not None:
            if not _doc_search_match(bk, q, extra):
                continue
            gr_no = item.get("gr_no") or safe_cell(bk, 8, "")
            truck_no = item.get("truck_no") or safe_cell(bk, 6, "")
            dest = item.get("destination") or safe_cell(bk, 7, "")
            date_val = item.get("booking_date") or safe_cell(bk, 0, "")
        else:
            gr_no = item.get("gr_no", "")
            truck_no = item.get("truck_no", "")
            if not _exact_gr_or_truck_match(gr_no, truck_no, q):
                continue
            dest = item.get("destination", "")
            date_val = item.get("booking_date", "")
        add_result(item.get("doc_type", "Document"), tid, gr_no, truck_no, dest, date_val, item.get("url"), "Documents", item.get("source_file", ""))

    # 2) Old POD links from Owner_Ledger.
    owner_rows = get_owner_ledger_values_for_docs()
    for tid, bk in booking_map.items():
        if not _doc_search_match(bk, q):
            continue
        for i, link in enumerate(extract_pod_links_from_owner_rows(owner_rows, tid), start=1):
            add_result("POD", tid, safe_cell(bk, 8, ""), safe_cell(bk, 6, ""), safe_cell(bk, 7, ""), safe_cell(bk, 0, ""), link, "Owner_Ledger old POD", f"Old POD {i}")

    # 3) Direct fallback scan for old Owner_Ledger rows.
    # Useful when old POD rows do not have a matching Trip ID but have GR/truck in the row.
    for row in list(owner_rows or [])[1:]:
        if not _old_row_gr_truck_match(row, q):
            continue
        row_text = " ".join(str(c or "") for c in row)
        if "pod" not in row_text.lower() and "http" not in row_text.lower() and "drive.google.com" not in row_text.lower():
            continue
        tid = safe_cell(row, 1, "")
        bk = booking_map.get(tid)
        gr_no = safe_cell(row, 2, "") or (safe_cell(bk, 8, "") if bk is not None else "")
        truck_no = safe_cell(row, 3, "") or (safe_cell(bk, 6, "") if bk is not None else "")
        dest = safe_cell(bk, 7, "") if bk is not None else ""
        date_val = safe_cell(bk, 0, "") if bk is not None else safe_cell(row, 0, "")
        for i, link in enumerate(extract_links(row_text), start=1):
            add_result("POD", tid, gr_no, truck_no, dest, date_val, link, "Owner_Ledger old POD direct", f"Old POD {i}", force_match=True)

    # 4) Old/new GR links saved in Bookings col Q/index 16.
    for _, bk in bookings_df.iterrows():
        if not _doc_search_match(bk, q):
            continue
        tid = safe_cell(bk, 14, "")
        for i, link in enumerate(extract_links(safe_cell(bk, 16, "")), start=1):
            add_result("GR / GRD", tid, safe_cell(bk, 8, ""), safe_cell(bk, 6, ""), safe_cell(bk, 7, ""), safe_cell(bk, 0, ""), link, "Bookings GR Link", f"GR Link {i}")

    if not results:
        st.info("कोई document link नहीं मिला।")
        return

    st.caption(f"{len(results)} document link(s) found")
    for idx, item in enumerate(results[:100], start=1):
        with st.container(border=True):
            st.write(f"**{idx}. {item['doc_type']}** | GR: `{item['gr_no']}` | 🚛 `{item['truck_no']}` | 📍 `{item['destination']}` | 📅 `{item['booking_date']}` | ID: `{item['trip_id']}`")
            if item.get("file_name"):
                st.caption(f"File/Source: {item['file_name']} • {item['source']}")
            else:
                st.caption(item['source'])
            st.link_button("📥 Open / Download", item["url"], use_container_width=True)
    if len(results) > 100:
        st.caption("पहले 100 results दिखाए गए हैं; search और narrow करें।")


def show_documents_upload_page():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem !important; max-width: 98% !important; }
        .doc-card { background:#f8faff; border:1px solid #c7d4f5; border-radius:12px; padding:14px; }
        .ok-box { background:#d1e7dd; border:1px solid #0f5132; border-radius:8px; padding:8px 12px; color:#0f5132; font-weight:700; }
        .warn-box { background:#fff3cd; border:1px solid #ffc107; border-radius:8px; padding:8px 12px; color:#856404; font-weight:700; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.header("📤 POD / GR-GRD Easy Upload")
    st.caption("Google Sheets + Google Drive mode. Multiple photos/PDF अलग-अलग full-page A4 PDFs के रूप में Drive पर save होंगे।")

    df = get_bookings_df()
    if df.empty:
        st.info("Bookings sheet में data नहीं मिला।")
        return

    prefill_search = st.session_state.pop("docs_upload_prefill_search", "")
    prefill_doc_type = st.session_state.pop("docs_upload_prefill_doc_type", "")
    prefill_notice = st.session_state.pop("docs_upload_prefill_notice", "")
    if prefill_search:
        clean_prefill = str(prefill_search).strip()
        st.session_state["docs_upload_search"] = clean_prefill
        st.session_state["docs_download_search"] = clean_prefill
    if prefill_doc_type in ["GR / GRD", "POD"]:
        st.session_state["docs_upload_doc_type"] = prefill_doc_type
    if prefill_notice:
        st.info(prefill_notice)

    render_documents_download_search(df)

    st.divider()
    st.subheader("📤 New Document Upload")

    search = st.text_input(
        "🔍 Search",
        placeholder="Exact GR number या exact गाड़ी number लिखें",
        key="docs_upload_search",
    )
    st.caption("Docs Upload में GR number या पूरी गाड़ी number से search होगा। Partial number नहीं चलेगा। खाली search पर list नहीं खुलेगी।")

    if not _number_keys(search):
        st.info("Upload के लिए पहले exact GR number या exact गाड़ी number डालें।")
        return

    filtered_rows = []
    for idx, row in df.iterrows():
        if _booking_gr_truck_match(row, search):
            filtered_rows.append((format_trip_label(row), idx))

    st.caption(f"Dropdown में {len(filtered_rows)} trip(s) loaded")
    if not filtered_rows:
        st.warning("Exact GR/गाड़ी number से कोई trip नहीं मिला।")
        return

    labels = [x[0] for x in filtered_rows]
    selected_index = 1 if len(labels) == 1 else 0
    selected_label = st.selectbox(
        "📝 Trip चुनें",
        ["चुनें..."] + labels,
        index=selected_index,
        key=f"docs_upload_trip_select_{_number_key(search)}",
    )
    if selected_label == "चुनें...":
        return

    selected_idx = dict(filtered_rows)[selected_label]
    row = df.loc[selected_idx]

    booking_date = safe_cell(row, 0, "")
    truck_no = safe_cell(row, 6, "")
    dest = safe_cell(row, 7, "")
    gr_no = safe_cell(row, 8, "N/A")
    trip_id = safe_cell(row, 14, "")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("GR", gr_no or "N/A")
    c2.metric("Truck", truck_no or "N/A")
    c3.metric("Destination", dest or "N/A")
    c4.metric("Date", str(booking_date)[:10] or "N/A")
    c5.metric("Trip ID", trip_id or "N/A")

    st.markdown("<div class='doc-card'>", unsafe_allow_html=True)
    doc_type = st.radio("Document type", ["GR / GRD", "POD"], horizontal=True, key="docs_upload_doc_type")
    overwrite_gr = True
    if doc_type == "GR / GRD":
        overwrite_gr = st.checkbox("पुराना GR link replace करें", value=True)

    remark = st.text_input("Remark", placeholder="Optional remark")
    files = st.file_uploader(
        "JPG / PNG photos या PDF चुनें",
        type=["jpg", "jpeg", "png", "heic", "heif", "pdf"],
        accept_multiple_files=True,
        key=f"doc_upload_{trip_id}_{doc_type}",
    )

    docs_crop_map = {}
    if files:
        st.markdown(f"<div class='ok-box'>📎 {len(files)} file(s) selected</div>", unsafe_allow_html=True)
        with st.expander("Selected files देखें"):
            for f in files:
                st.write(f"• {f.name}")
        st.info("हर JPG/PNG/PDF अलग full-page A4 PDF बनेगी। Multiple files merge नहीं होंगी।")
        docs_crop_map = render_crop_tool(
            files,
            key_prefix=f"docs_crop_{trip_id}_{doc_type}",
            title="✂️ GR/POD Crop Tool"
        )
    else:
        st.markdown("<div class='warn-box'>पहले photos/PDF select करें।</div>", unsafe_allow_html=True)

    upload_btn = st.button("🚀 Drive पर Upload + Sheet में Link Save", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if upload_btn:
        if not files:
            st.warning("पहले file select करें।")
            return
        if not trip_id:
            st.error("Trip ID missing है।")
            return

        doc_code = "GRD" if doc_type == "GR / GRD" else "POD"
        with st.spinner("Files process होकर Google Drive पर upload हो रही हैं..."):
            urls, source_names = upload_document_files(files, doc_code, gr_no, truck_no, trip_id, crop_map=docs_crop_map)

        if not urls:
            st.error("Drive upload fail हुआ। Google Apps Script URL / Drive permission check करें।")
            return

        primary_url = urls[0]
        ok = False
        if doc_type == "GR / GRD":
            ok = save_gr_links(trip_id, urls, overwrite=overwrite_gr)
        else:
            ok = save_pod_links(trip_id, gr_no, truck_no, urls)

        append_documents_log(
            doc_type=doc_type,
            trip_id=trip_id,
            gr_no=gr_no,
            truck_no=truck_no,
            dest=dest,
            booking_date=booking_date,
            urls=urls,
            files_count=len(files),
            source_files=source_names,
            remark=remark,
        )

        if ok:
            st.success(f"✅ Upload complete. {len(urls)} separate file link(s) Google Sheet में save हो गए।")
            for i, url in enumerate(urls[:10], start=1):
                st.link_button(f"📥 Uploaded file {i} खोलें", url, type="secondary")
            if len(urls) > 10:
                st.caption(f"बाकी {len(urls) - 10} links Documents sheet में save हैं।")
            time.sleep(1.2)
            st.rerun()
        else:
            st.warning("Drive upload हो गया, लेकिन main sheet में link save नहीं हुआ। Documents log check करें।")
            for i, url in enumerate(urls[:10], start=1):
                st.link_button(f"📥 Uploaded file {i} खोलें", url, type="secondary")

