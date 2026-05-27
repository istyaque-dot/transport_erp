import streamlit as st
import datetime
import time
import pandas as pd
import requests
import base64
from PIL import Image
from crop_utils import get_processed_image, get_processed_pdf_bytes, render_crop_tool
import io
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from supabase import create_client

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

# ==========================================
# 🗄️ SUPABASE DATABASE CONNECTION (Legacy - not used in main flow)
# ==========================================
@st.cache_resource
def get_supabase_client():
    try:
        clean_url = str(st.secrets["supabase"]["url"]).strip()
        clean_key = str(st.secrets["supabase"]["key"]).strip()
        return create_client(clean_url, clean_key)
    except:
        return None

try:
    supabase = get_supabase_client()
except Exception:
    supabase = None

def upload_to_drive(file_bytes, file_name):
    if file_name.lower().endswith(".pdf"):
        mime_type = "application/pdf"
    elif file_name.lower().endswith(".png"):
        mime_type = "image/png"
    else:
        mime_type = "image/jpeg"
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    payload = {"fileName": file_name, "mimeType": mime_type, "fileData": b64_data}
    try:
        res = requests.post(WEB_APP_URL, data=payload, timeout=60)
        result = res.text.strip()
        return result if "Error" not in result else None
    except:
        return None

# ==========================================
# ✅ STABILITY PATCH: Google Sheets mode (Active)
# ==========================================
from sheet_utils import connect_to_sheet as connect_to_sheet_booking, invalidate_sheet_cache, format_trip_label, filter_trip_dataframe, safe_cell

def save_booking_to_db(row_data):
    try:
        db = connect_to_sheet_booking()
        db.worksheet("Bookings").append_row(row_data, table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as e:
        st.error(f"Booking save error: {e}")
        return False

@st.cache_data(ttl=600)
def get_all_trips():
    try:
        db = connect_to_sheet_booking()
        data = db.worksheet("Bookings").get_all_values()
        if len(data) <= 1:
            return pd.DataFrame()
        max_cols = max(len(r) for r in data)
        rows = [r + [""] * (max_cols - len(r)) for r in data]
        header = rows[0]
        return pd.DataFrame(rows[1:], columns=header)
    except Exception as e:
        st.error(f"Booking load error: {e}")
        return pd.DataFrame()

def update_booking_in_db(trip_id, updated_row):
    try:
        db = connect_to_sheet_booking()
        ws = db.worksheet("Bookings")
        ids = [str(x).strip() for x in ws.col_values(15)]
        tid = str(trip_id).strip()
        if tid in ids:
            row_index = ids.index(tid) + 1
            ws.update(f"A{row_index}:P{row_index}", [updated_row])
            invalidate_sheet_cache()
            return True
        st.error("Trip ID नहीं मिला।")
        return False
    except Exception as e:
        st.error(f"Booking update error: {e}")
        return False

def save_gr_link_to_db(trip_id, gr_url):
    try:
        db = connect_to_sheet_booking()
        ws = db.worksheet("Bookings")
        ids = [str(x).strip() for x in ws.col_values(15)]
        tid = str(trip_id).strip()
        if tid in ids:
            row_index = ids.index(tid) + 1
            ws.update_cell(row_index, 17, gr_url)
            invalidate_sheet_cache()
            return True
        return False
    except Exception as e:
        st.error(f"GR link save error: {e}")
        return False

def save_to_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        db = connect_to_sheet_booking()
        gr = str(gr_no).strip() if str(gr_no).strip() else "N/A"
        base = [str(date_val), str(trip_id), gr, str(truck_no), str(dest)]
        db.worksheet("Company_Ledger").append_row(base + [int(comp_amt)], table_range="A1")
        db.worksheet("Owner_Ledger").append_row(base + [int(owner_amt)], table_range="A1")
        if int(float(uni_amt or 0)) > 0:
            db.worksheet("Universal_Ledger").append_row([str(date_val), str(trip_id), "N/A", "N/A", f"Freight: {truck_no}", int(uni_amt)], table_range="A1")
        if int(float(ish_amt or 0)) > 0:
            db.worksheet("Ishtyaque_Ledger").append_row([str(date_val), str(trip_id), "N/A", "N/A", f"Profit: {truck_no}", int(ish_amt)], table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as e:
        st.error(f"Ledger insert error: {e}")
        return False

def update_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        db = connect_to_sheet_booking()
        gr = str(gr_no).strip() if str(gr_no).strip() else "N/A"
        ledgers = {
            "Company_Ledger": int(comp_amt),
            "Owner_Ledger": int(owner_amt),
            "Universal_Ledger": int(float(uni_amt or 0)),
            "Ishtyaque_Ledger": int(float(ish_amt or 0)),
        }
        for sheet_name, amt in ledgers.items():
            if amt == 0 and sheet_name in ["Universal_Ledger", "Ishtyaque_Ledger"]:
                continue
            ws = db.worksheet(sheet_name)
            records = ws.get_all_values()
            row_to_update = -1
            for i, row in enumerate(records):
                if len(row) > 1 and str(row[1]).strip() == str(trip_id).strip():
                    row_to_update = i + 1
                    break
            if sheet_name == "Universal_Ledger":
                new_row = [str(date_val), str(trip_id), "N/A", "N/A", f"Freight: {truck_no}", amt]
            elif sheet_name == "Ishtyaque_Ledger":
                new_row = [str(date_val), str(trip_id), "N/A", "N/A", f"Profit: {truck_no}", amt]
            else:
                new_row = [str(date_val), str(trip_id), gr, str(truck_no), str(dest), amt]
            if row_to_update != -1:
                ws.update(f"A{row_to_update}:F{row_to_update}", [new_row])
            else:
                ws.append_row(new_row, table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as e:
        st.error(f"Ledger update error: {e}")
        return False

# ==========================================
# 🎨 CSS
# ==========================================
BOOKING_CSS = """
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px !important; background: #f0f4ff !important; border-radius: 10px !important; padding: 4px !important; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px !important; padding: 4px 16px !important; font-weight: 600 !important; font-size: 0.88rem !important; color: #444 !important; }
    .stTabs [aria-selected="true"] { background: #003399 !important; color: white !important; }
    div[data-testid="stForm"] { background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 12px !important; padding: 16px 20px !important; box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important; }
    h2 { font-size: 1.4rem !important; margin-bottom: 2px !important; color: #111 !important; }
    h3 { font-size: 1.1rem !important; margin-bottom: 4px !important; color: #222 !important; }
    h4 { font-size: 1rem !important; margin-bottom: 4px !important; color: #003399 !important; }
    div[data-testid="stVerticalBlock"] { gap: 0.45rem !important; }
    div[data-testid="stHorizontalBlock"] { gap: 0.55rem !important; }
    .stTextInput > div > div > input, .stNumberInput > div > div > input { border-radius: 7px !important; border: 1px solid #cbd5e1 !important; padding: 4px 10px !important; min-height: 1.9rem !important; font-size: 0.88rem !important; background: #fafafa !important; }
    .stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus { border-color: #003399 !important; background: #fff !important; box-shadow: 0 0 0 2px rgba(0,51,153,0.1) !important; }
    .stSelectbox > div > div { border-radius: 7px !important; border: 1px solid #cbd5e1 !important; min-height: 1.9rem !important; font-size: 0.88rem !important; }
    label { font-size: 0.8rem !important; font-weight: 700 !important; color: #374151 !important; margin-bottom: 0px !important; }
    .stButton > button { border-radius: 8px !important; min-height: 1.9rem !important; font-size: 0.88rem !important; font-weight: 600 !important; padding: 2px 14px !important; transition: all 0.15s ease !important; }
    .stButton > button[kind="primary"] { background: linear-gradient(135deg, #003399, #0055cc) !important; border: none !important; color: white !important; }
    .stButton > button[kind="primary"]:hover { background: linear-gradient(135deg, #002277, #0044aa) !important; box-shadow: 0 3px 10px rgba(0,51,153,0.3) !important; }
    div[data-testid="stAlert"] { border-radius: 8px !important; padding: 6px 12px !important; margin: 2px 0 !important; }
    div[data-testid="stAlert"] p { font-size: 0.88rem !important; margin: 0 !important; }
    div[data-testid="metric-container"] { background: linear-gradient(135deg, #f0f4ff, #e8eeff) !important; border: 1px solid #c7d4f5 !important; border-radius: 10px !important; padding: 8px 12px !important; }
    div[data-testid="stMetricValue"] { font-size: 1.15rem !important; font-weight: 700 !important; color: #003399 !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; font-weight: 600 !important; color: #555 !important; }
    .gr-box { background: #f8faff; border: 1px solid #c7d4f5; border-radius: 10px; padding: 14px; height: 100%; }
    .summary-bar { background: linear-gradient(135deg, #003399, #0055cc); border-radius: 10px; padding: 10px 18px; color: white; font-size: 0.9rem; font-weight: 600; margin: 6px 0; }
    .summary-bar span { margin-right: 28px; }
    .confirm-box { background: #fffbeb; border: 1.5px solid #f59e0b; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; }
    hr { margin: 0.4em 0 !important; border-color: #e2e8f0 !important; }
</style>
"""

# ==========================================
# Helper Function for Bulk Processing
# ==========================================
def _process_bulk_bookings(df_upload):
    if df_upload is None or df_upload.empty:
        st.warning("कोई data नहीं मिला।")
        return

    success_count, error_count = 0, 0
    progress_bar = st.progress(0, text="सेव हो रही हैं...")

    with st.spinner(f"⏳ {len(df_upload)} गाड़ियाँ सेव हो रही हैं..."):
        total = len(df_upload)
        for index, row in df_upload.iterrows():
            try:
                def clean_num(val):
                    try: return float(val) if pd.notna(val) else 0
                    except: return 0
                def clean_str(val):
                    return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

                date_str    = clean_str(row.get("Date (YYYY-MM-DD)", "")) or str(datetime.date.today())
                from_loc    = clean_str(row.get("From", "Kashipur"))
                company     = clean_str(row.get("Company", "Other"))
                owner_rate  = clean_num(row.get("Owner Rate", 0))
                comp_rate   = clean_num(row.get("Company Rate", 0))
                weight      = clean_num(row.get("Weight", 0))
                truck_no    = clean_str(row.get("Truck No", ""))
                to_loc      = clean_str(row.get("To", ""))
                gr_no       = clean_str(row.get("GR No", "N/A"))
                uni_amt     = clean_num(row.get("Universal Amt", 0))
                comments    = clean_str(row.get("Comments", ""))
                ish_amt     = clean_num(row.get("Ishtyaque Profit", 0))

                if not truck_no or not to_loc:
                    error_count += 1
                    continue

                comp_freight   = int(weight * comp_rate) + int(uni_amt)
                owner_freight  = int(weight * owner_rate)
                final_uni_amt  = int(uni_amt * 0.99) if uni_amt > 0 else 0
                trip_id = f"TRP-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}{index}"

                row_data = [
                    date_str, from_loc, company,
                    owner_rate, comp_rate, weight,
                    truck_no, to_loc,
                    gr_no if gr_no else "N/A",
                    int(uni_amt), comments,
                    comp_freight, owner_freight,
                    final_uni_amt, trip_id, int(ish_amt)
                ]
                if save_booking_to_db(row_data):
                    save_to_ledgers(date_str, trip_id, gr_no, truck_no, to_loc, comp_freight, owner_freight, final_uni_amt, int(ish_amt))
                    success_count += 1
                    time.sleep(0.08)
                else:
                    error_count += 1

                progress_bar.progress((index + 1) / total, text=f"✅ {success_count} सेव | ⚠️ {error_count} skip")
            except:
                error_count += 1
                continue

    invalidate_sheet_cache()
    if success_count > 0:
        st.success(f"🎊 {success_count} गाड़ियाँ सफलतापूर्वक सेव हो गईं!")
    if error_count > 0:
        st.warning(f"⚠️ {error_count} rows skip हुईं (गाड़ी नंबर या Destination खाली था)।")

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================
def show_booking_page():
    st.markdown(BOOKING_CSS, unsafe_allow_html=True)
    st.header("🚛 बुकिंग मैनेजमेंट")

    if "bk_ck" not in st.session_state: st.session_state.bk_ck = 0
    if "show_confirm" not in st.session_state: st.session_state.show_confirm = False
    if "bk_saving_lock" not in st.session_state: st.session_state.bk_saving_lock = False

    c = st.session_state.bk_ck
    tab1, tab2, tab3 = st.tabs(["🆕 नई गाड़ी (Single)", "✏️ एडिट बुकिंग", "📑 बल्क अपलोड (Excel / Google Sheet)"])

    # TAB 1 & TAB 2 same rahega (aapke paste jaisa)

    # ══════════════════════════════════════
    # TAB 3 — बल्क अपलोड (Excel + Google Sheet)
    # ══════════════════════════════════════
    with tab3:
        st.markdown("### 📑 बल्क बुकिंग अपलोड (Excel / Google Sheet)")

        template_cols = [
            "Date (YYYY-MM-DD)", "From", "Company", "Owner Rate", "Company Rate",
            "Weight", "Truck No", "To", "GR No", "Universal Amt",
            "Comments", "Ishtyaque Profit"
        ]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame(columns=template_cols).to_excel(writer, index=False, sheet_name='BulkBooking')

        col_dl, _ = st.columns([1, 2])
        with col_dl:
            st.download_button(
                label="⬇️ Excel Template डाउनलोड करें",
                data=output.getvalue(),
                file_name="Khan_Transport_Bulk_Format.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.caption("💡 Tip: Google Sheet में भी ऊपर वाले columns के नाम इस्तेमाल करें (पहली row header होनी चाहिए)")

        st.divider()

        import_mode = st.radio(
            "Import Mode चुनें",
            ["📁 Excel/CSV File Upload", "📊 Google Sheet Tab से Direct Import"],
            horizontal=True,
            key="bulk_import_mode"
        )

        # MODE 1: Excel/CSV
        if import_mode == "📁 Excel/CSV File Upload":
            uploaded_excel = st.file_uploader(
                "📥 भरी हुई Excel/CSV अपलोड करें",
                type=["xlsx", "xls", "csv"],
                key="bulk_excel_uploader"
            )
            if uploaded_excel is not None:
                try:
                    df_upload = (pd.read_csv(uploaded_excel) if uploaded_excel.name.endswith('.csv') else pd.read_excel(uploaded_excel))
                    st.markdown(f"**📋 {len(df_upload)} गाड़ियाँ मिलीं — नीचे चेक करें:**")
                    st.dataframe(df_upload, use_container_width=True, height=250)

                    if st.button("🚀 सभी गाड़ियाँ सेव करें (Excel से)", type="primary", use_container_width=True, key="bulk_save_excel"):
                        _process_bulk_bookings(df_upload)
                except Exception as e:
                    st.error(f"❌ Excel फाइल पढ़ने में दिक्कत: {e}")

        # MODE 2: Google Sheet Tab
        else:
            st.info("⚡ Google Sheet के उसी Workbook में कोई भी Tab (जैसे: `Bulk_Import_Bookings`) बना लें। पहली row में headers होने चाहिए।")

            source_sheet = st.text_input(
                "📋 Source Google Sheet Tab का नाम",
                value="Bulk_Import_Bookings",
                placeholder="जैसे: Bulk_Import_Bookings",
                key="bulk_gs_sheet_name"
            )

            if st.button("🔄 Google Sheet से Data Load करें", type="secondary", use_container_width=True, key="bulk_gs_load"):
                try:
                    db = connect_to_sheet_booking()
                    raw_data = db.worksheet(source_sheet).get_all_values()
                    if len(raw_data) <= 1:
                        st.warning("⚠️ Source sheet में data नहीं मिला या सिर्फ header है।")
                    else:
                        header = raw_data[0]
                        df_gs = pd.DataFrame(raw_data[1:], columns=header)
                        st.session_state["bulk_gs_df"] = df_gs
                        st.success(f"✅ {len(df_gs)} rows Google Sheet `{source_sheet}` से load हो गईं!")
                except Exception as e:
                    st.error(f"❌ Google Sheet से data load नहीं हो पाया: {e}")
                    st.info("Sheet का नाम सही है? Sheet Setup tab चलाकर worksheet create कर लें।")

            if st.session_state.get("bulk_gs_df") is not None and not st.session_state.get("bulk_gs_df", pd.DataFrame()).empty:
                df_gs = st.session_state["bulk_gs_df"]
                st.markdown(f"**📋 {len(df_gs)} गाड़ियाँ Google Sheet से मिलीं — चेक करें:**")
                st.dataframe(df_gs, use_container_width=True, height=250)

                if st.button("🚀 सभी गाड़ियाँ सेव करें (Google Sheet से)", type="primary", use_container_width=True, key="bulk_save_gs"):
                    _process_bulk_bookings(df_gs)
                    if st.button("🔄 नया Import करें", key="clear_gs_bulk"):
                        if "bulk_gs_df" in st.session_state:
                            del st.session_state["bulk_gs_df"]
                        st.rerun()

# Note: Tab 1 and Tab 2 ka code aapke paste jaisa hi rakha hai (sirf Tab 3 update kiya hai)
