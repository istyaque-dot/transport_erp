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
from streamlit_cropper import st_cropper

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

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
# 📤 DRIVE UPLOAD FUNCTIONS
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

def _save_pod_to_drive(db, gr_no, truck_no, trip_id, final_bytes, file_ext):
    f_name = f"POD_{gr_no}_{truck_no}.{file_ext}"
    d_id = upload_to_drive(final_bytes, f_name)
    if d_id:
        pod_url = d_id if d_id.startswith("http") else f"https://drive.google.com/file/d/{d_id}/view"
        db.worksheet("Owner_Ledger").append_row(
            [str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0]
        )
        st.cache_data.clear()
        st.success("✅ बिल्टी (POD) सुरक्षित Drive पर सेव हो गई!")
        time.sleep(1.5)
        st.rerun()
    else:
        st.error("❌ Drive अपलोड फेल! दोबारा कोशिश करें।")

# ==========================================
# ✂️ MULTI-PAGE CROP UI — CORE FUNCTION
# ==========================================

def show_pod_crop_and_upload(db, gr_no, truck_no, trip_id, up_files, key_prefix="pod"):
    """
    - Unlimited images upload kar sakte hain
    - Har image ke liye alag crop box
    - Ek page se doosre par navigate karo (tabs)
    - Crop ki gayi sab images → ek PDF → Drive
    - Skip crop button bhi hai
    """
    if not up_files:
        st.warning("⚠️ पहले फ़ाइल चुनें!")
        return

    # ── PDF: seedha Drive par ──
    if len(up_files) == 1 and up_files[0].name.lower().endswith(".pdf"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 PDF Drive पर सेव करें",
                         type="primary", use_container_width=True,
                         key=f"{key_prefix}_pdf_save"):
                with st.spinner("PDF Drive पर जा रही है..."):
                    _save_pod_to_drive(db, gr_no, truck_no, trip_id,
                                       up_files[0].read(), "pdf")
        return

    # ── Image files filter ──
    image_files = [f for f in up_files
                   if f.name.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not image_files:
        st.error("❌ कोई valid image नहीं मिली (JPG/PNG चाहिए)।")
        return

    total_pages = len(image_files)

    # ── Session State init ──
    ss_images_key  = f"{key_prefix}_orig_images"
    ss_crops_key   = f"{key_prefix}_cropped_images"
    ss_page_key    = f"{key_prefix}_current_page"
    ss_done_key    = f"{key_prefix}_crop_done"

    # Images ko ek baar load karke session mein rakh do
    if ss_images_key not in st.session_state:
        loaded = []
        for f in image_files:
            f.seek(0)
            img = Image.open(f)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Performance: 1400px se bada ho to resize
            if img.width > 1400:
                ratio = 1400 / img.width
                img = img.resize(
                    (1400, int(img.height * ratio)), Image.LANCZOS
                )
            loaded.append(img)
        st.session_state[ss_images_key] = loaded

    if ss_crops_key not in st.session_state:
        # Pehle original hi rakh do default mein
        st.session_state[ss_crops_key] = {
            i: st.session_state[ss_images_key][i].copy()
            for i in range(total_pages)
        }

    if ss_page_key not in st.session_state:
        st.session_state[ss_page_key] = 0

    if ss_done_key not in st.session_state:
        st.session_state[ss_done_key] = {i: False for i in range(total_pages)}

    orig_images = st.session_state[ss_images_key]
    current_page = st.session_state[ss_page_key]

    # ── Header + Progress ──
    st.markdown("#### ✂️ बिल्टी Crop करें")

    done_count = sum(st.session_state[ss_done_key].values())
    st.progress(done_count / total_pages,
                text=f"✅ {done_count}/{total_pages} पेज crop हो गए")

    # ── Page Tabs (ज़्यादा हो तो tabs, कम हो तो direct) ──
    if total_pages <= 6:
        tab_labels = [
            f"{'✅' if st.session_state[ss_done_key][i] else '📄'} पेज {i+1}"
            for i in range(total_pages)
        ]
        tabs = st.tabs(tab_labels)
        for i, tab in enumerate(tabs):
            with tab:
                _render_single_crop(
                    orig_images[i], i, key_prefix,
                    ss_crops_key, ss_done_key, image_files[i].name
                )
    else:
        # ज़्यादा pages के लिए: navigation arrows
        col_prev, col_info, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("◀ पिछला", key=f"{key_prefix}_prev",
                         disabled=(current_page == 0)):
                st.session_state[ss_page_key] -= 1
                st.rerun()
        with col_info:
            st.markdown(
                f"<div style='text-align:center;font-weight:bold;padding-top:6px;'>"
                f"पेज {current_page+1} / {total_pages}</div>",
                unsafe_allow_html=True
            )
        with col_next:
            if st.button("अगला ▶", key=f"{key_prefix}_next",
                         disabled=(current_page == total_pages - 1)):
                st.session_state[ss_page_key] += 1
                st.rerun()

        _render_single_crop(
            orig_images[current_page], current_page, key_prefix,
            ss_crops_key, ss_done_key, image_files[current_page].name
        )

    st.markdown("<hr style='margin:8px 0;border-color:#eee'>", unsafe_allow_html=True)

    # ── Final Action Buttons ──
    col_save, col_skip, col_reset = st.columns([2, 2, 1])

    with col_save:
        save_label = (
            f"🚀 सभी {total_pages} पेज की PDF Drive पर सेव करें"
            if done_count == total_pages
            else f"🚀 PDF सेव करें ({done_count}/{total_pages} cropped)"
        )
        if st.button(save_label, type="primary",
                     use_container_width=True, key=f"{key_prefix}_final_save"):
            _build_and_save_pdf(
                db, gr_no, truck_no, trip_id,
                st.session_state[ss_crops_key], total_pages, key_prefix
            )

    with col_skip:
        if st.button("⏭️ Crop किए बिना Original सेव करें",
                     use_container_width=True, key=f"{key_prefix}_skip"):
            with st.spinner("Original images से PDF बन रही है..."):
                _build_and_save_pdf(
                    db, gr_no, truck_no, trip_id,
                    {i: orig_images[i] for i in range(total_pages)},
                    total_pages, key_prefix
                )

    with col_reset:
        if st.button("🔄 Reset", use_container_width=True,
                     key=f"{key_prefix}_reset"):
            for k in [ss_images_key, ss_crops_key, ss_page_key, ss_done_key]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()


def _render_single_crop(img, page_idx, key_prefix,
                         ss_crops_key, ss_done_key, file_name):
    """Ek page ka crop UI render karta hai"""
    is_done = st.session_state[ss_done_key][page_idx]

    col_crop, col_prev = st.columns([2, 1], gap="small")

    with col_crop:
        if is_done:
            st.markdown(
                "<span style='background:#d1e7dd;border-radius:12px;"
                "padding:2px 10px;font-size:0.8rem;color:#0f5132;"
                "font-weight:bold'>✅ Crop हो गई</span>",
                unsafe_allow_html=True
            )
            st.image(
                st.session_state[ss_crops_key][page_idx],
                caption=f"Cropped: {file_name}",
                use_container_width=True
            )
            if st.button(f"✏️ दोबारा Crop करें",
                         key=f"{key_prefix}_reedit_{page_idx}"):
                st.session_state[ss_done_key][page_idx] = False
                st.rerun()
        else:
            st.caption(f"📄 {file_name} — नीली border खींचकर हिस्सा चुनें")
            cropped = st_cropper(
                img,
                realtime_update=True,
                box_color="#0055FF",
                aspect_ratio=None,
                key=f"{key_prefix}_cropper_{page_idx}"
            )
            if cropped:
                st.session_state[ss_crops_key][page_idx] = cropped

            if st.button(f"✅ यह Crop ठीक है — अगला पेज",
                         type="primary",
                         use_container_width=True,
                         key=f"{key_prefix}_confirm_{page_idx}"):
                st.session_state[ss_done_key][page_idx] = True
                st.rerun()

    with col_prev:
        st.markdown("**👁️ Preview**")
        preview_img = (st.session_state[ss_crops_key][page_idx]
                       if is_done else cropped if not is_done and 'cropped' in dir() and cropped
                       else img)
        st.image(preview_img, use_container_width=True)
        if preview_img:
            st.caption(f"{preview_img.width}×{preview_img.height}px")


def _build_and_save_pdf(db, gr_no, truck_no, trip_id,
                         crops_dict, total_pages, key_prefix):
    """Cropped images dictionary se PDF banao aur Drive par save karo"""
    with st.spinner(f"📄 {total_pages} पेज की PDF बन रही है..."):
        images_list = [crops_dict[i] for i in range(total_pages)
                       if crops_dict.get(i) is not None]
        if not images_list:
            st.error("❌ कोई image नहीं मिली।")
            return
        pdf_bytes = io.BytesIO()
        if len(images_list) == 1:
            images_list[0].save(pdf_bytes, format="PDF")
        else:
            images_list[0].save(
                pdf_bytes, format="PDF",
                save_all=True,
                append_images=images_list[1:]
            )
        # Session cleanup
        for k in [f"{key_prefix}_orig_images", f"{key_prefix}_cropped_images",
                  f"{key_prefix}_current_page", f"{key_prefix}_crop_done"]:
            if k in st.session_state:
                del st.session_state[k]

        _save_pod_to_drive(db, gr_no, truck_no, trip_id,
                           pdf_bytes.getvalue(), "pdf")

# ==========================================
# 💾 SAVE FUNCTIONS
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
                padding: 2px !important;
                min-height: 1.7rem !important;
                font-size: 0.85rem !important;
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

    parts    = selected.split(" | ")
    gr_no    = parts[0].replace("GR: ", "")
    truck_no = parts[1].replace("🚛 ", "")
    trip_id  = parts[3].replace("ID: ", "")

    trip_bk, total_adv, already_adj, existing_pod_url = get_trip_summary(trip_id)

    if not trip_bk:
        st.error("❌ Booking डेटा नहीं मिला। Sheet चेक करें।")
        return

    weight        = float(trip_bk['weight'])
    owner_freight = int(trip_bk['truck freight'])

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

    # ── CASE A: हिसाब पूरा ──
    if current_bal <= 0:
        st.success(f"✅ हिसाब पूरा! बैलेंस: ₹{current_bal:,}")
        if not existing_pod_url:
            st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
            st.markdown("#### 📄 बिल्टी (POD) अपलोड करें")
            up_files = st.file_uploader(
                "पेज चुनें (एक या ज़्यादा फोटो / PDF)",
                type=["pdf", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="pod_only"
            )
            if up_files:
                show_pod_crop_and_upload(
                    db, gr_no, truck_no, trip_id, up_files, key_prefix="case_a"
                )
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── CASE B: बाकी बैलेंस है ──
    st.warning(f"💰 अभी का बाकी बैलेंस: **₹{current_bal:,}**")

    col_pod, col_pay = st.columns([1, 1.4], gap="small")

    with col_pod:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 📄 1. बिल्टी (POD) अपलोड")
        if existing_pod_url:
            st.markdown(
                "<span class='pod-badge'>✅ पहले से अपलोड है</span>",
                unsafe_allow_html=True)
        up_files = st.file_uploader(
            "फोटो/PDF (एक या ज़्यादा)",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="pod_sep"
        )
        if up_files:
            show_pod_crop_and_upload(
                db, gr_no, truck_no, trip_id, up_files, key_prefix="case_b"
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_pay:
        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
        st.markdown("#### 💳 2. फाइनल पेमेंट (Settlement)")

        r1, r2 = st.columns(2)
        with r1: shortage  = st.number_input("Shortage/कटी (−₹)", min_value=0, step=50)
        with r2: extra_pay = st.number_input("Detention/Extra (+₹)", min_value=0, step=100)

        r3, r4 = st.columns(2)
        with r3: adj_remark = st.text_input("कारण (Remarks)", value="Final Settlement")
        with r4: pay_mode   = st.selectbox("बैंक/कैश",
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

        st.markdown("</div>", unsafe_allow_html=True)
