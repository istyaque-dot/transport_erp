import datetime
import re
import time
from typing import Any, Dict, List

import streamlit as st

from a4_pdf_utils import build_a4_full_pdf_from_uploads, build_single_upload_as_a4_pdf
from crop_utils import get_processed_image, get_processed_pdf_bytes
from documents import append_documents_log, get_bookings_df, save_gr_links, upload_to_drive
from ocr_utils import best_booking_match, parse_ocr_fields, run_google_vision_ocr
from sheet_utils import connect_to_sheet, format_trip_label, invalidate_sheet_cache, safe_cell


def _clean_file_part(value: str) -> str:
    text = str(value or "NA").strip().upper()
    text = re.sub(r"[^A-Z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "NA"


def _save_latest_pod_link(trip_id: str, gr_no: str, truck_no: str, url: str, pages: int) -> bool:
    try:
        today = str(datetime.date.today())
        desc = f"POD Link: {url} | POD Pages: {pages} | Bulk OCR POD Upload"
        connect_to_sheet().worksheet("Owner_Ledger").append_row([today, str(trip_id), str(gr_no), str(truck_no), desc, 0], table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as exc:
        st.error(f"Owner_Ledger POD link save error: {exc}")
        return False


def _trip_label_from_match(match: Dict[str, Any]) -> str:
    m = match or {}
    return f"GR: {m.get('gr_no','')} | 🚛 {m.get('truck_no','')} | 📍 {m.get('destination','')} | 📅 {str(m.get('booking_date',''))[:10]} | ID: {m.get('trip_id','')}"


def _all_trip_options(df) -> List[tuple[str, int]]:
    opts = []
    for idx, row in df.iterrows():
        opts.append((format_trip_label(row), idx))
    return opts


def _run_ocr_for_files(files, bookings_df):
    results = []
    progress = st.progress(0)
    for i, f in enumerate(files):
        try:
            text = run_google_vision_ocr(f)
            fields = parse_ocr_fields(text)
            best = best_booking_match(fields, bookings_df, safe_cell)
            results.append({
                "file_index": i,
                "file_name": getattr(f, "name", f"file_{i+1}"),
                "ocr_text": text,
                "fields": fields,
                "best": best,
                "selected_row_index": best.get("row_index"),
            })
        except Exception as exc:
            results.append({
                "file_index": i,
                "file_name": getattr(f, "name", f"file_{i+1}"),
                "ocr_text": "",
                "fields": parse_ocr_fields(""),
                "best": {"score": 0, "row_index": None, "match": None, "needs_confirm": True, "status": f"OCR error: {exc}"},
                "selected_row_index": None,
            })
        progress.progress((i + 1) / max(len(files), 1))
    progress.empty()
    return results


def _render_match_review(results, bookings_df):
    trip_options = _all_trip_options(bookings_df)
    label_to_idx = {label: idx for label, idx in trip_options}
    idx_to_label = {idx: label for label, idx in trip_options}

    final_map = {}
    auto_count = 0
    problem_count = 0

    for r in results:
        fields = r["fields"]
        best = r["best"]
        score = int(best.get("score", 0))
        needs_confirm = bool(best.get("needs_confirm", True)) or best.get("row_index") is None
        if not needs_confirm:
            auto_count += 1
        else:
            problem_count += 1

        title_icon = "✅" if not needs_confirm else "⚠️"
        with st.expander(f"{title_icon} {r['file_name']} | Score: {score} | {best.get('status','')}", expanded=needs_confirm):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("OCR GR", fields.gr_no or "Not found")
            c2.metric("OCR Truck", fields.truck_no or "Not found")
            c3.metric("OCR Destination", fields.destination or "Not found")
            c4.metric("OCR Date", fields.date or "Not found")

            match = best.get("match") or {}
            if match:
                st.write("Matched booking:", _trip_label_from_match(match))
                st.caption(
                    f"GR {'✅' if match.get('gr_ok') else '❌'} | "
                    f"Truck {'✅' if match.get('truck_ok') else '❌'} | "
                    f"Destination {'✅' if match.get('dest_ok') else '❌'} | "
                    f"Date {'✅' if match.get('date_ok') else '❌'}"
                )

            current_idx = r.get("selected_row_index")
            default_label = idx_to_label.get(current_idx, trip_options[0][0] if trip_options else "")
            if needs_confirm:
                chosen = st.selectbox(
                    "सही booking/trip चुनें",
                    [x[0] for x in trip_options],
                    index=[x[0] for x in trip_options].index(default_label) if default_label in [x[0] for x in trip_options] else 0,
                    key=f"ocr_trip_select_{r['file_index']}_{r['file_name']}",
                )
                final_map[r["file_index"]] = label_to_idx.get(chosen)
            else:
                st.success("4-field high confidence match: confirm की जरूरत नहीं।")
                final_map[r["file_index"]] = current_idx

            with st.expander("OCR raw text", expanded=False):
                st.text(r.get("ocr_text", "")[:4000])

    st.info(f"Auto matched: {auto_count} | Confirm/manual: {problem_count}")
    return final_map


def _save_gr_copies(files, final_map, bookings_df, crop_map=None):
    saved = 0
    links = []
    status = st.status("GR copies save हो रही हैं...", expanded=True)
    for i, f in enumerate(files):
        row_idx = final_map.get(i)
        if row_idx is None:
            status.write(f"Skip: {getattr(f, 'name', i)} — trip select नहीं है")
            continue
        row = bookings_df.loc[row_idx]
        gr_no = safe_cell(row, 8, "N/A")
        truck_no = safe_cell(row, 6, "")
        dest = safe_cell(row, 7, "")
        booking_date = safe_cell(row, 0, "")
        trip_id = safe_cell(row, 14, "")
        try:
            status.write(f"A4 PDF बना रहे हैं: GR {gr_no}")
            pdf_bytes = build_single_upload_as_a4_pdf(
                f, crop_map=crop_map or {}, index=i,
                get_processed_image_func=get_processed_image,
                get_processed_pdf_func=get_processed_pdf_bytes,
            )
            if not pdf_bytes:
                status.write(f"PDF failed: {f.name}")
                continue
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"GR_{_clean_file_part(gr_no)}_{_clean_file_part(truck_no)}_{timestamp}_{i+1:02d}.pdf"
            url = upload_to_drive(pdf_bytes, file_name, "application/pdf")
            if not url:
                status.write(f"Drive upload failed: {f.name}")
                continue
            save_gr_links(trip_id, [url], overwrite=False)
            append_documents_log(
                doc_type="GR / GRD", trip_id=trip_id, gr_no=gr_no, truck_no=truck_no,
                dest=dest, booking_date=booking_date, urls=[url], files_count=1,
                source_files=f.name, remark="Bulk OCR GR upload; single-page A4 PDF",
            )
            saved += 1
            links.append((gr_no, url))
        except Exception as exc:
            status.write(f"Error {f.name}: {exc}")
    status.update(label=f"GR save complete: {saved} file(s)", state="complete" if saved else "error")
    return links


def _save_pod_groups(files, final_map, bookings_df, crop_map=None):
    groups: Dict[int, List[Any]] = {}
    source_names: Dict[int, List[str]] = {}
    for i, f in enumerate(files):
        row_idx = final_map.get(i)
        if row_idx is None:
            continue
        groups.setdefault(row_idx, []).append(f)
        source_names.setdefault(row_idx, []).append(getattr(f, "name", f"file_{i+1}"))

    saved = 0
    links = []
    status = st.status("POD PDFs save हो रही हैं...", expanded=True)
    for row_idx, group_files in groups.items():
        row = bookings_df.loc[row_idx]
        gr_no = safe_cell(row, 8, "N/A")
        truck_no = safe_cell(row, 6, "")
        dest = safe_cell(row, 7, "")
        booking_date = safe_cell(row, 0, "")
        trip_id = safe_cell(row, 14, "")
        try:
            status.write(f"GR {gr_no}: {len(group_files)} POD page(s) की combined A4 PDF बन रही है...")
            # Keep only crop keys relevant to original file indexes; crop tool is optional here.
            pdf_bytes = build_a4_full_pdf_from_uploads(
                group_files, crop_map={},
                get_processed_image_func=get_processed_image,
                get_processed_pdf_func=get_processed_pdf_bytes,
            )
            if not pdf_bytes:
                status.write(f"PDF failed: GR {gr_no}")
                continue
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"POD_GR_{_clean_file_part(gr_no)}_{_clean_file_part(truck_no)}_{timestamp}.pdf"
            status.write(f"GR {gr_no}: Google Drive upload...")
            url = upload_to_drive(pdf_bytes, file_name, "application/pdf")
            if not url:
                status.write(f"Drive upload failed: GR {gr_no}")
                continue
            _save_latest_pod_link(trip_id, gr_no, truck_no, url, len(group_files))
            append_documents_log(
                doc_type="POD", trip_id=trip_id, gr_no=gr_no, truck_no=truck_no,
                dest=dest, booking_date=booking_date, urls=[url], files_count=len(group_files),
                source_files=", ".join(source_names.get(row_idx, [])),
                remark=f"Bulk OCR POD upload; combined A4 PDF; pages={len(group_files)}",
            )
            saved += 1
            links.append((gr_no, url, len(group_files)))
        except Exception as exc:
            status.write(f"Error GR {gr_no}: {exc}")
    status.update(label=f"POD save complete: {saved} PDF(s)", state="complete" if saved else "error")
    return links


def show_bulk_ocr_upload_page():
    st.header("🤖 Bulk OCR Upload")
    st.caption("Multiple photos upload करें. OCR GR/Truck/Destination/Date read करेगा. जहाँ 4-field match नहीं होगा, सिर्फ वहाँ confirm माँगेगा।")

    st.info("OCR direct auto-save नहीं करेगा. पहले preview बनेगा. High confidence rows auto-confirm रहेंगी; mismatch rows में trip manually चुनना होगा।")

    df = get_bookings_df()
    if df.empty:
        st.warning("Bookings sheet में data नहीं मिला।")
        return

    doc_type = st.radio("Document Type", ["POD Copy", "GR Copy"], horizontal=True, key="bulk_ocr_doc_type")
    files = st.file_uploader(
        "Multiple photos/PDF select करें",
        type=["jpg", "jpeg", "png", "heic", "heif", "pdf"],
        accept_multiple_files=True,
        key="bulk_ocr_files",
    )

    if not files:
        st.info("पहले files select करें।")
        return

    st.write(f"Selected files: {len(files)}")
    if st.button("🔎 OCR Read + Booking Match", type="primary", use_container_width=True):
        with st.spinner("OCR चल रहा है..."):
            st.session_state["bulk_ocr_results"] = _run_ocr_for_files(files, df)
            st.session_state["bulk_ocr_file_count"] = len(files)
        st.rerun()

    results = st.session_state.get("bulk_ocr_results", [])
    if not results:
        return
    if len(results) != len(files):
        st.warning("Files बदल गई हैं. OCR दोबारा चलाएँ।")
        return

    st.subheader("Review Match")
    final_map = _render_match_review(results, df)

    if doc_type == "POD Copy":
        st.success("POD mode: Same GR/trip वाली photos group होकर एक combined multi-page A4 PDF बनेंगी।")
    else:
        st.success("GR mode: हर photo अपनी booking में single-page A4 PDF के रूप में save होगी।")

    if st.button("✅ Confirm & Save", type="primary", use_container_width=True):
        if doc_type == "POD Copy":
            saved_links = _save_pod_groups(files, final_map, df)
            for gr, url, pages in saved_links:
                st.link_button(f"POD GR {gr} खोलें ({pages} pages)", url)
        else:
            saved_links = _save_gr_copies(files, final_map, df)
            for gr, url in saved_links:
                st.link_button(f"GR {gr} खोलें", url)
        time.sleep(1)
