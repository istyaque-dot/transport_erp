import streamlit as st
import datetime
import time
import pandas as pd
import base64
import requests
from PIL import Image
import io
from supabase import create_client, Client

# ==========================================
# 🚀 SUPABASE CONFIG
# ==========================================
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# Drive Upload URL (Unchanged)
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx2zpk3_Zl_7sdjNP8eZxehjt5B7TfxjPYVNxYqzGSCYjU-k55DLaWgG1E0UISE9vjE/exec"

# ==========================================
# 🗄️ DATABASE QUERIES (Supabase)
# ==========================================

@st.cache_data(ttl=15)
def get_trip_details_v2(trip_id):
    try:
        # 1. Booking Data
        bk = supabase.table("bookings").select("*").eq("trip_id", trip_id).single().execute()
        # 2. Total Advance
        adv = supabase.table("advances").select("amount").eq("trip_id", trip_id).execute()
        total_adv = sum(a['amount'] for a in adv.data) if adv.data else 0
        # 3. Ledger Adjustments (Shortage/Extra etc)
        ledg = supabase.table("owner_ledger").select("amount, description").eq("trip_id", trip_id).execute()
        adj = sum(l['amount'] for l in ledg.data if any(k in l['description'] for k in ["Shortage", "Extra", "Detention"])) if ledg.data else 0
        
        return bk.data, total_adv, adj
    except: return None, 0, 0

def save_final_settlement(data):
    try:
        # 1. Owner Ledger में एंट्री
        supabase.table("owner_ledger").insert({
            "date_val": data['date'], "trip_id": data['trip_id'], "gr_no": data['gr_no'],
            "truck_no": data['truck_no'], "description": f"Final Balance: {data['remark']}",
            "amount": -int(data['amount'])
        }).execute()

        # 2. Bank Ledger में एंट्री
        supabase.table("bank_ledgers").insert({
            "bank_name": data['bank'], "date_val": data['date'], "trip_id": data['trip_id'],
            "gr_no": data['gr_no'], "description": f"Final Pay to {data['truck_no']}",
            "amount": -int(data['amount'])
        }).execute()

        # 3. Advances Table में रिकॉर्ड (हिसाब की स्पष्टता के लिए)
        supabase.table("advances").insert({
            "date_val": data['date'], "trip_id": data['trip_id'], "truck_no": data['truck_no'],
            "bank_name": data['bank'], "description": f"Settlement: {data['remark']}", "amount": int(data['amount'])
        }).execute()

        return True
    except: return False

# ==========================================
# 📄 A4 PDF & DRIVE LOGIC (No changes in logic)
# ==========================================
def build_a4_pdf(image_files):
    a4_pages = []
    for file in image_files:
        if file.name.lower().endswith(".pdf"): return file.read()
        img = Image.open(file).convert('RGB')
        # A4 size at 150 DPI
        canvas = Image.new('RGB', (1240, 1754), (255, 255, 255))
        img.thumbnail((1240, 1754), Image.LANCZOS)
        canvas.paste(img, ((1240 - img.width)//2, (1754 - img.height)//2))
        a4_pages.append(canvas)
    pdf_bytes = io.BytesIO()
    a4_pages[0].save(pdf_bytes, format="PDF", save_all=True, append_images=a4_pages[1:])
    return pdf_bytes.getvalue()

def upload_to_drive(file_bytes, file_name):
    b64 = base64.b64encode(file_bytes).decode('utf-8')
    payload = {"fileName": file_name, "mimeType": "application/pdf", "fileData": b64}
    try:
        res = requests.post(WEB_APP_URL, data=payload)
        return res.text.strip()
    except: return None

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================
def show_pod_page():
    st.header("🏁 POD और फाइनल हिसाब (V2)")

    # Fetch Pending Trips
    try:
        res = supabase.table("bookings").select("trip_id, truck_no, gr_no, date_val").order("created_at", desc=True).limit(50).execute()
        choices = [f"GR: {r['gr_no']} | 🚛 {r['truck_no']} | 📅 {r['date_val']} | ID: {r['trip_id']}" for r in res.data]
    except: choices = []

    selected = st.selectbox("गाड़ी चुनें:", ["चुनें..."] + choices)
    if selected == "चुनें...": return

    trip_id = selected.split("ID: ")[1]
    bk_data, total_adv, already_adj = get_trip_details_v2(trip_id)

    if not bk_data: return

    # Calculations
    weight = float(bk_data['weight'])
    owner_fr = int(bk_data['owner_freight'])
    munshiyana = st.number_input("✍️ मुंशीयाना", value=int(weight))
    
    current_bal = (owner_fr - munshiyana - total_adv) + already_adj

    # UI Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("कुल भाड़ा", f"₹{owner_fr:,}")
    m2.metric("एडवांस दिया", f"₹{total_adv:,}")
    m3.metric("बाकी बैलेंस", f"₹{current_bal:,}", delta_color="inverse")

    st.divider()

    # Layout for Upload and Settlement
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📄 1. POD अपलोड")
        up_files = st.file_uploader("फोटो चुनें", type=["jpg","png","pdf"], accept_multiple_files=True)
        if st.button("🚀 Drive पर सेव करें", type="primary") and up_files:
            with st.spinner("PDF बन रही है..."):
                pdf = build_a4_pdf(up_files)
                d_id = upload_to_drive(pdf, f"POD_{bk_data['gr_no']}_{bk_data['truck_no']}.pdf")
                if d_id:
                    url = d_id if d_id.startswith("http") else f"https://drive.google.com/file/d/{d_id}/view"
                    supabase.table("owner_ledger").insert({"date_val": str(datetime.date.today()), "trip_id": trip_id, "truck_no": bk_data['truck_no'], "description": f"POD Link: {url}", "amount": 0}).execute()
                    st.success("✅ POD सेव हो गया!")
                    st.rerun()

    with col2:
        st.subheader("💳 2. फाइनल पेमेंट")
        shortage = st.number_input("शॉर्टेज (−₹)", min_value=0)
        extra = st.number_input("एक्स्ट्रा (+₹)", min_value=0)
        bank = st.selectbox("बैंक/कैश", ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747"])
        final_amt = current_bal - shortage + extra
        
        st.info(f"💵 नेट पेमेंट: ₹{final_amt:,}")

        if st.button("✅ हिसाब क्लोज करें", use_container_width=True):
            with st.spinner("प्रोसेस हो रहा है..."):
                t_date = str(datetime.date.today())
                if shortage > 0:
                    supabase.table("owner_ledger").insert({"date_val": t_date, "trip_id": trip_id, "truck_no": bk_data['truck_no'], "description": "Shortage", "amount": -int(shortage)}).execute()
                    supabase.table("company_pods").insert({"date_val": t_date, "trip_id": trip_id, "gr_no": bk_data['gr_no'], "truck_no": bk_data['truck_no'], "status": "Submitted", "shortage": int(shortage)}).execute()
                
                if extra > 0:
                    supabase.table("owner_ledger").insert({"date_val": t_date, "trip_id": trip_id, "truck_no": bk_data['truck_no'], "description": "Extra Pay", "amount": int(extra)}).execute()

                if save_final_settlement({'date': t_date, 'trip_id': trip_id, 'gr_no': bk_data['gr_no'], 'truck_no': bk_data['truck_no'], 'amount': final_amt, 'bank': bank, 'remark': "Final Settlement"}):
                    st.success("🎊 हिसाब पूरा हुआ!")
                    time.sleep(1)
                    st.rerun()
