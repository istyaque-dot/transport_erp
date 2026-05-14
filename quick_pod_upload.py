import datetime
import re
import time

import pandas as pd
import streamlit as st

from a4_pdf_utils import build_a4_full_pdf_from_uploads
from crop_utils import get_processed_image, get_processed_pdf_bytes, render_crop_tool
from documents import (
    append_documents_log,
    get_bookings_df,
    get_documents_sheet_values,
    upload_to_drive,
)
from sheet_utils import connect_to_sheet, format_trip_label, invalidate_sheet_cache, safe_cell


def _clean_file_part(value: str) -> str:
    text = str(value or "NA").strip().upper()
    text = re.sub(r"[^A-Z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "NA"


def _number_keys(value: str) -> set[str]:
    text = str(value or "").strip().upper()
    if not text:
        return set()
    keys = {re.sub(r"[^A-Z0-9]", "", text)}
    compact = re.sub(r"[^0-9.]", "", text)
    if re.fullmatch(r"\d+(?:\.0+)?", compact or ""):
        try:
            keys.add(str(int(float(compact))))
        except Exception:
            pass
    m = re.search(r"\b(\d+)\.0+\b", text)
    if m:
        keys.add(m.group(1))
    return {k for k in keys if k}


def _exact_gr_match(gr_no: str, query: str) -> bool:
    q_keys = _number_keys(query)
    if not q_keys:
        return False
    return bool(q_keys & _number_keys(gr_no))


def _pod_count_for_gr(gr_no: str, truck_no: str = "") -> int:
    count = 0
    try:
        for row in get_documents_sheet_values()[1:]:
            doc_type = str(row[1] if len(row) > 1 else "").lower()
            r_gr = str(row[3] if len(row) > 3 else "")
            r_truck = str(row[4] if len(row) > 4 else "")
            if "pod" in doc_type and (_exact_gr_match(r_gr, gr_no) or (truck_no and _number_keys(r_truck) & _number_keys(truck_no))):
                count += 1
    except Exception:
        pass
    return count


def _save_latest_pod_link(trip_id: str, gr_no: str, truck_no: str, url: str, pages: int) -> bool:
    try:
        today = str(datetime.date.today())
        desc = f"POD Link: {url} | POD Pages: {pages} | Quick POD Upload"
        connect_to_sheet().worksheet("Owner_Ledger").append_row([today, str(trip_id), str(gr_no), str(truck_no), desc, 0], table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as exc:
        st.error(f"Owner_Ledger POD link save error: {exc}")
        return False


def _make_combined_pod_pdf(files, crop_map=None) -> bytes | None:
    return build_a4_full_pdf_from_uploads(
        list(files or []),
        crop_map=crop_map or {},
        get_processed_image_func=get_processed_image,
        get_processed_pdf_func=get_processed_pdf_bytes,
    )


def _trip_card(row):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("GR", safe_cell(row, 8, "N/A"))
    c2.metric("Truck", safe_cell(row, 6, "N/A"))
    c3.metric("Destination", safe_cell(row, 7, "N/A"))
    c4.metric("Date", safe_cell(row, 0, "N/A")[:10])
    c5.metric("Trip ID", safe_cell(row, 14, "N/A"))


def show_quick_pod_upload_page():
    st.header("📸 Quick POD Upload")
    st.caption("GR number डालें → POD photos/PDF select करें → एक combined A4 PDF Google Drive में save होगा।")

    st.info(
        "Photo लेते समय mobile camera में Flash ON रखें, paper पूरा frame में रखें, shadow/blur हो तो retake करें. "
        "App photo को auto-enhance करके A4 full-page PDF बनाएगा."
    )

    df = get_bookings_df()
    if df.empty:
        st.warning("Bookings sheet में data नहीं मिला।")
        return

    gr_query = st.text_input("GR Number", placeholder="जैसे: 179", key="quick_pod_gr")
    if not _number_keys(gr_query):
        st.info("POD upload के लिए exact GR number डालें।")
        return

    matches = []
    for idx, row in df.iterrows():
        if _exact_gr_match(safe_cell(row, 8, ""), gr_query):
            matches.append((format_trip_label(row), idx))

    if not matches:
        st.error("इस GR number से booking/trip नहीं मिला।")
        return

    labels = [x[0] for x in matches]
    selected_label = labels[0] if len(labels) == 1 else st.selectbox("Same GR में multiple trips हैं — सही trip चुनें", labels, key="quick_pod_trip")
    idx = dict(matches)[selected_label]
    row = df.loc[idx]

    st.subheader("Trip Confirm")
    _trip_card(row)

    gr_no = safe_cell(row, 8, "N/A")
    truck_no = safe_cell(row, 6, "")
    dest = safe_cell(row, 7, "")
    booking_date = safe_cell(row, 0, "")
    trip_id = safe_cell(row, 14, "")

    old_count = _pod_count_for_gr(gr_no, truck_no)
    if old_count:
        st.warning(f"इस GR पर पहले से {old_count} POD PDF/log saved है. नई upload latest POD PDF के रूप में save होगी; पुरानी file delete नहीं होगी।")

    st.markdown("### POD photos/PDF")
    files = st.file_uploader(
        "Camera/Gallery से POD photos या PDF चुनें",
        type=["jpg", "jpeg", "png", "heic", "heif", "pdf"],
        accept_multiple_files=True,
        key=f"quick_pod_files_{trip_id}",
    )

    crop_map = {}
    if files:
        st.success(f"{len(files)} file(s) selected. Final output = 1 combined A4 PDF.")
        with st.expander("Selected files"):
            for f in files:
                st.write(f"• {f.name}")
        with st.expander("✂️ Crop optional", expanded=False):
            crop_map = render_crop_tool(files, key_prefix=f"quick_pod_crop_{trip_id}", title="POD Crop Tool")

    disabled = not bool(files)
    if st.button("✅ Save POD PDF with this GR", type="primary", use_container_width=True, disabled=disabled):
        if not files:
            st.warning("पहले POD photo/PDF select करें।")
            return
        if not trip_id:
            st.error("Trip ID missing है।")
            return

        status = st.status("POD PDF save process start हो गया है. दुबारा click न करें.", expanded=True)
        try:
            status.write("1/4: Photos/PDF को A4 full-page pages में convert कर रहे हैं...")
            pdf_bytes = _make_combined_pod_pdf(files, crop_map=crop_map)
            if not pdf_bytes:
                status.update(label="❌ PDF बन नहीं पाई। File format/crop check करें।", state="error")
                return

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"POD_GR_{_clean_file_part(gr_no)}_{_clean_file_part(truck_no)}_{timestamp}.pdf"

            status.write("2/4: Google Drive पर single POD PDF upload हो रही है...")
            url = upload_to_drive(pdf_bytes, file_name, "application/pdf")
            if not url:
                status.update(label="❌ Drive upload fail हुआ। Apps Script URL / permission check करें।", state="error")
                return

            status.write("3/4: Owner_Ledger में latest POD link save हो रहा है...")
            ok = _save_latest_pod_link(trip_id, gr_no, truck_no, url, len(files))

            status.write("4/4: Documents sheet में POD log save हो रहा है...")
            append_documents_log(
                doc_type="POD",
                trip_id=trip_id,
                gr_no=gr_no,
                truck_no=truck_no,
                dest=dest,
                booking_date=booking_date,
                urls=[url],
                files_count=len(files),
                source_files=", ".join([f.name for f in files]),
                remark=f"Quick POD Upload combined PDF; pages={len(files)}; previous_pod_logs={old_count}",
            )

            if ok:
                status.update(label="✅ POD combined A4 PDF save हो गई।", state="complete")
                st.success(f"POD saved. GR: {gr_no} | Files/pages: {len(files)} | Single PDF link saved.")
                st.link_button("📥 POD PDF खोलें", url, type="secondary")
                time.sleep(1.0)
            else:
                status.update(label="⚠️ Drive upload हुआ, लेकिन Owner_Ledger save issue है।", state="error")
                st.link_button("📥 Uploaded POD PDF खोलें", url, type="secondary")
        except Exception as exc:
            status.update(label=f"❌ Quick POD upload error: {exc}", state="error")
