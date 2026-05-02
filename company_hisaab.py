import streamlit as st
import datetime
import time
import pandas as pd
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

# ==========================================
# 🗄️ DATABASE QUERIES (Supabase)
# ==========================================

@st.cache_data(ttl=15)
def get_company_balance(trip_id):
    """सिर्फ इस ट्रिप का लेजर बैलेंस निकालना"""
    try:
        res = supabase.table("company_ledger").select("amount").eq("trip_id", trip_id).execute()
        return sum(item['amount'] for item in res.data) if res.data else 0
    except: return 0

def save_company_settlement(date_val, trip_id, gr_no, truck_no, pay_rec, bank, shortage, tds, extra, remarks):
    try:
        entries = []
        # 1. TDS Entry
        if tds > 0:
            entries.append({"date_val": date_val, "trip_id": trip_id, "gr_no": gr_no, "truck_no": truck_no, "description": f"TDS: {remarks}", "amount": -int(tds)})
        # 2. Shortage Entry
        if shortage > 0:
            entries.append({"date_val": date_val, "trip_id": trip_id, "gr_no": gr_no, "truck_no": truck_no, "description": f"Shortage: {remarks}", "amount": -int(shortage)})
        # 3. Extra/Detention Entry
        if extra > 0:
            entries.append({"date_val": date_val, "trip_id": trip_id, "gr_no": gr_no, "truck_no": truck_no, "description": f"Extra: {remarks}", "amount": int(extra)})
        # 4. Cash/Bank Payment Received
        if pay_rec > 0:
            entries.append({"date_val": date_val, "trip_id": trip_id, "gr_no": gr_no, "truck_no": truck_no, "description": f"Payment: {bank} | {remarks}", "amount": -int(pay_rec)})
            # बैंक लेजर अपडेट करें
            bank_entry = {"bank_name": bank, "date_val": date_val, "trip_id": trip_id, "gr_no": gr_no, "description": f"From Company | {truck_no}", "amount": int(pay_rec)}
            supabase.table("bank_ledgers").insert(bank_entry).execute()

        if entries:
            supabase.table("company_ledger").insert(entries).execute()
        return True
    except: return False

@st.cache_data(ttl=15)
def get_all_trips_v2():
    try:
        res = supabase.table("bookings").select("*").order("created_at", desc=True).limit(100).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

# ==========================================
# 🖥️ MAIN PAGE UI
# ==========================================
def show_company_page():
    st.header("🏢 कंपनी खाता और सेटलमेंट (V2)")
    
    df = get_all_trips_v2()
    if df.empty:
        st.info("कोई बुकिंग नहीं मिली।"); return

    # Trip Selector
    df['label'] = "🚛 " + df['truck_no'] + " | 🏢 " + df['company'] + " | GR: " + df['gr_no'].astype(str)
    selected = st.selectbox("गाड़ी चुनें:", ["चुनें..."] + df['label'].tolist())

    if selected == "चुनें...": return

    row = df[df['label'] == selected].iloc[0]
    trip_id = row['trip_id']
    balance = get_company_balance(trip_id)

    # UI Display
    st.success(f"💰 इस गाड़ी का वर्तमान बकाया: ₹{balance:,}") if balance > 0 else st.info("✅ हिसाब बराबर है।")

    # Settlement Form
    with st.form("settlement_form"):
        st.subheader("💳 पेमेंट और कटौती की जानकारी")
        c1, c2, c3 = st.columns(3)
        with c1: pay_rec = st.number_input("💵 बैंक में आया (₹)", min_value=0)
        with c2: bank = st.selectbox("🏦 बैंक", ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747"])
        with c3: tds = st.number_input("✂️ TDS (₹)", value=int(row['comp_freight']*0.01))

        c4, c5, c6 = st.columns(3)
        with c4: shortage = st.number_input("📉 शॉर्टेज (₹)", min_value=0)
        with c5: extra = st.number_input("📈 Extra/Detention (₹)", min_value=0)
        with c6: remarks = st.text_input("📝 रिमार्क / UTR")

        if st.form_submit_button("✅ सेटलमेंट सेव करें", use_container_width=True, type="primary"):
            with st.spinner("⏳ अपडेट हो रहा है..."):
                if save_company_settlement(str(datetime.date.today()), trip_id, row['gr_no'], row['truck_no'], pay_rec, bank, shortage, tds, extra, remarks):
                    st.success("🎉 कंपनी खाता अपडेट हो गया!")
                    st.balloons()
                    time.sleep(1.5)
                    st.rerun()
