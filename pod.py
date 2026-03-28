import json
import streamlit as st
import datetime
import time
import pandas as pd
import requests
import base64
from oauth2client.service_account import ServiceAccountCredentials
import gspread
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
    return client.open("Khan_Transport_ERP")

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
        bk_data = db.worksheet("Bookings").get_all_records()
        trip_bk = [r for r in bk_data if str(r['trip number']) == trip_id][0]
        adv_data = db.worksheet("Advances").get_all_values()
        total_adv = sum([int(float(str(r[8]).replace(',', ''))) for r in adv_data[1:] if str(r[1]).strip() == trip_id])
        df_owner = pd.DataFrame(db.worksheet("Owner_Ledger").get_all_values())
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
    except: return None, 0, 0, None

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
# 🖥️ USER INTERFACE (यह वह फंक्शन है जो मिसिंग था)
# ==========================================
def show_pod_page():
    st.header("🏁 POD और फाइनल हिसाब (Settlement)")
    db = connect_to_sheet()
    df_owner_raw = db.worksheet("Owner_Ledger").get_all_values()
    df_owner = pd.DataFrame(df_owner_raw[1:], columns=df_owner_raw[0])
    
    if not df_owner.empty:
        df_clean = df_owner[~df_owner.iloc[:, 4].str.contains("Shortage|Extra|Detention|Final|POD Link", case=False, na=False)].tail(50).iloc[::-1]
        choices = [f"GR: {r.iloc[2]} | 🚛 {r.iloc[3]} | 📍 {r.iloc[4]} | ID: {r.iloc[1]}" for _, r in df_clean.iterrows()]
        
        selected = st.selectbox("🔍 गाड़ी चुनें जिसका हिसाब फाइनल करना है या POD अपलोड करनी है", ["चुनें..."] + choices)
        
        if selected != "चुनें...":
            parts = selected.split(" | ")
            gr_no = parts[0].replace("GR: ", "")
            truck_no = parts[1].replace("🚛 ", "")
            trip_id = parts[3].replace("ID: ", "")
            
            trip_bk, total_adv, already_adj, existing_pod_url = get_trip_summary(trip_id)
            
            if trip_bk:
                weight = float(trip_bk['weight'])
                owner_freight = int(trip_bk['truck freight'])
                
                st.subheader("📊 लाइव पासबुक")
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("कुल भाड़ा", f"₹{owner_freight:,}")
                with c2: st.metric("एडवांस दे चुके", f"₹{total_adv:,}")
                with c3:
                    default_munshi = int(weight * 1)
                    munshiyana = st.number_input("✍️ मुंशीयाना (Edit करें)", min_value=0, value=default_munshi, step=50)
                
                current_bal = (owner_freight - munshiyana - total_adv) + already_adj
                
                if existing_pod_url:
                    st.success("📄 इस गाड़ी की बिल्टी (POD) सिस्टम में सेव है।")
                    st.link_button("📥 सेव की गई बिल्टी (POD) यहाँ से देखें / डाउनलोड करें", existing_pod_url, type="secondary")
                st.divider()

                if current_bal <= 0:
                    st.success(f"✅ इस गाड़ी का फुल एंड फाइनल हिसाब हो चुका है! (बैलेंस: ₹{current_bal:,})")
                    st.info(f"कुल भाड़ा (मुंशीयाना हटाकर): ₹{owner_freight - munshiyana:,} | कुल पेमेंट (एडवांस + फाइनल): ₹{total_adv:,}")
                    st.subheader("📄 नई बिल्टी (POD) अपलोड")
                    st.write("अगर बिल्टी में कई पन्ने (Pages) हैं, तो एक साथ सारी फोटो सेलेक्ट करें। सिस्टम खुद उसकी एक PDF बना देगा!")
                    up_files = st.file_uploader("बिल्टी के पेज (फोटो) चुनें", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True, key="pod_only_upload")
                    if st.button("🚀 सिर्फ POD अपलोड करें", type="primary"):
                        if up_files:
                            with st.spinner("बिल्टी की PDF बन रही है और Drive पर सेव हो रही है..."):
                                final_bytes, file_ext = prepare_pod_file(up_files)
                                if final_bytes:
                                    f_name = f"POD_{gr_no}_{truck_no}.{file_ext}"
                                    d_id = upload_to_drive(final_bytes, f_name)
                                    if d_id:
                                        pod_url = f"https://drive.google.com/file/d/{d_id}/view"
                                        db.worksheet("Owner_Ledger").append_row([str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0])
                                        st.cache_data.clear()
                                        st.success("✅ सारी फोटो जुड़कर एक PDF बन गई और सुरक्षित सेव हो गई!")
                                        time.sleep(2); st.rerun()
                                    else: st.error("❌ अपलोड फेल हो गया!")
                                else: st.error("❌ फोटो को प्रोसेस करने में दिक्कत आई।")
                        else: st.error("⚠️ कृपया पहले बिल्टी की फोटो चुनें!")
                else:
                    st.warning(f"💰 **अभी का बाकी बैलेंस: ₹{current_bal:,}**")
                    
                    # --- PART 1: सिर्फ POD अपलोड ---
                    st.subheader("📄 1. बिल्टी (POD) अपलोड करें")
                    st.write("अगर आपको सिर्फ बिल्टी सेव करनी है (पेमेंट बाद में करेंगे), तो यहाँ से करें:")
                    up_files = st.file_uploader("बिल्टी के पेज (फोटो) चुनें", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True, key="pod_upload_separate")
                    if st.button("🚀 सिर्फ बिल्टी (POD) सेव करें"):
                        if up_files:
                            with st.spinner("बिल्टी की PDF बन रही है और Drive पर सेव हो रही है..."):
                                final_bytes, file_ext = prepare_pod_file(up_files)
                                if final_bytes:
                                    f_name = f"POD_{gr_no}_{truck_no}.{file_ext}"
                                    d_id = upload_to_drive(final_bytes, f_name)
                                    if d_id:
                                        pod_url = f"https://drive.google.com/file/d/{d_id}/view"
                                        db.worksheet("Owner_Ledger").append_row([str(datetime.date.today()), trip_id, gr_no, truck_no, f"POD Link: {pod_url}", 0])
                                        st.cache_data.clear()
                                        st.success("✅ बिल्टी (POD) सुरक्षित सेव हो गई!")
                                        time.sleep(2); st.rerun()
                                    else: st.error("❌ अपलोड फेल हो गया!")
                                else: st.error("❌ फोटो को प्रोसेस करने में दिक्कत आई।")
                        else: st.error("⚠️ कृपया पहले बिल्टी की फोटो चुनें!")
                    
                    st.divider()
                    
                    # --- PART 2: सिर्फ पेमेंट/हिसाब ---
                    st.subheader("💳 2. फाइनल पेमेंट और हिसाब (Settlement)")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("शॉर्टेज/कटी डालें:")
                        shortage = st.number_input("Shortage / कटी (- ₹)", min_value=0, step=50)
                        extra_pay = st.number_input("Detention / Extra KM (+ ₹)", min_value=0, step=100)
                        adj_remark = st.text_input("कारण (Remarks / Comments)", value="Final Settlement")
                        final_payable = current_bal - shortage + extra_pay
                        st.error(f"💵 **अब हाथ में देने वाली फाइनल रकम: ₹{final_payable:,}**")
                    with col2:
                        st.write("पेमेंट फाइनल करें:")
                        pay_mode = st.selectbox("कहाँ से पेमेंट किया?", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])
                        if st.button("✅ फुल एंड फाइनल पेमेंट करें", type="primary"):
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
    else: st.info("कोई डेटा नहीं मिला।")
