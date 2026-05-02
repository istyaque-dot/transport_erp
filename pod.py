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

# A4 size at 150 DPI (width x height in pixels)
A4_W, A4_H = 1240, 1754  # 210mm x 297mm @ 150dpi

# ==========================================
# 🗄️ DATABASE — Connection Unchanged
# ==========================================

@st.cache_resource(ttl=3000)
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
# 📦 CACHED DATA FETCHERS
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
# 📄 A4 PDF BUILDER
# ==========================================

def image_to_a4(img: Image.Image) -> Image.Image:
    """
    Kisi bhi size/orientation ki image ko A4 canvas par
    center mein fit karke white background par paste karta hai.
    Aspect ratio maintain rehti hai — stretch nahi hota.
    """
    if img.mode != 'RGB':
        img = img.convert('RGB')

    img_w, img_h = img.size

    # Portrait ya Landscape decide karo image ke ratio se
    if img_w > img_h:
        # Landscape image → A4 Landscape canvas
        canvas_w, canvas_h = A4_H, A4_W
    else:
        # Portrait image → A4 Portrait canvas
        canvas_w, canvas_h = A4_W, A4_H

    # Image ko canvas mein fit karne ka scale
    scale = min(canvas_w / img_w, canvas_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # White A4 canvas banao
    canvas = Image.new('RGB', (canvas_w, canvas_h), (255, 255, 255))

    # Center mein paste karo
    paste_x = (canvas_w - new_w) // 2
    paste_y = (canvas_h - new_h) // 2
    canvas.paste(img_resized, (paste_x, paste_y))

    return canvas

def build_a4_pdf(image_files) -> bytes | None:
    """
    List of uploaded files → har ek A4 page →
    sab ka ek multi-page PDF (bytes).
    PDF already ho to directly return karo.
    """
    # Single PDF file: seedha return
    if len(image_files) == 1 and image_files[0].name.lower().endswith(".pdf"):
        return image_files[0].read()

    a4_pages = []
    for file in image_files:
        if not file.name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        file.seek(0)
        img = Image.open(file)
        a4_page = image_to_a4(img)
        a4_pages.append(a4_page)

    if not a4_pages:
        return None

    pdf_bytes = io.BytesIO()
    if len(a4_pages) == 1:
        a4_pages[0].save(pdf_bytes, format="PDF",
                         resolution=150)
    else:
        a4_pages[0].save(pdf_bytes, format="PDF",
                         save_all=True,
                         append_images=a4_pages[1:],
                         resolution=150)
    return pdf_bytes.getvalue()

# ==========================================
# 📤 DRIVE UPLOAD
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

def save_pod_to_drive(db, gr_no, truck_no, trip_id, up_files):
    """
    Images → A4 PDF → Drive → Owner_Ledger mein link save.
    """
    if not up_files:
        st.warning("⚠️ पहले फ़ाइल चुनें!")
        return

    with st.spinner(f"📄 {len(up_files)} पेज की A4 PDF बन रही है..."):
        final_bytes = build_a4_pdf(up_files)

    if not final_bytes:
        st.error("❌ PDF नहीं बनी। JPG/PNG/PDF फ़ाइल चुनें।")
        return

    with st.spinner("☁️ Drive पर अपलोड हो रही है..."):
        f_name = f"POD_{gr_no}_{truck_no}.pdf"
        d_id = upload_to_drive(final_bytes, f_name)

    if d_id:
        pod_url = (d_id if d_id.startswith("http")
                   else f"https://drive.google.com/file/d/{d_id}/view")
        db.worksheet("Owner_Ledger").append_row(
            [str(datetime.date.today()), trip_id, gr_no, truck_no,
             f"POD Link: {pod_url}", 0]
        )
        st.cache_data.clear()
        st.success(f"✅ {len(up_files)} पेज की A4 PDF Drive पर सेव हो गई! 🖨️ Print-ready है।")
        time.sleep(1.5)
        st.rerun()
    else:
        st.error("❌ Drive अपलोड फेल! दोबारा कोशिश करें।")

# ==========================================
# 💾 LEDGER SAVE FUNCTIONS
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

def save_balance_to_ledgers(db, date_val, trip_id, gr_no, truck_no,
                             amount, bank_name, remark):
    try:
        db.worksheet("Owner_Ledger").append_row(
            [str(date_val), trip_id, gr_no, truck_no,
             f"Final Balance: {remark}", -int(amount)]
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
            [str(date_val), trip_id, truck_no, 0,
             f"Final Settlement ({remark})", c_amt, b_amt, bank_name, int(amount)]
        )
        return True
    except:
        return False

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
            .stNumberInput > div > div > input {
                padding: 2px !important; min-height: 1.7rem !important; font-size: 0.85rem !important;
            }
            label { font-size: 0.8rem !important; font-weight: 600 !important; margin-bottom: 0 !important; }
            div[data-testid="stAlert"] { padding: 4px 10px !important; margin: 0.1rem 0 !important; }
            div[data-testid="stAlert"] p { font-size: 0.85rem !important; margin: 0 !important; }
            div[data-testid="metric-container"] { background: transparent !important; border: none !important; padding: 0 5px !important; }
            div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
            hr { margin: 0.25em 0 !important; border-color: #ddd !important; }
            .stButton > button { min-height: 1.7rem !important; padding: 0 10px !important; font-size: 0.85rem !important; }
            .custom-box {
                background: #f8f9fa; border: 1px solid #d1d5db;
                border-radius: 6px; padding: 10px; margin-top: 0;
            }
            .balance-card-due {
                background: #fff3cd; border: 1.5px solid #ffc107;
                border-radius: 8px; padding: 8px 14px; text-align: center;
                font-size: 1.1rem; font-weight: bold; color: #856404; margin: 4px 0;
            }
            .balance-card-clear {
                background: #d1e7dd; border: 1.5px solid #0f5132;
                border-radius: 8px; padding: 8px 14px; text-align: center;
                font-size: 1.1rem; font-weight: bold; color: #0f5132; margin: 4px 0;
            }
            .balance-card-over {
                background: #f8d7da; border: 1.5px solid #dc3545;
                border-radius: 8px; padding: 8px 14px; text-align: center;
                font-size: 1.1rem; font-weight: bold; color: #842029; margin: 4px 0;
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

    col_s1, col_s2 = st.columns([1, 2.5])
    with col_s1:
        search_gr = st.text_input("🔍 GR नंबर से खोजें:")

    df_show = df_pending[
        df_pending.iloc[:, 2].astype(str).str.contains(
            search_gr.strip(), case=False, na=False)
    ] if search_gr else df_pending

    choices = [
        f"GR: {r.iloc[2]} | 🚛 {r.iloc[3]} | 📍 {r.iloc[4]} | ID: {r.iloc[1]}"
        for _, r in df_show.iterrows()
    ]

    if "pod_selected" not in st.session_state:
        st.session_state.pod_selected = "चुनें..."

    with col_s2:
        all_choices = ["चुनें..."] + choices
        saved = st.session_state.pod_selected
        default_idx = all_choices.index(saved) if saved in all_choices else 0
        selected = st.selectbox(
            "📝 गाड़ी चुनें", all_choices,
            index=default_idx, label_visibility="collapsed"
        )
    st.session_state.pod_selected = selected
    st.markdown("<hr>", unsafe_allow_html=True)

    if selected == "चुनें...":
        st.info("👆 ऊपर से गाड़ी चुनें।")
        return

    parts    = selected.split(" | ")
    gr_no    = parts[0].replace("GR: ", "")
    truck_no = parts[1].replace("🚛 ", "")
    trip_id  = parts[3].replace("ID: ", "")

    trip_bk, total_adv, already_adj, existing_pod_url = get_trip_summary(trip_id)

    if not trip_bk:
        st.error("❌ Booking डेटा नहीं मिला। Sheet चेक करें।")
        return

    weight        = float(trip_bk['weight'])
    owner_freight = int(trip_bk['truck freight'])

    # ── Live Passbook ──
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
            st.markdown(
                f"<div class='balance-card-due'>💰 बाकी देना<br>₹{current_bal:,}</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='balance-card-clear'>✅ हिसाब क्लियर<br>₹{current_bal:,}</div>",
                unsafe_allow_html=True)

    if existing_pod_url:
        st.markdown("<span class='pod-badge'>📄 POD सेव है</span>", unsafe_allow_html=True)
        st.link_button("📥 सेव की गई बिल्टी देखें", existing_pod_url, type="secondary")

    st.markdown("<hr>", unsafe_allow_html=True)
    db = connect_to_sheet()

    # ==========================================
    # CASE A: हिसाब पूरा
    # ==========================================
    if current_bal <= 0:
        st.success(f"✅ हिसाब पूरा! बैलेंस: ₹{current_bal:,}")
        if not existing_pod_url:
            st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
            st.markdown("#### 📄 बिल्टी (POD) अपलोड करें")
            st.caption("🖨️ हर फोटो A4 size के अलग PDF page पर save होगी")
            up_files = st.file_uploader(
                "फोटो/PDF चुनें (एक या ज़्यादा)",
                type=["pdf", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="pod_only"
            )
            if up_files:
                st.info(f"📎 {len(up_files)} फ़ाइल चुनी गई — हर एक A4 page बनेगी")
                if st.button("🚀 A4 PDF बनाएं और Drive पर सेव करें",
                             type="primary", key="save_a", use_container_width=True):
                    save_pod_to_drive(db, gr_no, truck_no, trip_id, up_files)
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # ==========================================
    # CASE B: बाकी बैलेंस है
    # ==========================================
    st.warning(f"💰 अभी का बाकी बैलेंस: **₹{current_bal:,}**")

    col_pod, col_pay = st.columns([1, 1.4], gap="small")

    # ── Left: POD Upload ──
    with col_pod:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 📄 1. बिल्टी (POD) अपलोड")
        if existing_pod_url:
            st.markdown(
                "<span class='pod-badge'>✅ पहले से अपलोड है</span>",
                unsafe_allow_html=True)
        st.caption("🖨️ हर फोटो A4 size के अलग PDF page पर save होगी")
        up_files = st.file_uploader(
            "फोटो/PDF (एक या ज़्यादा)",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="pod_sep"
        )
        if up_files:
            st.info(f"📎 {len(up_files)} फ़ाइल चुनी गई")
            if st.button("🚀 A4 PDF बनाएं और सेव करें",
                         use_container_width=True, key="save_b"):
                save_pod_to_drive(db, gr_no, truck_no, trip_id, up_files)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Right: Final Payment ──
    with col_pay:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 💳 2. फाइनल पेमेंट (Settlement)")

        r1, r2 = st.columns(2)
        with r1: shortage  = st.number_input("Shortage/कटी (−₹)", min_value=0, step=50)
        with r2: extra_pay = st.number_input("Detention/Extra (+₹)", min_value=0, step=100)

        r3, r4 = st.columns(2)
        with r3: adj_remark = st.text_input("कारण (Remarks)", value="Final Settlement")
        with r4: pay_mode   = st.selectbox("बैंक/कैश",
                                            ["N/A", "Cash", "canara bank 311",
                                             "canara bank 41", "bob"])

        final_payable = current_bal - shortage + extra_pay

        if final_payable > 0:
            st.markdown(
                f"<div class='balance-card-due'>💵 हाथ में देना: ₹{final_payable:,}</div>",
                unsafe_allow_html=True)
        elif final_payable == 0:
            st.markdown(
                "<div class='balance-card-clear'>✅ रकम बिल्कुल बराबर!</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='balance-card-over'>⚠️ ओवरपेमेंट: ₹{abs(final_payable):,}</div>",
                unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✅ फुल एंड फाइनल करें", type="primary",
                     use_container_width=True, key="final_settle"):
            if pay_mode == "N/A" and final_payable > 0:
                st.error("⚠️ बैंक या Cash ज़रूर चुनें!")
            else:
                with st.spinner("हिसाब क्लोज हो रहा है..."):
                    t_date = str(datetime.date.today())
                    if shortage > 0:
                        save_company_pod_status(
                            t_date, trip_id, gr_no, truck_no, shortage)
                        db.worksheet("Owner_Ledger").append_row(
                            [t_date, trip_id, gr_no, truck_no,
                             f"Shortage: {adj_remark}", -int(shortage)])
                    if extra_pay > 0:
                        db.worksheet("Owner_Ledger").append_row(
                            [t_date, trip_id, gr_no, truck_no,
                             f"Extra/Detention: {adj_remark}", int(extra_pay)])
                    ok = True
                    if final_payable > 0:
                        ok = save_balance_to_ledgers(
                            db, t_date, trip_id, gr_no, truck_no,
                            final_payable, pay_mode, adj_remark)
                    if ok:
                        st.cache_data.clear()
                        st.success(f"🎊 हिसाब बराबर! ₹{final_payable:,} सेटलमेंट हो गया।")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ सेव नहीं हुआ! दोबारा कोशिश करें।")

        st.markdown("</div>", unsafe_allow_html=True). 
