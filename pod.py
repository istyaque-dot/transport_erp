import streamlit as st
import datetime
import time
import pandas as pd
import gspread
import base64
from oauth2client.service_account import ServiceAccountCredentials
import requests
from PIL import Image
from crop_utils import get_processed_image, get_processed_pdf_bytes, render_crop_tool
from a4_pdf_utils import build_a4_full_pdf_from_uploads
from doc_link_utils import extract_pod_links_from_owner_rows
import io
import json

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

# A4 size pixels at 150 DPI
A4_W, A4_H = 1240, 1754 

# ==========================================
# 🗄️ DATABASE CONNECTION
# ==========================================

from sheet_utils import connect_to_sheet, invalidate_sheet_cache

# Local fallback helpers so POD page does not crash if GitHub has an older sheet_utils.py.
# Search sequence: GR / Truck No / Destination / Date / Trip ID
TRIP_SEARCH_INDEXES = [8, 6, 7, 0, 14]

def safe_cell(row, idx, default=""):
    try:
        val = row.iloc[idx] if hasattr(row, "iloc") else row[idx]
        if val is None:
            return default
        text = str(val).strip()
        if text.lower() in ("", "nan", "none"):
            return default
        return text
    except Exception:
        return default

def format_trip_label(row):
    gr = safe_cell(row, 8, "N/A")
    truck = safe_cell(row, 6, "N/A")
    dest = safe_cell(row, 7, "N/A")
    date = safe_cell(row, 0, "N/A")[:10]
    trip_id = safe_cell(row, 14, "N/A")
    return f"GR: {gr} | 🚛 {truck} | 📍 {dest} | 📅 {date} | ID: {trip_id}"

def trip_search_blob(row):
    return " ".join(safe_cell(row, i, "") for i in TRIP_SEARCH_INDEXES).lower()

def trip_matches(row, query):
    q = str(query or "").strip().lower()
    if not q:
        return True
    terms = [t for t in q.replace("/", " ").replace("|", " ").split() if t]
    blob = trip_search_blob(row)
    return all(t in blob for t in terms)

def filter_trip_dataframe(df, query):
    if df is None or getattr(df, "empty", True):
        return df
    q = str(query or "").strip()
    if not q:
        return df
    try:
        return df[df.apply(lambda row: trip_matches(row, q), axis=1)].reset_index(drop=True)
    except Exception:
        return df

# ==========================================
# 📦 DATA FETCHERS
# ==========================================

@st.cache_data(ttl=300)
def get_owner_ledger_data():
    try:
        db = connect_to_sheet()
        return db.worksheet("Owner_Ledger").get_all_values()
    except Exception as e:
        st.error(f"Owner ledger load error: {e}")
        return []

@st.cache_data(ttl=300)
def get_bookings_data_for_pod():
    try:
        db = connect_to_sheet()
        return db.worksheet("Bookings").get_all_values()
    except Exception as e:
        st.error(f"Bookings load error: {e}")
        return []

@st.cache_data(ttl=300)
def get_trip_summary(trip_id):
    """ट्रिप का पूरा कच्चा-चिट्ठा निकालना (Freight, Advances, Adjustments)"""
    try:
        db = connect_to_sheet()
        bk_data = db.worksheet("Bookings").get_all_values()
        trip_bk = None
        for r in bk_data[1:]:
            if len(r) > 14 and str(r[14]).strip() == trip_id:
                trip_bk = {
                    'weight': float(str(r[5]).replace(',', '')),
                    'truck freight': float(str(r[12]).replace(',', ''))
                }
                break

        adv_data = db.worksheet("Advances").get_all_values()
        def adv_amount(row):
            # New schema: total at col 9/index 8. Old schema: amount at col 6/index 5.
            try:
                if len(row) > 8:
                    return int(float(str(row[8]).replace(',', '') or 0))
                if len(row) > 5:
                    return int(float(str(row[5]).replace(',', '') or 0))
            except Exception:
                return 0
            return 0
        total_adv = sum(
            adv_amount(r)
            for r in adv_data[1:]
            if len(r) > 1 and str(r[1]).strip() == trip_id
        )

        df_owner_raw = get_owner_ledger_data()
        df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])
        already_adj = 0
        existing_pod_urls = []

        if not df_owner.empty and len(df_owner.columns) > 5:
            adj_rows = df_owner[df_owner.iloc[:, 1] == trip_id]
            for _, r in adj_rows.iterrows():
                desc = str(r.iloc[4])
                if any(k in desc for k in ["Shortage", "Extra", "Detention"]):
                    try:
                        already_adj += int(float(str(r.iloc[5]).replace(',', '') or 0))
                    except: pass
        # Support old and new POD link formats: POD Link:, POD Link 1:, raw Drive IDs, and multi-links.
        existing_pod_urls = extract_pod_links_from_owner_rows(df_owner_raw, trip_id)

        return trip_bk, total_adv, already_adj, existing_pod_urls
    except Exception as e:
        st.error(f"डेटा लोड एरर: {e}")
        return None, 0, 0, []

# ==========================================
# 📄 A4 PDF BUILDER
# ==========================================

def image_to_a4(img: Image.Image) -> Image.Image:
    # Legacy wrapper retained for compatibility; actual upload uses build_a4_pdf below.
    from a4_pdf_utils import image_to_a4_full_page
    return image_to_a4_full_page(img)

def build_a4_pdf(image_files, crop_map=None) -> bytes | None:
    """Build full-page A4 PDF for POD/GR files.

    Also fixes old PDFs where the document image is pasted small in the center.
    """
    return build_a4_full_pdf_from_uploads(
        list(image_files or []),
        crop_map=crop_map or {},
        get_processed_image_func=get_processed_image,
        get_processed_pdf_func=get_processed_pdf_bytes,
    )

# ==========================================
# 📤 DRIVE & LEDGER FUNCTIONS
# ==========================================

def upload_to_drive(file_bytes, file_name):
    mime_type = "application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg"
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    payload = {"fileName": file_name, "mimeType": mime_type, "fileData": b64_data}
    try:
        res = requests.post(WEB_APP_URL, data=payload, timeout=60)
        result = res.text.strip()
        return result if "Error" not in result else None
    except: return None

def save_pod_to_drive(db, gr_no, truck_no, trip_id, up_files, crop_map=None):
    with st.spinner("📄 A4 PDF बन रही है और अपलोड हो रही है..."):
        final_bytes = build_a4_pdf(up_files, crop_map=crop_map)
        if final_bytes:
            f_name = f"POD_{gr_no}_{truck_no}.pdf"
            d_id = upload_to_drive(final_bytes, f_name)
            if d_id:
                pod_url = d_id if d_id.startswith("http") else f"https://drive.google.com/file/d/{d_id}/view"
                db.worksheet("Owner_Ledger").append_row([str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0])
                invalidate_sheet_cache()
                st.success("✅ POD सुरक्षित हो गई!")
                time.sleep(1.5); st.rerun()
            else: st.error("❌ Drive अपलोड फेल!")

def save_balance_to_ledgers(db, date_val, trip_id, gr_no, truck_no, amount, bank_name, remark):
    try:
        # 1. मालिक के लेजर में फाइनल एंट्री
        db.worksheet("Owner_Ledger").append_row([str(date_val), trip_id, gr_no, truck_no, f"Final Balance: {remark}", -int(amount)])
        # 2. बैंक लेजर में एंट्री
        sheet_map = {"Cash": "Cash_Ledger", "canara bank 311": "Canara_311_Ledger", "canara bank 41": "Canara_41_Ledger", "bob": "BOB_Ledger"}
        s_name = sheet_map.get(bank_name)
        if s_name: db.worksheet(s_name).append_row([str(date_val), trip_id, gr_no, f"Final Pay: {truck_no}", -int(amount)])
        # 3. एडवांस शीट में फाइनल सेटलमेंट रिकॉर्ड
        c_amt = amount if bank_name == "Cash" else 0
        b_amt = amount if bank_name != "Cash" else 0
        db.worksheet("Advances").append_row([str(date_val), trip_id, truck_no, 0, f"Final Settlement ({remark})", c_amt, b_amt, bank_name, int(amount)])
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_pod_page():
    st.markdown("""
        <style>
            .block-container { padding-top: 3.5rem !important; max-width: 98% !important; }
            h2 { font-size: 1.3rem !important; }
            .balance-card-due { background: #fff3cd; border: 1.5px solid #ffc107; border-radius: 8px; padding: 8px; text-align: center; font-weight: bold; color: #856404; }
            .balance-card-clear { background: #d1e7dd; border: 1.5px solid #0f5132; border-radius: 8px; padding: 8px; text-align: center; font-weight: bold; color: #0f5132; }
            .custom-box { background: #f8f9fa; border: 1px solid #d1d5db; border-radius: 6px; padding: 10px; }
            .pod-badge { background: #d1e7dd; border: 1px solid #0f5132; border-radius: 20px; padding: 2px 12px; font-size: 0.78rem; color: #0f5132; font-weight: bold; display: inline-block; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🏁 POD और फाइनल हिसाब (Settlement)")

    df_owner_raw = get_owner_ledger_data()
    if len(df_owner_raw) <= 1:
        st.info("कोई पेंडिंग हिसाब नहीं मिला।"); return

    df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])
    if df_owner.empty or df_owner.shape[1] < 6:
        st.info("Owner_Ledger में जरूरी columns नहीं मिले।")
        return
    EXCLUDE = r"Shortage:|Extra/Detention:|Final Balance:|Final Pay:|POD\s*Link"
    df_pending = df_owner[~df_owner.iloc[:, 4].astype(str).str.contains(EXCLUDE, case=False, na=False)].iloc[::-1]
    if df_pending.empty:
        st.info("कोई पेंडिंग हिसाब नहीं मिला।")
        return

    st.markdown("<hr>", unsafe_allow_html=True)
    # Build booking lookup so POD search also supports Destination and Date.
    bk_raw = get_bookings_data_for_pod()
    bk_map = {str(r[14]).strip(): r for r in bk_raw[1:] if len(r) > 14} if len(bk_raw) > 1 else {}

    search_gr = st.text_input(
        "🔍 Search",
        placeholder="GR / गाड़ी नंबर / Destination / Date / Trip ID लिखें — खाली छोड़ें तो पूरी list",
        key="pod_global_search"
    )

    choice_rows = []
    seen_trip_ids = set()
    for _, r in df_pending.iterrows():
        tid = safe_cell(r, 1, "")
        if tid in seen_trip_ids:
            continue
        seen_trip_ids.add(tid)
        bk_row = bk_map.get(tid)
        label = format_trip_label(bk_row) if bk_row else f"GR: {safe_cell(r,2,'N/A')} | 🚛 {safe_cell(r,3,'N/A')} | 📍 N/A | 📅 N/A | ID: {tid}"
        blob_row = bk_row if bk_row else ["", "", "", "", "", "", safe_cell(r,3,''), "", safe_cell(r,2,''), "", "", "", "", "", tid]
        if trip_matches(blob_row, search_gr):
            choice_rows.append((label, tid))
    st.caption(f"Dropdown में {len(choice_rows)} pending trip(s) loaded")
    choices = [x[0] for x in choice_rows]

    selected = st.selectbox("📝 गाड़ी चुनें", ["चुनें..."] + choices, label_visibility="collapsed")
    if selected == "चुनें...": st.info("👆 ऊपर से गाड़ी चुनें।"); return

    trip_id = selected.split("ID: ")[-1].strip()
    selected_bk = bk_map.get(trip_id)
    if selected_bk:
        gr_no = safe_cell(selected_bk, 8, "N/A")
        truck_no = safe_cell(selected_bk, 6, "N/A")
    else:
        parts = selected.split(" | ")
        gr_no = parts[0].replace("GR: ", "") if len(parts) > 0 else "N/A"
        truck_no = parts[1].replace("🚛 ", "") if len(parts) > 1 else "N/A"
    trip_bk, total_adv, already_adj, existing_pod_urls = get_trip_summary(trip_id)

    if not trip_bk: st.error("❌ डेटा नहीं मिला।"); return

    owner_freight = int(trip_bk['truck freight'])
    st.markdown("### 📊 लाइव पासबुक")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("कुल भाड़ा", f"₹{owner_freight:,}")
    with c2: st.metric("एडवांस भुगतान", f"₹{total_adv:,}")
    with c3: munshiyana = st.number_input("✍️ मुंशीयाना", min_value=0, value=int(trip_bk['weight'] * 1), step=50)
    current_bal = (owner_freight - munshiyana - total_adv) + already_adj

    with c4:
        st.markdown(f"<div class='balance-card-due'>💰 बाकी देना<br>₹{current_bal:,}</div>" if current_bal > 0 else f"<div class='balance-card-clear'>✅ हिसाब क्लियर<br>₹{current_bal:,}</div>", unsafe_allow_html=True)

    if existing_pod_urls:
        st.markdown("<span class='pod-badge'>📄 POD सेव है</span>", unsafe_allow_html=True)
        for i, pod_url in enumerate(existing_pod_urls, start=1):
            st.link_button(f"📥 POD / बिल्टी {i} देखें", pod_url, type="secondary")

    st.markdown("<hr>", unsafe_allow_html=True)
    db = connect_to_sheet()

    if current_bal <= 0:
        st.success("✅ हिसाब पूरा हो चुका है।")
        if not existing_pod_urls:
            with st.container():
                st.markdown("#### 📄 बिल्टी (POD) अपलोड करें")
                up_files = st.file_uploader("Upload", type=["pdf", "jpg", "jpeg", "png", "heic", "heif"], accept_multiple_files=True, key="pod_only", label_visibility="collapsed")
                pod_crop_map = render_crop_tool(up_files, key_prefix=f"pod_only_crop_{trip_id}", title="✂️ POD Crop Tool") if up_files else {}
                if up_files and st.button("🚀 सेव करें", type="primary", use_container_width=True):
                    save_pod_to_drive(db, gr_no, truck_no, trip_id, up_files, crop_map=pod_crop_map)
        return

    # हिसाब बाकी होने पर सेटलमेंट फॉर्म
    col_pod, col_pay = st.columns([1, 1.4], gap="small")
    with col_pod:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 📄 1. POD अपलोड")
        up_f = st.file_uploader("Files", type=["pdf", "jpg", "jpeg", "png", "heic", "heif"], accept_multiple_files=True, key="pod_sep", label_visibility="collapsed")
        pod_sep_crop_map = render_crop_tool(up_f, key_prefix=f"pod_sep_crop_{trip_id}", title="✂️ POD Crop Tool") if up_f else {}
        if up_f and st.button("🚀 PDF सेव करें", use_container_width=True): save_pod_to_drive(db, gr_no, truck_no, trip_id, up_f, crop_map=pod_sep_crop_map)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_pay:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 💳 2. फाइनल सेटलमेंट")
        r1, r2 = st.columns(2)
        shortage = r1.number_input("कटी (−₹)", min_value=0, step=50)
        extra_pay = r2.number_input("एक्स्ट्रा (+₹)", min_value=0, step=100)
        pay_mode = st.selectbox("बैंक/कैश", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])
        final_pay = current_bal - shortage + extra_pay
        st.markdown(f"<div class='balance-card-due'> हाथ में देना: ₹{final_pay:,}</div>", unsafe_allow_html=True)
        if st.button("✅ फुल एंड फाइनल करें", type="primary", use_container_width=True):
            if pay_mode == "N/A" and final_pay > 0: st.error("⚠️ खाता चुनें!")
            else:
                with st.spinner("प्रोसेसिंग..."):
                    t_date = str(datetime.date.today())
                    if shortage > 0: db.worksheet("Owner_Ledger").append_row([t_date, trip_id, gr_no, truck_no, "Shortage", -int(shortage)])
                    if extra_pay > 0: db.worksheet("Owner_Ledger").append_row([t_date, trip_id, gr_no, truck_no, "Extra/Detention", int(extra_pay)])
                    if save_balance_to_ledgers(db, t_date, trip_id, gr_no, truck_no, final_pay, pay_mode, "Final Settlement"):
                        invalidate_sheet_cache(); st.success("🎊 हिसाब बराबर!"); time.sleep(1.5); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
