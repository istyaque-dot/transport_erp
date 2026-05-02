import streamlit as st
import datetime
import time
import pandas as pd
import gspread
import base64
from oauth2client.service_account import ServiceAccountCredentials
import requests
from PIL import Image
import io

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

# ==========================================
# 🗄️ DATABASE — Connection unchanged
# ==========================================

@st.cache_resource(ttl=3000)  # 50 min — token expire se pehle refresh
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Khan_Transport_ERP")

# ==========================================
# 📦 CACHED DATA FETCHERS (NEW)
# ==========================================

@st.cache_data(ttl=300)
def get_owner_ledger_data():
    db = connect_to_sheet()
    return db.worksheet("Owner_Ledger").get_all_values()

@st.cache_data(ttl=300)
def get_trip_summary(trip_id):
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
        total_adv = sum(
            int(float(str(r[8]).replace(',', '')))
            for r in adv_data[1:]
            if len(r) > 8 and str(r[1]).strip() == trip_id
        )

        df_owner_raw = get_owner_ledger_data()
        df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])

        already_adj = 0
        existing_pod_url = None

        if not df_owner.empty and len(df_owner.columns) > 5:
            adj_rows = df_owner[df_owner.iloc[:, 1] == trip_id]
            for _, r in adj_rows.iterrows():
                desc = str(r.iloc[4])
                if any(k in desc for k in ["Shortage", "Extra", "Detention"]):
                    try:
                        already_adj += int(float(str(r.iloc[5]).replace(',', '') or 0))
                    except:
                        pass
                elif "POD Link:" in desc:
                    existing_pod_url = desc.replace("POD Link:", "").strip()

        return trip_bk, total_adv, already_adj, existing_pod_url
    except Exception as e:
        st.error(f"डेटा लोड एरर: {e}")
        return None, 0, 0, None

# ==========================================
# 📤 FILE UPLOAD FUNCTIONS — Unchanged
# ==========================================

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
        res = requests.post(WEB_APP_URL, data=payload)
        result = res.text.strip()
        return result if "Error" not in result else None
    except:
        return None

def prepare_pod_file(uploaded_files):
    if not uploaded_files:
        return None, None
    if len(uploaded_files) == 1 and uploaded_files[0].name.lower().endswith(".pdf"):
        return uploaded_files[0].read(), "pdf"

    images = []
    for file in uploaded_files:
        if file.name.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

    if images:
        pdf_bytes = io.BytesIO()
        if len(images) == 1:
            images[0].save(pdf_bytes, format="PDF")
        else:
            images[0].save(pdf_bytes, format="PDF", save_all=True, append_images=images[1:])
        return pdf_bytes.getvalue(), "pdf"
    return None, None

# ==========================================
# 💾 SAVE FUNCTIONS — Unchanged logic
# ==========================================

def save_company_pod_status(date_val, trip_id, gr_no, truck_no, shortage_amt):
    try:
        db = connect_to_sheet()
        db.worksheet("Company_PODs").append_row(
            [str(date_val), trip_id, gr_no, truck_no, "Submitted", int(shortage_amt)]
        )
        return True
    except:
        return False

def save_balance_to_ledgers(db, date_val, trip_id, gr_no, truck_no, amount, bank_name, remark):
    try:
        db.worksheet("Owner_Ledger").append_row(
            [str(date_val), trip_id, gr_no, truck_no, f"Final Balance: {remark}", -int(amount)]
        )
        base = [str(date_val), trip_id, gr_no, f"Final Pay: {truck_no}"]
        sheet_map = {
            "Cash": "Cash_Ledger",
            "canara bank 311": "Canara_311_Ledger",
            "canara bank 41": "Canara_41_Ledger",
            "bob": "BOB_Ledger"
        }
        s_name = sheet_map.get(bank_name)
        if s_name:
            db.worksheet(s_name).append_row(base + [-int(amount)])
        c_amt = amount if bank_name == "Cash" else 0
        b_amt = amount if bank_name != "Cash" else 0
        db.worksheet("Advances").append_row(
            [str(date_val), trip_id, truck_no, 0, f"Final Settlement ({remark})", c_amt, b_amt, bank_name, int(amount)]
        )
        return True
    except:
        return False

def upload_pod_and_save(db, gr_no, truck_no, trip_id, up_files):
    """Reusable POD upload + ledger save"""
    final_bytes, file_ext = prepare_pod_file(up_files)
    if not final_bytes:
        st.error("❌ फ़ाइल प्रोसेस नहीं हुई।")
        return
    f_name = f"POD_{gr_no}_{truck_no}.{file_ext}"
    with st.spinner("📤 Drive पर अपलोड हो रही है..."):
        d_id = upload_to_drive(final_bytes, f_name)
    if d_id:
        pod_url = d_id if d_id.startswith("http") else f"https://drive.google.com/file/d/{d_id}/view"
        db.worksheet("Owner_Ledger").append_row(
            [str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0]
        )
        st.cache_data.clear()
        st.success("✅ बिल्टी (POD) सुरक्षित सेव हो गई!")
        time.sleep(1.5)
        st.rerun()
    else:
        st.error("❌ अपलोड फेल! Drive कनेक्शन चेक करें।")

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_pod_page():
    st.markdown("""
        <style>
            .block-container {
                padding-top: 3.5rem !important;
                padding-bottom: 0.5rem !important;
                max-width: 98% !important;
            }
            h2 { font-size: 1.3rem !important; margin-bottom: 0 !important; }
            h3 { font-size: 1.05rem !important; margin-top: 2px !important; margin-bottom: 0 !important; }
            h4 { font-size: 0.95rem !important; margin-top: 0 !important; margin-bottom: 4px !important; color: #003399; }
            div[data-testid="stVerticalBlock"] { gap: 0.15rem !important; }
            div[data-testid="stHorizontalBlock"] { gap: 0.35rem !important; }
            .stTextInput > div > div > input,
            .stNumberInput > div > div > input { padding: 2px !important; min-height: 1.7rem !important; font-size: 0.85rem !important; }
            label { font-size: 0.8rem !important; font-weight: 600 !important; margin-bottom: 0 !important; }
            div[data-testid="stAlert"] { padding: 4px 10px !important; margin: 0.1rem 0 !important; }
            div[data-testid="stAlert"] p { font-size: 0.85rem !important; margin: 0 !important; }
            div[data-testid="metric-container"] { background: transparent !important; border: none !important; padding: 0 5px !important; }
            div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
            hr { margin: 0.25em 0 !important; border-color: #ddd !important; }
            .stButton > button { min-height: 1.7rem !important; padding: 0 10px !important; font-size: 0.85rem !important; }
            .custom-box {
                background: #f8f9fa; border: 1px solid #d1d5db;
                border-radius: 6px; padding: 10px; height: 100%; margin-top: 0;
            }
            .balance-card-due {
                background: #fff3cd; border: 1.5px solid #ffc107;
                border-radius: 8px; padding: 8px 14px; text-align: center;
                font-size: 1.1rem; font-weight: bold; color: #856404;
            }
            .balance-card-clear {
                background: #d1e7dd; border: 1.5px solid #0f5132;
                border-radius: 8px; padding: 8px 14px; text-align: center;
                font-size: 1.1rem; font-weight: bold; color: #0f5132;
            }
            .pod-badge {
                background: #d1e7dd; border: 1px solid #0f5132;
                border-radius: 20px; padding: 2px 12px;
                font-size: 0.78rem; color: #0f5132; font-weight: bold;
                display: inline-block; margin-bottom: 4px;
            }
            .stFileUploader section { padding: 4px !important; min-height: auto !important; }
            .stFileUploader label { display: none !important; }
            .stFileUploader small { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🏁 POD और फाइनल हिसाब (Settlement)")

    # ---- Data Load ----
    df_owner_raw = get_owner_ledger_data()
    if len(df_owner_raw) <= 1:
        st.info("कोई डेटा नहीं मिला।")
        return

    df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])
    EXCLUDE = r"Shortage:|Extra/Detention:|Final Balance:|Final Pay:|POD Link:"
    df_pending = df_owner[
        ~df_owner.iloc[:, 4].astype(str).str.contains(EXCLUDE, case=False, na=False)
    ].iloc[::-1]

    st.markdown("<hr>", unsafe_allow_html=True)

    # ---- Search + Select ----
    col_s1, col_s2 = st.columns([1, 2.5])
    with col_s1:
        search_gr = st.text_input("🔍 GR नंबर से खोजें:")

    df_show = df_pending[
        df_pending.iloc[:, 2].astype(str).str.contains(search_gr.strip(), case=False, na=False)
    ] if search_gr else df_pending

    choices = [
        f"GR: {r.iloc[2]} | 🚛 {r.iloc[3]} | 📍 {r.iloc[4]} | ID: {r.iloc[1]}"
        for _, r in df_show.iterrows()
    ]

    # Session state: last selected trip yaad rahe
    if "pod_selected" not in st.session_state:
        st.session_state.pod_selected = "चुनें..."

    with col_s2:
        selected = st.selectbox(
            "📝 गाड़ी चुनें",
            ["चुनें..."] + choices,
            index=(["चुनें..."] + choices).index(st.session_state.pod_selected)
            if st.session_state.pod_selected in ["चुनें..."] + choices else 0,
            label_visibility="collapsed"
        )
    st.session_state.pod_selected = selected
    st.markdown("<hr>", unsafe_allow_html=True)

    if selected == "चुनें...":
        st.info("👆 ऊपर से गाड़ी चुनें।")
        return

    # ---- Parse selected ----
    parts = selected.split(" | ")
    gr_no   = parts[0].replace("GR: ", "")
    truck_no = parts[1].replace("🚛 ", "")
    trip_id  = parts[3].replace("ID: ", "")

    trip_bk, total_adv, already_adj, existing_pod_url = get_trip_summary(trip_id)

    if not trip_bk:
        st.error("❌ Booking डेटा नहीं मिला। Sheet चेक करें।")
        return

    weight       = float(trip_bk['weight'])
    owner_freight = int(trip_bk['truck freight'])

    # ---- Live Passbook ----
    st.markdown("### 📊 लाइव पासबुक")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("कुल भाड़ा", f"₹{owner_freight:,}")
    with c2: st.metric("एडवांस दे चुके", f"₹{total_adv:,}")
    with c3:
        munshiyana = st.number_input("✍️ मुंशीयाना", min_value=0,
                                     value=int(weight * 1), step=50)
    current_bal = (owner_freight - munshiyana - total_adv) + already_adj
    with c4:
        if current_bal > 0:
            st.markdown(f"<div class='balance-card-due'>💰 बाकी देना<br>₹{current_bal:,}</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='balance-card-clear'>✅ हिसाब क्लियर<br>₹{current_bal:,}</div>",
                        unsafe_allow_html=True)

    # ---- POD Status ----
    if existing_pod_url:
        st.markdown(
            f"<span class='pod-badge'>📄 POD सेव है</span>", unsafe_allow_html=True
        )
        st.link_button("📥 सेव की गई बिल्टी देखें", existing_pod_url, type="secondary")

    st.markdown("<hr>", unsafe_allow_html=True)
    db = connect_to_sheet()

    # ==========================================
    # CASE A: हिसाब पूरा हो चुका है
    # ==========================================
    if current_bal <= 0:
        st.success(f"✅ हिसाब पूरा! बैलेंस: ₹{current_bal:,}")
        if not existing_pod_url:
            with st.container():
                st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
                st.markdown("#### 📄 बिल्टी (POD) अपलोड करें")
                up_files = st.file_uploader("पेज चुनें", type=["pdf","jpg","jpeg","png"],
                                            accept_multiple_files=True, key="pod_only")
                if st.button("🚀 POD सेव करें", type="primary"):
                    if up_files:
                        upload_pod_and_save(db, gr_no, truck_no, trip_id, up_files)
                    else:
                        st.warning("⚠️ पहले फ़ाइल चुनें!")
                st.markdown("</div>", unsafe_allow_html=True)
        return

    # ==========================================
    # CASE B: बाकी बैलेंस है
    # ==========================================
    st.warning(f"💰 अभी का बाकी बैलेंस: **₹{current_bal:,}**")

    col_pod, col_pay = st.columns([1, 1.4], gap="small")

    # --- Left: POD Upload ---
    with col_pod:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 📄 1. बिल्टी (POD) अपलोड")
        if existing_pod_url:
            st.markdown("<span class='pod-badge'>✅ पहले से अपलोड है</span>", unsafe_allow_html=True)
        up_files = st.file_uploader("बिल्टी की फोटो/PDF", type=["pdf","jpg","jpeg","png"],
                                    accept_multiple_files=True, key="pod_sep")
        if st.button("🚀 बिल्टी सेव करें", use_container_width=True):
            if up_files:
                upload_pod_and_save(db, gr_no, truck_no, trip_id, up_files)
            else:
                st.warning("⚠️ पहले फ़ाइल चुनें!")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Right: Final Payment ---
    with col_pay:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 💳 2. फाइनल पेमेंट (Settlement)")

        r1, r2 = st.columns(2)
        with r1: shortage  = st.number_input("Shortage/कटी (−₹)", min_value=0, step=50)
        with r2: extra_pay = st.number_input("Detention/Extra (+₹)", min_value=0, step=100)

        r3, r4 = st.columns(2)
        with r3: adj_remark = st.text_input("कारण (Remarks)", value="Final Settlement")
        with r4: pay_mode   = st.selectbox("बैंक/कैश", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])

        final_payable = current_bal - shortage + extra_pay

        # Color-coded final amount
        if final_payable > 0:
            st.markdown(
                f"<div class='balance-card-due'>💵 हाथ में देना: ₹{final_payable:,}</div>",
                unsafe_allow_html=True
            )
        elif final_payable == 0:
            st.markdown(
                "<div class='balance-card-clear'>✅ रकम बिल्कुल बराबर है!</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='background:#f8d7da;border:1.5px solid #dc3545;border-radius:8px;"
                f"padding:8px 14px;text-align:center;font-weight:bold;color:#842029;'>"
                f"⚠️ ओवरपेमेंट: ₹{abs(final_payable):,}</div>",
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✅ फुल एंड फाइनल करें", type="primary", use_container_width=True):
            if pay_mode == "N/A" and final_payable > 0:
                st.error("⚠️ बैंक या Cash ज़रूर चुनें!")
            else:
                with st.spinner("हिसाब क्लोज हो रहा है..."):
                    t_date = str(datetime.date.today())
                    ok = True
                    if shortage > 0:
                        save_company_pod_status(t_date, trip_id, gr_no, truck_no, shortage)
                        db.worksheet("Owner_Ledger").append_row(
                            [t_date, trip_id, gr_no, truck_no, f"Shortage: {adj_remark}", -int(shortage)]
                        )
                    if extra_pay > 0:
                        db.worksheet("Owner_Ledger").append_row(
                            [t_date, trip_id, gr_no, truck_no, f"Extra/Detention: {adj_remark}", int(extra_pay)]
                        )
                    if final_payable > 0:
                        ok = save_balance_to_ledgers(db, t_date, trip_id, gr_no, truck_no,
                                                     final_payable, pay_mode, adj_remark)
                    if ok:
                        st.cache_data.clear()
                        st.success(f"🎊 हिसाब बराबर! ₹{final_payable:,} सेटलमेंट हो गया।")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ सेव नहीं हुआ! दोबारा कोशिश करें।")

        st.markdown("</div>", unsafe_allow_html=True)
