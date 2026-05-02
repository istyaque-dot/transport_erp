import streamlit as st
import datetime
import time
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
import requests        
import base64          
from PIL import Image 
import io              

# ==========================================
# ⚠️ Google Apps Script Web App URL
# ==========================================
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

# ==========================================
# 🗄️ DATABASE FUNCTIONS
# ==========================================

@st.cache_resource(ttl=86400)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    client = gspread.authorize(creds)
    sheet = client.open("Khan_Transport_ERP")
    return sheet

def upload_to_drive(file_bytes, file_name):
    if file_name.lower().endswith(".pdf"): mime_type = "application/pdf"
    elif file_name.lower().endswith(".png"): mime_type = "image/png"
    else: mime_type = "image/jpeg"
        
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    payload = {"fileName": file_name, "mimeType": mime_type, "fileData": b64_data}
    
    try:
        res = requests.post(WEB_APP_URL, data=payload)
        result = res.text.strip()
        if "Error" not in result: return result
        else: return None
    except: return None

def prepare_pod_file(uploaded_files):
    if not uploaded_files: return None, None
    if len(uploaded_files) == 1 and uploaded_files[0].name.lower().endswith(".pdf"):
        return uploaded_files[0].read(), "pdf"
    
    images = []
    for file in uploaded_files:
        if file.name.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(file)
            if img.mode != 'RGB': img = img.convert('RGB')
            images.append(img)
    
    if images:
        pdf_bytes = io.BytesIO()
        if len(images) == 1: images[0].save(pdf_bytes, format="PDF")
        else: images[0].save(pdf_bytes, format="PDF", save_all=True, append_images=images[1:])
        return pdf_bytes.getvalue(), "pdf"
    return None, None

def save_company_pod_status(date_val, trip_id, gr_no, truck_no, shortage_amt):
    try:
        db = connect_to_sheet()
        db.worksheet("Company_PODs").append_row([str(date_val), trip_id, gr_no, truck_no, "Submitted", int(shortage_amt)])
        return True
    except: return False

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
        total_adv = sum([int(float(str(r[8]).replace(',', ''))) for r in adv_data[1:] if len(r) > 8 and str(r[1]).strip() == trip_id])
        
        df_owner_raw = db.worksheet("Owner_Ledger").get_all_values()
        df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])
        already_adj = 0
        existing_pod_url = None 
        if not df_owner.empty and len(df_owner.columns) > 5:
            adj_rows = df_owner[df_owner.iloc[:, 1] == trip_id]
            for _, r in adj_rows.iterrows():
                desc = str(r.iloc[4])
                if "Shortage" in desc or "Extra" in desc or "Detention" in desc:
                    try: already_adj += int(float(str(r.iloc[5]).replace(',', '')))
                    except: pass
                elif "POD Link:" in desc:
                    existing_pod_url = desc.replace("POD Link:", "").strip()
        return trip_bk, total_adv, already_adj, existing_pod_url
    except Exception as e: 
        return None, 0, 0, None

def save_balance_to_ledgers(db, date_val, trip_id, gr_no, truck_no, amount, bank_name, remark):
    try:
        db.worksheet("Owner_Ledger").append_row([str(date_val), trip_id, gr_no, truck_no, f"Final Balance: {remark}", -int(amount)])
        base = [str(date_val), trip_id, gr_no, f"Final Pay: {truck_no}"]
        s_name = {"Cash": "Cash_Ledger", "canara bank 311": "Canara_311_Ledger", "canara bank 41": "Canara_41_Ledger", "bob": "BOB_Ledger"}.get(bank_name)
        if s_name:
            db.worksheet(s_name).append_row(base + [-int(amount)], table_range="A1")
        c_amt = amount if bank_name == "Cash" else 0
        b_amt = amount if bank_name != "Cash" else 0
        db.worksheet("Advances").append_row([str(date_val), trip_id, truck_no, 0, f"Final Settlement ({remark})", c_amt, b_amt, bank_name, int(amount)])
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================
def show_pod_page():
    # 🟢 PERFECTLY BALANCED CSS FOR 11-INCH MAC
    st.markdown("""
        <style>
            /* ऊपर थोड़ी जगह बढ़ा दी, ताकि हेडिंग न चिपके */
            .block-container { padding-top: 1.35rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
            h2 { font-size: 1.35rem !important; margin-bottom: 0 !important; padding-bottom: 0 !important; }
            h3 { font-size: 1.05rem !important; margin-top: 2px !important; margin-bottom: 0px !important; padding-bottom: 0px !important;}
            h4 { font-size: 0.95rem !important; margin-top: 0px !important; margin-bottom: 4px !important; color: #003399; }
            
            /* बीच का गैप हल्का सा (Minor) कम किया */
            div[data-testid="stVerticalBlock"] { gap: 0.4rem !important; } 
            div[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
            
            /* इनपुट फील्ड्स स्लिम हैं */
            .stTextInput > div > div > input, 
            .stNumberInput > div > div > input, 
            .stSelectbox > div > div > select { 
                padding-top: 2px !important; padding-bottom: 2px !important; min-height: 1.8rem !important; font-size: 0.85rem !important;
            }
            
            label { font-size: 0.8rem !important; font-weight: 600 !important; margin-bottom: 0px !important; padding-bottom: 0px !important; }
            
            /* अलर्ट बॉक्स (पीला वाला) के ऊपर-नीचे का गैप सेट किया */
            div[data-testid="stAlert"] { padding: 4px 10px !important; min-height: 30px !important; margin-top: 0.2rem !important; margin-bottom: 0.2rem !important;}
            div[data-testid="stAlert"] p { font-size: 0.85rem !important; margin: 0px !important; }
            
            /* पासबुक के डब्बे */
            div[data-testid="metric-container"] {
                background-color: transparent !important; border: none !important; box-shadow: none !important; padding: 0px 5px !important; margin-bottom: 0px !important;
            }
            div[data-testid="stMetricValue"] { font-size: 1.1rem !important; }
            div[data-testid="stMetricLabel"] { font-weight: bold !important; color: #333 !important;}
            
            /* लाइनों का मार्जिन सेट किया */
            hr { margin: 0.4em 0px !important; border-color: #ddd !important; }
            .stButton > button { min-height: 1.8rem !important; padding: 2px 10px !important; font-size: 0.9rem !important;}
            
            /* कस्टम बॉक्स की पैडिंग थोड़ी बढ़ा दी ताकि भरा-भरा लगे */
            .custom-box {
                background-color: #f8f9fa; border: 1px solid #d1d5db; border-radius: 6px; padding: 12px; height: 100%; margin-top: 0px;
            }
            
            /* फाइल अपलोडर से फालतू टेक्स्ट हटाया */
            .stFileUploader section { padding: 6px !important; min-height: auto !important; }
            .stFileUploader label { display: none !important; }
            .stFileUploader small { display: none !important; } 
        </style>
    """, unsafe_allow_html=True)

    st.header("🏁 POD और फाइनल हिसाब (Settlement)")
    db = connect_to_sheet()
    df_owner_raw = db.worksheet("Owner_Ledger").get_all_values()
    
    if len(df_owner_raw) > 1:
        df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])
        df_pending = df_owner[~df_owner.iloc[:, 4].astype(str).str.contains("Shortage|Extra|Detention|Final|POD Link", case=False, na=False)].iloc[::-1]
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # 🟢 स्मार्ट GR सर्च
        col_s1, col_s2 = st.columns([1, 2.5])
        with col_s1:
            search_gr = st.text_input("🔍 GR नंबर से खोजें:")
            
        if search_gr:
            df_show = df_pending[df_pending.iloc[:, 2].astype(str).str.contains(search_gr.strip(), case=False, na=False)]
        else:
            df_show = df_pending
            
        choices = [f"GR: {r.iloc[2]} | 🚛 {r.iloc[3]} | 📍 {r.iloc[4]} | ID: {r.iloc[1]}" for _, r in df_show.iterrows()]
        
        with col_s2:
            selected = st.selectbox("📝 नीचे लिस्ट से गाड़ी चुनें", ["चुनें..."] + choices, label_visibility="collapsed")
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        if selected != "चुनें...":
            parts = selected.split(" | ")
            gr_no = parts[0].replace("GR: ", "")
            truck_no = parts[1].replace("🚛 ", "")
            trip_id = parts[3].replace("ID: ", "")
            
            trip_bk, total_adv, already_adj, existing_pod_url = get_trip_summary(trip_id)
            
            if trip_bk:
                weight = float(trip_bk['weight'])
                owner_freight = int(trip_bk['truck freight'])
                
                st.markdown("### 📊 लाइव पासबुक")
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("कुल भाड़ा", f"₹{owner_freight:,}")
                with c2: st.metric("एडवांस दे चुके", f"₹{total_adv:,}")
                with c3:
                    default_munshi = int(weight * 1)
                    munshiyana = st.number_input("✍️ मुंशीयाना", min_value=0, value=default_munshi, step=50)
                
                current_bal = (owner_freight - munshiyana - total_adv) + already_adj
                
                with c4:
                    if current_bal > 0:
                        st.metric("बैलेंस (देना है)", f"₹{current_bal:,}", "बाकी", delta_color="inverse")
                    else:
                        st.metric("बैलेंस", f"₹{current_bal:,}", "क्लियर ✅", delta_color="normal")
                
                if existing_pod_url:
                    st.success("📄 इस गाड़ी की बिल्टी (POD) सिस्टम में सेव है।")
                    st.link_button("📥 सेव की गई बिल्टी (POD) देखें", existing_pod_url, type="secondary")
                
                st.markdown("<hr>", unsafe_allow_html=True)

                if current_bal <= 0:
                    st.success(f"✅ हिसाब पूरा हो चुका है! (बैलेंस: ₹{current_bal:,})")
                    st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
                    st.markdown("#### 📄 नई बिल्टी (POD) अपलोड")
                    up_files = st.file_uploader("बिल्टी के पेज चुनें", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True, key="pod_only_upload")
                    if st.button("🚀 सिर्फ POD अपलोड करें", type="primary"):
                        if up_files:
                            with st.spinner("बिल्टी सेव हो रही है..."):
                                final_bytes, file_ext = prepare_pod_file(up_files)
                                if final_bytes:
                                    f_name = f"POD_{gr_no}_{truck_no}.{file_ext}"
                                    d_id = upload_to_drive(final_bytes, f_name)
                                    if d_id:
                                        pod_url = d_id if "http" in d_id else f"https://drive.google.com/file/d/{d_id}/view"
                                        db.worksheet("Owner_Ledger").append_row([str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0])
                                        st.cache_data.clear()
                                        st.success("✅ PDF सुरक्षित सेव हो गई!")
                                        time.sleep(2); st.rerun()
                                    else: st.error("❌ अपलोड फेल हो गया!")
                                else: st.error("❌ प्रोसेस दिक्कत।")
                        else: st.error("⚠️ फोटो चुनें!")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                else:
                    st.warning(f"💰 **अभी का बाकी बैलेंस: ₹{current_bal:,}**")
                    
                    # 🟢 SIDE-BY-SIDE LAYOUT
                    col_pod, col_pay = st.columns([1, 1.4], gap="small")
                    
                    # --- PART 1: सिर्फ POD अपलोड (Left Box) ---
                    with col_pod:
                        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
                        st.markdown("#### 📄 1. बिल्टी (POD) अपलोड")
                        up_files = st.file_uploader("बिल्टी की फोटो", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True, key="pod_upload_separate")
                        if st.button("🚀 सिर्फ बिल्टी सेव करें", use_container_width=True):
                            if up_files:
                                with st.spinner("Drive पर सेव हो रही है..."):
                                    final_bytes, file_ext = prepare_pod_file(up_files)
                                    if final_bytes:
                                        f_name = f"POD_{gr_no}_{truck_no}.{file_ext}"
                                        d_id = upload_to_drive(final_bytes, f_name)
                                        if d_id:
                                            pod_url = d_id if "http" in d_id else f"https://drive.google.com/file/d/{d_id}/view"
                                            db.worksheet("Owner_Ledger").append_row([str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0])
                                            st.cache_data.clear()
                                            st.success("✅ सुरक्षित सेव हो गई!")
                                            time.sleep(2); st.rerun()
                                        else: st.error("❌ अपलोड फेल!")
                                    else: st.error("❌ प्रोसेस दिक्कत।")
                            else: st.error("⚠️ पहले फोटो चुनें!")
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # --- PART 2: फाइनल पेमेंट (Right Box) ---
                    with col_pay:
                        st.markdown("<div class='custom-box'>", unsafe_allow_html=True)
                        st.markdown("#### 💳 2. फाइनल पेमेंट (Settlement)")
                        
                        r1, r2 = st.columns(2)
                        with r1: shortage = st.number_input("Shortage/कटी (- ₹)", min_value=0, step=50)
                        with r2: extra_pay = st.number_input("Detention/Extra (+ ₹)", min_value=0, step=100)
                        
                        r3, r4 = st.columns(2)
                        with r3: adj_remark = st.text_input("कारण (Remarks)", value="Final Settlement")
                        with r4: pay_mode = st.selectbox("पेमेंट बैंक/कैश?", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])
                        
                        final_payable = current_bal - shortage + extra_pay
                        st.error(f"💵 **अब हाथ में देने वाली रकम: ₹{final_payable:,}**")
                        
                        if st.button("✅ फुल एंड फाइनल पेमेंट करें", type="primary", use_container_width=True):
                            if pay_mode == "N/A" and final_payable > 0:
                                st.error("⚠️ कृपया बैंक या Cash चुनें!")
                            else:
                                with st.spinner("हिसाब क्लोज हो रहा है..."):
                                    t_date = str(datetime.date.today())
                                    if shortage > 0:
                                        save_company_pod_status(t_date, trip_id, gr_no, truck_no, shortage)
                                        db.worksheet("Owner_Ledger").append_row([t_date, trip_id, gr_no, truck_no, f"Shortage: {adj_remark}", -int(shortage)])
                                    if extra_pay > 0:
                                        db.worksheet("Owner_Ledger").append_row([t_date, trip_id, gr_no, truck_no, f"Extra/Detention: {adj_remark}", int(extra_pay)])
                                    if final_payable > 0:
                                        save_balance_to_ledgers(db, t_date, trip_id, gr_no, truck_no, final_payable, pay_mode, adj_remark)
                                    st.cache_data.clear()
                                    st.success(f"🎊 हिसाब बराबर! ₹{final_payable:,} का सेटलमेंट हो गया।")
                                    time.sleep(2); st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
    else: st.info("कोई डेटा नहीं मिला।")
