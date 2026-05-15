import streamlit as st
import datetime
import time
import pandas as pd
import requests
import base64
from PIL import Image
import io
import zipfile
import re
from supabase import create_client

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

# ==========================================
# 🗄️ SUPABASE DATABASE CONNECTION
# ==========================================
@st.cache_resource
def get_supabase_client():
    clean_url = str(st.secrets["supabase"]["url"]).strip()
    clean_key = str(st.secrets["supabase"]["key"]).strip()
    return create_client(clean_url, clean_key)

supabase = get_supabase_client()

def upload_to_drive(file_bytes, file_name):
    if file_name.lower().endswith(".pdf"): mime_type = "application/pdf"
    elif file_name.lower().endswith(".png"): mime_type = "image/png"
    else: mime_type = "image/jpeg"
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    payload = {"fileName": file_name, "mimeType": mime_type, "fileData": b64_data}
    try:
        res = requests.post(WEB_APP_URL, data=payload)
        result = res.text.strip()
        return result if "Error" not in result else None
    except: return None

# 🟢 A4 SIZE PDF LOGIC
def prepare_pod_file(uploaded_files):
    if not uploaded_files: return None, None
    if len(uploaded_files) == 1 and uploaded_files[0].name.lower().endswith(".pdf"):
        return uploaded_files[0].read(), "pdf"
        
    A4_WIDTH = 2480
    A4_HEIGHT = 3508
    
    a4_images = []
    for file in uploaded_files:
        if file.name.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(file)
            if img.mode != 'RGB': img = img.convert('RGB')
            
            try:
                img.thumbnail((A4_WIDTH, A4_HEIGHT), Image.Resampling.LANCZOS)
            except AttributeError:
                img.thumbnail((A4_WIDTH, A4_HEIGHT), Image.LANCZOS)
            
            a4_canvas = Image.new('RGB', (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            
            x_offset = (A4_WIDTH - img.width) // 2
            y_offset = (A4_HEIGHT - img.height) // 2
            a4_canvas.paste(img, (x_offset, y_offset))
            
            a4_images.append(a4_canvas)
            
    if a4_images:
        pdf_bytes = io.BytesIO()
        if len(a4_images) == 1: 
            a4_images[0].save(pdf_bytes, format="PDF", resolution=300)
        else: 
            a4_images[0].save(pdf_bytes, format="PDF", resolution=300, save_all=True, append_images=a4_images[1:])
        return pdf_bytes.getvalue(), "pdf"
    return None, None

def save_gr_link_to_db(trip_id, gr_url):
    try:
        supabase.table("bookings").update({"google_url": gr_url}).eq("trip_id", str(trip_id)).execute()
        return True
    except: return False



# ==========================================
# 📥 BULK EDIT / GR-POD FILE UPDATE HELPERS
# ==========================================
def _norm_key(val):
    """GR/Truck exact matching: spaces, hyphen, case ignore; 45.0 -> 45."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    text = str(val).strip()
    if text.lower() in ("nan", "none", "n/a", ""):
        return ""
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def _clean_str(val, default=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    text = str(val).strip()
    return default if text.lower() in ("nan", "none", "") else text


def _clean_num(val, default=None):
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return default
    try:
        return float(val)
    except Exception:
        return default


class _BytesFile:
    def __init__(self, name, data):
        self.name = name
        self._data = data
        self._pos = 0
    def read(self):
        return self._data
    def getvalue(self):
        return self._data


def _safe_filename_part(val, fallback="NA"):
    text = _clean_str(val, fallback)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text or fallback


def _load_zip_files(uploaded_zip):
    """Return dict filename -> bytes for PDFs/images inside ZIP."""
    files = {}
    if uploaded_zip is None:
        return files
    try:
        raw = uploaded_zip.getvalue() if hasattr(uploaded_zip, 'getvalue') else uploaded_zip.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = info.filename.split('/')[-1]
                if not base or base.startswith('.'):
                    continue
                if base.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
                    files[base] = zf.read(info.filename)
    except Exception as e:
        st.error(f"ZIP पढ़ने में दिक्कत: {e}")
    return files


def _find_files_for_gr(gr_no, file_name_hint, zip_files, allow_multiple=False):
    """Find file(s) by exact file hint or exact GR token in filename."""
    if not zip_files:
        return []
    hint = _clean_str(file_name_hint)
    if hint:
        hints = [h.strip() for h in re.split(r"[|,;]", hint) if h.strip()]
        matched = []
        for h in hints:
            for fn, data in zip_files.items():
                if fn == h or fn.lower() == h.lower():
                    matched.append((fn, data))
        if matched:
            return matched if allow_multiple else matched[:1]
    target = _norm_key(gr_no)
    if not target:
        return []
    candidates = []
    for fn, data in zip_files.items():
        stem = re.sub(r"\.[^.]+$", "", fn)
        tokens = [_norm_key(x) for x in re.split(r"[^A-Za-z0-9]+", stem)]
        if target in tokens:
            candidates.append((fn, data))
    if candidates:
        return candidates if allow_multiple else candidates[:1]
    # digit boundary fallback for GR like 176 in file names
    gr_raw = str(gr_no).replace('.0', '').strip()
    for fn, data in zip_files.items():
        stem = re.sub(r"\.[^.]+$", "", fn)
        if re.search(rf"(?<!\d){re.escape(gr_raw)}(?!\d)", stem):
            candidates.append((fn, data))
    return candidates if allow_multiple else candidates[:1]


def _build_bulk_edit_template():
    cols = [
        "GR No", "Date", "Truck No", "Destination", "Company", "Company Rate",
        "Weight", "Owner Rate", "From", "Universal Amt", "Comments",
        "Ishtyaque Profit", "GR File Name", "POD File Name"
    ]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pd.DataFrame(columns=cols).to_excel(writer, index=False, sheet_name="BulkEdit")
    return output.getvalue()


def _make_drive_url(d_id):
    if not d_id:
        return None
    return d_id if str(d_id).startswith("http") else f"https://drive.google.com/file/d/{d_id}/view"


def save_pod_link_to_ledger(trip_id, gr_no, truck_no, destination, pod_url, pages=1):
    """Save POD link in Owner_Ledger. Works with Google Sheet if available, else tries Supabase owner_ledger."""
    try:
        from database import connect_to_sheet
        db = connect_to_sheet()
        db.worksheet("Owner_Ledger").append_row([
            str(datetime.date.today()), str(trip_id), str(gr_no), str(truck_no),
            f"POD Link: {pod_url}", 0
        ], table_range="A1")
        return True
    except Exception:
        pass
    try:
        supabase.table("owner_ledger").insert({
            "date": str(datetime.date.today()),
            "trip_id": str(trip_id),
            "gr_no": str(gr_no),
            "truck_no": str(truck_no),
            "destination": str(destination),
            "description": f"POD Link: {pod_url}",
            "amount": 0
        }).execute()
        return True
    except Exception as e:
        st.warning(f"POD link ledger में save नहीं हो पाया: {e}")
        return False

def save_booking_to_db(row_data):
    try:
        data_dict = {
            "date": row_data[0],
            "from_loc": row_data[1],
            "company": row_data[2],
            "freight_truck": float(row_data[3]),
            "freight_company": float(row_data[4]),
            "weight": float(row_data[5]),
            "truck_no": row_data[6],
            "destination": row_data[7],
            "gr_number": row_data[8],
            "universal_amount": float(row_data[9]),
            "connect_person": row_data[10],
            "totalfright": float(row_data[11]),
            "truck_freight": float(row_data[12]),
            "universal_payment": float(row_data[13]),
            "trip_id": row_data[14],
            "ishtyaque": float(row_data[15])
        }
        supabase.table("bookings").insert(data_dict).execute()
        return True
    except Exception as e: 
        st.error(f"DB Error: {e}")
        return False

@st.cache_data(ttl=60)
def get_all_trips():
    try:
        response = supabase.table("bookings").select("*").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            ordered_cols = ["date", "from_loc", "company", "freight_truck", "freight_company", 
                            "weight", "truck_no", "destination", "gr_number", "universal_amount", 
                            "connect_person", "totalfright", "truck_freight", "universal_payment", 
                            "trip_id", "ishtyaque", "google_url"]
            for col in ordered_cols:
                if col not in df.columns:
                    df[col] = None
            return df[ordered_cols]
        return pd.DataFrame()
    except: return pd.DataFrame()

def update_booking_in_db(trip_id, updated_row):
    try:
        data_dict = {
            "date": updated_row[0], "from_loc": updated_row[1], "company": updated_row[2],
            "freight_truck": float(updated_row[3]), "freight_company": float(updated_row[4]),
            "weight": float(updated_row[5]), "truck_no": updated_row[6], "destination": updated_row[7],
            "gr_number": updated_row[8], "universal_amount": float(updated_row[9]),
            "connect_person": updated_row[10], "totalfright": float(updated_row[11]),
            "truck_freight": float(updated_row[12]), "universal_payment": float(updated_row[13]),
            "ishtyaque": float(updated_row[15])
        }
        supabase.table("bookings").update(data_dict).eq("trip_id", str(trip_id)).execute()
        return True
    except: return False

def save_to_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        gr = str(gr_no).strip() if str(gr_no).strip() else "N/A"
        
        supabase.table("company_ledger").insert({
            "date": str(date_val), "trip_id": str(trip_id), "gr_no": gr, 
            "truck_no": str(truck_no), "destination": str(dest), "freight": float(comp_amt)
        }).execute()
        
        supabase.table("owner_ledger").insert({
            "date": str(date_val), "trip_id": str(trip_id), "gr_no": gr, 
            "truck_no": str(truck_no), "destination": str(dest), "freight": float(owner_amt)
        }).execute()
        
        if float(uni_amt) > 0:
            supabase.table("universal_ledger").insert({
                "date": str(date_val), "trip_date": str(trip_id), "gr_no": gr, 
                "comment": "N/A", "truck_no": f"Freight: {truck_no}", "payment": -float(uni_amt)
            }).execute()
            
        if float(ish_amt) > 0:
            supabase.table("ishtyaque_ledger").insert({
                "date": str(date_val), "trip_id": str(trip_id), "gr_no": gr, 
                "comment": "N/A", "truck_no": f"Profit: {truck_no}", "amount": -float(ish_amt)
            }).execute()
            
        return True
    except Exception as e: 
        st.error(f"Ledger Insert Error: {e}")
        return False

def update_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        supabase.table("company_ledger").delete().eq("trip_id", str(trip_id)).execute()
        supabase.table("owner_ledger").delete().eq("trip_id", str(trip_id)).execute()
        supabase.table("universal_ledger").delete().eq("trip_date", str(trip_id)).execute()
        supabase.table("ishtyaque_ledger").delete().eq("trip_id", str(trip_id)).execute()
        
        save_to_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt)
        return True
    except: return False

# ==========================================
# 🎨 CSS
# ==========================================
BOOKING_CSS = """
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
        max-width: 98% !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        background: #f0f4ff !important;
        border-radius: 10px !important;
        padding: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 4px 16px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #444 !important;
    }
    .stTabs [aria-selected="true"] {
        background: #003399 !important;
        color: white !important;
    }

    /* Form container */
    div[data-testid="stForm"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important;
    }

    /* Headings */
    h2 { font-size: 1.4rem !important; margin-bottom: 2px !important; color: #111 !important; }
    h3 { font-size: 1.1rem !important; margin-bottom: 4px !important; color: #222 !important; }
    h4 { font-size: 1rem !important; margin-bottom: 4px !important; color: #003399 !important; }

    /* Spacing */
    div[data-testid="stVerticalBlock"] { gap: 0.45rem !important; }
    div[data-testid="stHorizontalBlock"] { gap: 0.55rem !important; }

    /* Inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        border-radius: 7px !important;
        border: 1px solid #cbd5e1 !important;
        padding: 4px 10px !important;
        min-height: 1.9rem !important;
        font-size: 0.88rem !important;
        background: #fafafa !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #003399 !important;
        background: #fff !important;
        box-shadow: 0 0 0 2px rgba(0,51,153,0.1) !important;
    }
    .stSelectbox > div > div {
        border-radius: 7px !important;
        border: 1px solid #cbd5e1 !important;
        min-height: 1.9rem !important;
        font-size: 0.88rem !important;
    }

    /* Labels */
    label {
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        color: #374151 !important;
        margin-bottom: 0px !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px !important;
        min-height: 1.9rem !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        padding: 2px 14px !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #003399, #0055cc) !important;
        border: none !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #002277, #0044aa) !important;
        box-shadow: 0 3px 10px rgba(0,51,153,0.3) !important;
    }

    /* Alert boxes */
    div[data-testid="stAlert"] {
        border-radius: 8px !important;
        padding: 6px 12px !important;
        margin: 2px 0 !important;
    }
    div[data-testid="stAlert"] p { font-size: 0.88rem !important; margin: 0 !important; }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #f0f4ff, #e8eeff) !important;
        border: 1px solid #c7d4f5 !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: #003399 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        color: #555 !important;
    }

    /* GR box */
    .gr-box {
        background: #f8faff;
        border: 1px solid #c7d4f5;
        border-radius: 10px;
        padding: 14px;
        height: 100%;
    }

    /* Summary bar */
    .summary-bar {
        background: linear-gradient(135deg, #003399, #0055cc);
        border-radius: 10px;
        padding: 10px 18px;
        color: white;
        font-size: 0.9rem;
        font-weight: 600;
        margin: 6px 0;
    }
    .summary-bar span { margin-right: 28px; }

    /* Confirm box */
    .confirm-box {
        background: #fffbeb;
        border: 1.5px solid #f59e0b;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }

    hr { margin: 0.4em 0 !important; border-color: #e2e8f0 !important; }

    .stFileUploader section { padding: 4px !important; }
    .stFileUploader label { display: none !important; }
    .stFileUploader small { display: none !important; }
    .stDateInput > div > div > input { border-radius: 7px !important; font-size: 0.88rem !important; }
</style>
"""

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
    tab1, tab2, tab3 = st.tabs(["🆕 नई गाड़ी (Single)", "✏️ एडिट बुकिंग", "📑 बल्क अपलोड (Excel)"])

    # ══════════════════════════════════════
    # TAB 1 — नई बुकिंग
    # ══════════════════════════════════════
    with tab1:
        if not st.session_state.show_confirm:
            with st.form(key=f"booking_form_{c}"):
                st.markdown("#### 🚛 गाड़ी की जानकारी")
                r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                with r1c1: b_date = st.date_input("📅 तारीख", datetime.date.today())
                with r1c2: truck_no = st.text_input("🚛 गाड़ी नंबर")
                with r1c3: from_loc = st.text_input("📍 कहाँ से", "Kashipur")
                with r1c4: to_loc = st.text_input("📍 कहाँ तक")

                st.markdown("#### 💰 भाड़े की जानकारी")
                r2c1, r2c2, r2c3, r2c4 = st.columns(4)
                with r2c1: company = st.selectbox("🏢 कंपनी", ["Universal Industries", "Other"])
                with r2c2: weight = st.number_input("⚖️ माल का वज़न (क्विंटल)", min_value=0, step=1)
                with r2c3: comp_rate = st.number_input("📊 कंपनी रेट (₹/क्विंटल)", min_value=0, step=1)
                with r2c4: owner_rate = st.number_input("🚛 गाड़ी वाला रेट (₹/क्विंटल)", min_value=0, step=1)

                st.markdown("#### 📋 अन्य जानकारी")
                r3c1, r3c2, r3c3, r3c4 = st.columns(4)
                with r3c1: universal_amt = st.number_input("🏭 Universal (₹)", min_value=0, value=1000, step=10)
                with r3c2: ishtyaque_amt = st.number_input("👤 Ishtyaque (₹)", min_value=0, value=0, step=100)
                with r3c3: gr_no = st.text_input("📄 GR Number (Optional)")
                with r3c4: comments = st.text_input("💬 टिप्पणी")

                comp_freight = int(weight * comp_rate) + universal_amt
                owner_freight = int(weight * owner_rate)
                tds = int(comp_freight * 0.01)
                hold_10 = int(comp_freight * 0.10)
                advance_approx = int(owner_freight * 0.90)

                st.markdown("---")
                st.markdown("#### 📊 कैलकुलेशन")
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("💵 कुल कंपनी भाड़ा", f"₹{comp_freight:,}")
                mc2.metric("🚛 गाड़ी एडवांस (90%)", f"₹{advance_approx:,}")
                mc3.metric("📋 TDS (1%)", f"₹{tds:,}")
                mc4.metric("🔒 10% रोक", f"₹{hold_10:,}")

                submitted = st.form_submit_button(
                    "➡️ सेव करने के लिए आगे बढ़ें",
                    use_container_width=True, type="primary"
                )

                if submitted:
                    if not truck_no or not to_loc:
                        st.error("⚠️ गाड़ी नंबर और कहाँ तक (Destination) भरना ज़रूरी है!")
                    else:
                        st.session_state.temp_data = {
                            "b_date": b_date, "from_loc": from_loc, "company": company,
                            "weight": weight, "comp_rate": comp_rate,
                            "universal_amt": universal_amt, "truck_no": truck_no,
                            "to_loc": to_loc, "gr_no": gr_no, "owner_rate": owner_rate,
                            "comments": comments, "ishtyaque_amt": ishtyaque_amt,
                            "comp_freight": comp_freight, "owner_freight": owner_freight
                        }
                        st.session_state.show_confirm = True
                        st.rerun()

        # Confirm box
        if st.session_state.show_confirm:
            d = st.session_state.temp_data
            st.markdown(f"""
                <div class='confirm-box'>
                    ❓ क्या आप पक्का <b>गाड़ी {d['truck_no']}</b> की बुकिंग सेव करना चाहते हैं?<br>
                    <small>
                        📍 {d['from_loc']} → {d['to_loc']} &nbsp;|&nbsp;
                        ⚖️ {d['weight']} क्विंटल &nbsp;|&nbsp;
                        💵 कंपनी भाड़ा: ₹{d['comp_freight']:,} &nbsp;|&nbsp;
                        🚛 गाड़ी भाड़ा: ₹{d['owner_freight']:,}
                    </small>
                </div>
            """, unsafe_allow_html=True)

            cb1, cb2 = st.columns([1, 4])
            if cb1.button("👍 हाँ, सेव करें", type="primary"):
                if st.session_state.bk_saving_lock:
                    st.toast("⏳ प्रोसेस हो रहा है...")
                else:
                    st.session_state.bk_saving_lock = True
                    with st.spinner("⏳ डेटा सेव हो रहा है..."):
                        trip_id = f"TRP-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
                        final_uni_amt = int(d['universal_amt'] * 0.99) if d['universal_amt'] > 0 else 0
                        row_data = [
                            str(d['b_date']), str(d['from_loc']), str(d['company']),
                            d['owner_rate'], d['comp_rate'], d['weight'],
                            str(d['truck_no']), str(d['to_loc']),
                            str(d['gr_no']) if d['gr_no'] else "N/A",
                            d['universal_amt'], str(d['comments']),
                            d['comp_freight'], d['owner_freight'],
                            final_uni_amt, trip_id, d['ishtyaque_amt']
                        ]
                        if save_booking_to_db(row_data):
                            save_to_ledgers(
                                d['b_date'], trip_id, d['gr_no'], d['truck_no'],
                                d['to_loc'], d['comp_freight'], d['owner_freight'],
                                final_uni_amt, d['ishtyaque_amt']
                            )
                            st.cache_data.clear()
                            st.success(f"✅ गाड़ी {d['truck_no']} की बुकिंग सेव हो गई!")
                            time.sleep(1.5)
                            st.session_state.bk_saving_lock = False
                            st.session_state.show_confirm = False
                            st.session_state.bk_ck += 1
                            st.rerun()
                        else:
                            st.session_state.bk_saving_lock = False
                            st.error("❌ बुकिंग सेव नहीं हो पाई।")

            if cb2.button("❌ कैंसिल करें"):
                st.session_state.show_confirm = False
                st.rerun()

    # ══════════════════════════════════════
    # TAB 2 — एडिट बुकिंग
    # ══════════════════════════════════════
    with tab2:
        df_trips = get_all_trips()
        if df_trips.empty:
            st.info("कोई पुरानी बुकिंग नहीं मिली।")
        else:
            # ─────────────────────────────────────
            # 📥 Bulk Edit / GR-POD Update inside Edit tab
            # ─────────────────────────────────────
            st.markdown("### 📥 Bulk Upload से Existing Booking Edit / GR-POD Update")
            with st.expander("📥 Excel + GR/POD ZIP से selected GR update करें", expanded=False):
                cdl, cinf = st.columns([1, 2])
                with cdl:
                    st.download_button(
                        "⬇️ Bulk Edit Template",
                        data=_build_bulk_edit_template(),
                        file_name="booking_bulk_edit_gr_pod_update_template.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                with cinf:
                    st.info("Excel में GR No जरूरी है। Blank cell छोड़ने पर existing data वैसा ही रहेगा। GR/POD ZIP optional हैं।")

                bulk_excel = st.file_uploader("1) Bulk Edit Excel/CSV upload करें", type=["xlsx", "xls", "csv"], key="booking_bulk_edit_excel")
                czip1, czip2 = st.columns(2)
                with czip1:
                    bulk_gr_zip = st.file_uploader("2) GR PDF/Image ZIP upload करें", type=["zip"], key="booking_bulk_gr_zip")
                with czip2:
                    bulk_pod_zip = st.file_uploader("3) POD PDF/Image ZIP upload करें", type=["zip"], key="booking_bulk_pod_zip")

                if bulk_excel is not None:
                    try:
                        df_bulk = (pd.read_csv(bulk_excel) if bulk_excel.name.lower().endswith('.csv') else pd.read_excel(bulk_excel))
                        gr_zip_files = _load_zip_files(bulk_gr_zip) if bulk_gr_zip is not None else {}
                        pod_zip_files = _load_zip_files(bulk_pod_zip) if bulk_pod_zip is not None else {}

                        preview_rows = []
                        for _, row in df_bulk.iterrows():
                            gr = _clean_str(row.get("GR No", ""))
                            matches = df_trips[df_trips.iloc[:, 8].apply(_norm_key) == _norm_key(gr)] if gr else pd.DataFrame()
                            status = "✅ Ready" if len(matches) == 1 else ("⚠️ Duplicate GR" if len(matches) > 1 else "❌ GR Not Found")
                            gr_match = _find_files_for_gr(gr, row.get("GR File Name", ""), gr_zip_files, allow_multiple=False)
                            pod_match = _find_files_for_gr(gr, row.get("POD File Name", ""), pod_zip_files, allow_multiple=True)
                            preview_rows.append({
                                "Status": status,
                                "GR No": gr,
                                "Matched Booking": len(matches),
                                "GR File": gr_match[0][0] if gr_match else "",
                                "POD Files": len(pod_match),
                                "Truck Excel": _clean_str(row.get("Truck No", "")),
                                "Destination Excel": _clean_str(row.get("Destination", "")),
                            })
                        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, height=220)

                        c1, c2, c3 = st.columns(3)
                        with c1:
                            update_fields = st.checkbox("Excel fields update करें", value=True)
                        with c2:
                            upload_gr_pdf = st.checkbox("GR PDF/Image save करें", value=True)
                        with c3:
                            upload_pod_pdf = st.checkbox("POD PDF/Image save करें", value=True)

                        if st.button("🚀 Ready Rows Update करें", type="primary", use_container_width=True):
                            success = skipped = gr_saved = pod_saved = failed_files = 0
                            progress = st.progress(0, text="Bulk update शुरू...")
                            total = max(len(df_bulk), 1)

                            for idx, row in df_bulk.iterrows():
                                try:
                                    gr = _clean_str(row.get("GR No", ""))
                                    matches = df_trips[df_trips.iloc[:, 8].apply(_norm_key) == _norm_key(gr)] if gr else pd.DataFrame()
                                    if len(matches) != 1:
                                        skipped += 1
                                        progress.progress((idx + 1) / total, text=f"Skipped {skipped}: GR {gr}")
                                        continue

                                    current = matches.iloc[0].copy()
                                    trip_id = str(current.iloc[14])

                                    def keep_or_new(col_name, current_val, numeric=False):
                                        val = row.get(col_name, "")
                                        if numeric:
                                            n = _clean_num(val, None)
                                            return int(n) if n is not None else int(float(current_val or 0))
                                        s = _clean_str(val, "")
                                        return s if s else _clean_str(current_val, "")

                                    final_date = keep_or_new("Date", current.iloc[0])
                                    final_from = keep_or_new("From", current.iloc[1])
                                    final_company = keep_or_new("Company", current.iloc[2])
                                    final_owner_rate = keep_or_new("Owner Rate", current.iloc[3], numeric=True)
                                    final_company_rate = keep_or_new("Company Rate", current.iloc[4], numeric=True)
                                    final_weight = keep_or_new("Weight", current.iloc[5], numeric=True)
                                    final_truck = keep_or_new("Truck No", current.iloc[6])
                                    final_dest = keep_or_new("Destination", current.iloc[7])
                                    final_gr = gr or keep_or_new("GR No", current.iloc[8])
                                    final_universal = keep_or_new("Universal Amt", current.iloc[9], numeric=True)
                                    final_comments = keep_or_new("Comments", current.iloc[10])
                                    final_ish = keep_or_new("Ishtyaque Profit", current.iloc[15], numeric=True)

                                    final_comp_freight = int(final_weight * final_company_rate) + int(final_universal)
                                    final_owner_freight = int(final_weight * final_owner_rate)
                                    final_uni_pay = int(final_universal * 0.99) if int(final_universal) > 0 else 0

                                    if update_fields:
                                        updated_row = [
                                            str(final_date), str(final_from), str(final_company),
                                            final_owner_rate, final_company_rate, final_weight,
                                            str(final_truck), str(final_dest), str(final_gr),
                                            final_universal, str(final_comments), final_comp_freight,
                                            final_owner_freight, final_uni_pay, trip_id, final_ish
                                        ]
                                        if update_booking_in_db(trip_id, updated_row):
                                            update_ledgers(final_date, trip_id, final_gr, final_truck, final_dest,
                                                           final_comp_freight, final_owner_freight, final_uni_pay, final_ish)

                                    if upload_gr_pdf and gr_zip_files:
                                        gr_files_found = _find_files_for_gr(final_gr, row.get("GR File Name", ""), gr_zip_files, allow_multiple=False)
                                        if gr_files_found:
                                            fn, data = gr_files_found[0]
                                            final_bytes, file_ext = prepare_pod_file([_BytesFile(fn, data)])
                                            if final_bytes:
                                                clean_name = f"GR_{_safe_filename_part(final_gr)}_{_safe_filename_part(final_truck)}_{_safe_filename_part(final_dest)}.pdf"
                                                d_id = upload_to_drive(final_bytes, clean_name)
                                                url = _make_drive_url(d_id)
                                                if url and save_gr_link_to_db(trip_id, url):
                                                    gr_saved += 1
                                                else:
                                                    failed_files += 1
                                        elif row.get("GR File Name", "") or gr_zip_files:
                                            failed_files += 1

                                    if upload_pod_pdf and pod_zip_files:
                                        pod_files_found = _find_files_for_gr(final_gr, row.get("POD File Name", ""), pod_zip_files, allow_multiple=True)
                                        if pod_files_found:
                                            pod_inputs = [_BytesFile(fn, data) for fn, data in pod_files_found]
                                            final_bytes, file_ext = prepare_pod_file(pod_inputs)
                                            if final_bytes:
                                                clean_name = f"POD_{_safe_filename_part(final_gr)}_{_safe_filename_part(final_truck)}_{_safe_filename_part(final_dest)}.pdf"
                                                d_id = upload_to_drive(final_bytes, clean_name)
                                                url = _make_drive_url(d_id)
                                                if url and save_pod_link_to_ledger(trip_id, final_gr, final_truck, final_dest, url, pages=len(pod_inputs)):
                                                    pod_saved += 1
                                                else:
                                                    failed_files += 1
                                        elif row.get("POD File Name", "") or pod_zip_files:
                                            failed_files += 1

                                    success += 1
                                    progress.progress((idx + 1) / total, text=f"Updated {success}, skipped {skipped}, GR {gr_saved}, POD {pod_saved}")
                                except Exception as e:
                                    skipped += 1
                                    st.warning(f"Row {idx + 2} skip: {e}")

                            st.cache_data.clear()
                            st.success(f"✅ Bulk complete: {success} row processed, {skipped} skipped, {gr_saved} GR saved, {pod_saved} POD saved, {failed_files} file issue.")
                            st.info("अगर data तुरंत न दिखे तो sidebar का Refresh Data दबाएँ, browser hard refresh न करें।")
                    except Exception as e:
                        st.error(f"Bulk file read/update error: {e}")

            df_last = df_trips.tail(50).iloc[::-1]
            labels, trip_ids = [], []
            for _, row in df_last.iterrows():
                try:
                    gr_disp = (str(row.iloc[8])
                               if pd.notna(row.iloc[8]) and str(row.iloc[8]).lower() != "nan"
                               else "N/A")
                    labels.append(
                        f"🚛 {row.iloc[6]}  |  📅 {row.iloc[0]}  |  "
                        f"📍 {row.iloc[7]}  |  GR: {gr_disp}"
                    )
                    trip_ids.append(str(row.iloc[14]))
                except: pass

            selected_label = st.selectbox(
                "✏️ एडिट करने के लिए गाड़ी चुनें:",
                ["चुनें..."] + labels
            )
            st.markdown("<hr style='margin:0.5em 0;border-color:#e2e8f0'>",
                        unsafe_allow_html=True)

            if selected_label != "चुनें...":
                idx = labels.index(selected_label)
                selected_trip_id = trip_ids[idx]
                row_data = df_last[
                    df_last.iloc[:, 14].astype(str) == selected_trip_id
                ].iloc[0]

                col_edit, col_gr = st.columns([2.2, 1], gap="small")

                # ── Edit Form ──
                with col_edit:
                    st.markdown("#### 📝 बुकिंग अपडेट फॉर्म")
                    with st.form("edit_booking_form"):
                        def s_int(val):
                            try: return int(float(val))
                            except: return 0
                        def s_str(val):
                            return str(val) if pd.notna(val) and str(val).lower() != "nan" else ""

                        current_gr = s_str(row_data.iloc[8])
                        if current_gr == "N/A": current_gr = ""

                        e1, e2, e3 = st.columns(3)
                        with e1: e_date = st.text_input("📅 तारीख", s_str(row_data.iloc[0]))
                        with e2: e_truck = st.text_input("🚛 गाड़ी नंबर", s_str(row_data.iloc[6]))
                        with e3: e_from = st.text_input("📍 कहाँ से", s_str(row_data.iloc[1]))

                        e4, e5, e6 = st.columns(3)
                        with e4: e_to = st.text_input("📍 कहाँ तक", s_str(row_data.iloc[7]))
                        with e5: e_company = st.selectbox("🏢 कंपनी",
                            ["Universal Industries", "Other"],
                            index=0 if str(row_data.iloc[2]) == "Universal Industries" else 1)
                        with e6: e_weight = st.number_input("⚖️ वज़न", value=s_int(row_data.iloc[5]), step=1)

                        e7, e8, e9 = st.columns(3)
                        with e7: e_comp_rate = st.number_input("📊 कंपनी रेट", value=s_int(row_data.iloc[4]), step=1)
                        with e8: e_owner_rate = st.number_input("🚛 गाड़ी रेट", value=s_int(row_data.iloc[3]), step=1)
                        with e9: e_uni_amt = st.number_input("🏭 Universal (₹)", value=s_int(row_data.iloc[9]), step=10)

                        e10, e11, e12 = st.columns(3)
                        with e10: e_ish_amt = st.number_input("👤 Ishtyaque (₹)", min_value=0, value=s_int(row_data.iloc[15]), step=100)
                        with e11: e_gr = st.text_input("📄 GR Number", current_gr)
                        with e12: e_comments = st.text_input("💬 टिप्पणी", s_str(row_data.iloc[10]))

                        e_comp_freight = int(e_weight * e_comp_rate) + e_uni_amt
                        e_owner_freight = int(e_weight * e_owner_rate)

                        st.markdown(f"""
                            <div class='summary-bar'>
                                <span>💵 कंपनी भाड़ा: ₹{e_comp_freight:,}</span>
                                <span>🚛 गाड़ी भाड़ा: ₹{e_owner_freight:,}</span>
                                <span>⚖️ वज़न: {e_weight} क्विंटल</span>
                            </div>
                        """, unsafe_allow_html=True)

                        if st.form_submit_button("💾 अपडेट करें",
                                                 use_container_width=True, type="primary"):
                            with st.spinner("अपडेट हो रहा है..."):
                                e_final_uni = int(e_uni_amt * 0.99) if e_uni_amt > 0 else 0
                                final_gr = str(e_gr).strip() if str(e_gr).strip() else "N/A"
                                updated_row = [
                                    str(e_date), str(e_from), str(e_company),
                                    e_owner_rate, e_comp_rate, e_weight,
                                    str(e_truck), str(e_to), final_gr,
                                    e_uni_amt, str(e_comments),
                                    e_comp_freight, e_owner_freight,
                                    e_final_uni, selected_trip_id, e_ish_amt
                                ]
                                if update_booking_in_db(selected_trip_id, updated_row):
                                    update_ledgers(
                                        e_date, selected_trip_id, final_gr, e_truck, e_to,
                                        e_comp_freight, e_owner_freight, e_final_uni, e_ish_amt
                                    )
                                    st.cache_data.clear()
                                    st.success("✅ बुकिंग सफलतापूर्वक अपडेट हो गई!")
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error("❌ अपडेट फेल हो गया।")

                # ── GR Upload ──
                with col_gr:
                    st.markdown("<div class='gr-box'>", unsafe_allow_html=True)
                    st.markdown("#### 📄 GR (बिल्टी) अपलोड")

                    if (len(row_data) > 16
                            and pd.notna(row_data.iloc[16])
                            and "http" in str(row_data.iloc[16])):
                        existing_gr_url = str(row_data.iloc[16])
                        st.markdown("""
                            <div style='background:#d1e7dd;border:1px solid #0f5132;
                            border-radius:8px;padding:6px 12px;
                            font-size:0.82rem;color:#0f5132;font-weight:bold;
                            margin-bottom:8px;'>
                            ✅ GR सुरक्षित है
                            </div>
                        """, unsafe_allow_html=True)
                        st.link_button("📥 GR कॉपी देखें", existing_gr_url,
                                       type="secondary", use_container_width=True)
                    else:
                        st.markdown("""
                            <div style='background:#fff3cd;border:1px solid #ffc107;
                            border-radius:8px;padding:6px 12px;
                            font-size:0.82rem;color:#856404;font-weight:bold;
                            margin-bottom:8px;'>
                            ⚠️ GR अभी तक अपलोड नहीं
                            </div>
                        """, unsafe_allow_html=True)

                    gr_files = st.file_uploader(
                        "GR फोटो (A4 में सेव होगी)", type=["pdf", "jpg", "jpeg", "png"],
                        accept_multiple_files=True,
                        key=f"gr_up_{selected_trip_id}",
                        label_visibility="collapsed"
                    )
                    if gr_files:
                        st.caption(f"📎 {len(gr_files)} फ़ाइल चुनी गई")

                    if st.button("🚀 GR अपलोड करें", type="primary", use_container_width=True):
                        if gr_files:
                            with st.spinner("GR (A4 PDF) Drive पर जा रही है..."):
                                final_bytes, file_ext = prepare_pod_file(gr_files)
                                if final_bytes:
                                    f_name = f"GR_{row_data.iloc[8]}_{row_data.iloc[6]}.{file_ext}"
                                    d_id = upload_to_drive(final_bytes, f_name)
                                    if d_id:
                                        gr_url = (d_id if d_id.startswith("http")
                                                  else f"https://drive.google.com/file/d/{d_id}/view")
                                        if save_gr_link_to_db(selected_trip_id, gr_url):
                                            st.cache_data.clear()
                                            st.success("✅ A4 साइज़ GR सेव हो गई!")
                                            time.sleep(1.5)
                                            st.rerun()
                                        else: st.error("❌ Link save फेल!")
                                    else: st.error("❌ Drive अपलोड फेल!")
                                else: st.error("❌ फ़ाइल process नहीं हुई।")
                        else: st.warning("⚠️ पहले फ़ाइल चुनें!")
                    st.markdown("</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════
    # TAB 3 — बल्क एक्सेल अपलोड
    # ══════════════════════════════════════
    with tab3:
        st.markdown("### 📑 Excel से बल्क बुकिंग अपलोड")

        template_cols = [
            "Date (YYYY-MM-DD)", "From", "Company", "Owner Rate", "Company Rate",
            "Weight", "Truck No", "To", "GR No", "Universal Amt",
            "Comments", "Ishtyaque Profit"
        ]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame(columns=template_cols).to_excel(
                writer, index=False, sheet_name='BulkBooking')

        col_dl, _ = st.columns([1, 2])
        with col_dl:
            st.download_button(
                label="⬇️ Excel Template डाउनलोड करें",
                data=output.getvalue(),
                file_name="Khan_Transport_Bulk_Format.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.divider()
        uploaded_excel = st.file_uploader(
            "📥 भरी हुई Excel/CSV अपलोड करें",
            type=["xlsx", "xls", "csv"]
        )

        if uploaded_excel is not None:
            try:
                df_upload = (pd.read_csv(uploaded_excel)
                             if uploaded_excel.name.endswith('.csv')
                             else pd.read_excel(uploaded_excel))

                st.markdown(f"**📋 {len(df_upload)} गाड़ियाँ मिलीं — नीचे चेक करें:**")
                st.dataframe(df_upload, use_container_width=True, height=250)

                if st.button("🚀 सभी गाड़ियाँ सेव करें",
                             type="primary", use_container_width=True):
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
                                    error_count += 1; continue

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
                                    save_to_ledgers(
                                        date_str, trip_id, gr_no, truck_no, to_loc,
                                        comp_freight, owner_freight, final_uni_amt, int(ish_amt)
                                    )
                                    success_count += 1
                                    time.sleep(0.1) 
                                else:
                                    error_count += 1

                                progress_bar.progress(
                                    (index + 1) / total,
                                    text=f"✅ {success_count} सेव | ⚠️ {error_count} skip"
                                )
                            except: error_count += 1; continue

                    st.cache_data.clear()
                    if success_count > 0:
                        st.success(f"🎊 {success_count} गाड़ियाँ सफलतापूर्वक सेव हो गईं!")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} rows skip हुईं (गाड़ी नंबर या Destination खाली था)।")

            except Exception as e:
                st.error(f"❌ Excel फाइल पढ़ने में दिक्कत: {e}")
