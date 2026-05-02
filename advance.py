import streamlit as st
import datetime
import time
import pandas as pd
from supabase import create_client, Client

# ==========================================
# 🚀 SUPABASE CONFIG (V2)
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

def save_advance_to_supabase(date_val, trip_id, truck_no, mode, remarks, amount):
    try:
        # 1. Advances टेबल में डेटा डालना
        adv_entry = {
            "date_val": str(date_val), "trip_id": str(trip_id), "truck_no": str(truck_no),
            "bank_name": str(mode), "description": str(remarks), "amount": int(amount),
            "zero_col": 0
        }
        supabase.table("advances").insert(adv_entry).execute()

        # 2. Owner Ledger में एंट्री (ताकि गाड़ी के बैलेंस में दिखे)
        owner_ledger_entry = {
            "date_val": str(date_val), "trip_id": str(trip_id), "gr_no": "N/A",
            "truck_no": str(truck_no), "description": f"Advance: {mode} | {remarks}",
            "amount": -int(amount) # पेमेंट है इसलिए माइनस
        }
        supabase.table("owner_ledger").insert(owner_ledger_entry).execute()

        # 3. Bank Ledger में एंट्री
        bank_entry = {
            "bank_name": str(mode), "date_val": str(date_val), "trip_id": str(trip_id),
            "gr_no": "N/A", "description": f"Advance to {truck_no} | {remarks}",
            "amount": -int(amount)
        }
        supabase.table("bank_ledgers").insert(bank_entry).execute()

        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

@st.cache_data(ttl=15)
def get_bookings_from_supabase():
    try:
        res = supabase.table("bookings").select("*").order("created_at", desc=True).limit(50).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

# ==========================================
# 🎨 CSS (Compact & Fast)
# ==========================================
ADVANCE_CSS = """
<style>
.block-container { padding-top: 0.8rem !important; max-width: 98% !important; }
h2 { font-size: 1.2rem !important; color: #111 !important; }
[data-testid="stForm"] { background: #ffffff !important; border: 1px solid #dde3f0 !important; border-radius: 10px !important; padding: 12px 16px !important; }
label { font-size: 0.75rem !important; font-weight: 700 !important; }
.trip-card { background: linear-gradient(135deg, #f0f4ff, #e8eeff); border-left: 4px solid #003399; border-radius: 8px; padding: 8px 14px; margin: 4px 0; font-size: 0.82rem; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================
def show_advance_page():
    st.markdown(ADVANCE_CSS, unsafe_allow_html=True)
    st.header("💸 एडवांस पेमेंट (V2 Superfast)")

    df_trips = get_bookings_from_supabase()

    if df_trips.empty:
        st.info("⚠️ कोई बुकिंग नहीं मिली। पहले 'बुकिंग' पेज से गाड़ी लगाएँ।")
        return

    # ── Trip selector ──
    labels, trip_ids, truck_nos = [], [], []
    for _, row in df_trips.iterrows():
        labels.append(f"🚛 {row['truck_no']}  |  📅 {row['date_val']}  |  📍 {row['to_loc']}")
        trip_ids.append(str(row['trip_id']))
        truck_nos.append(str(row['truck_no']))

    selected_label = st.selectbox("गाड़ी चुनें:", ["चुनें..."] + labels, label_visibility="collapsed")

    if selected_label == "चुनें...":
        st.info("👆 ऊपर से गाड़ी चुनें।")
        return

    idx = labels.index(selected_label)
    sel_trip_id = trip_ids[idx]
    sel_truck_no = truck_nos[idx]
    sel_row = df_trips[df_trips['trip_id'] == sel_trip_id].iloc[0]

    st.markdown(f"""
        <div class='trip-card'>
            🚛 <b>{sel_truck_no}</b> &nbsp;&nbsp; 📅 {sel_row['date_val']} &nbsp;&nbsp; 
            📍 {sel_row['to_loc']} &nbsp;&nbsp; 💵 कुल गाड़ी भाड़ा: <b>₹{int(sel_row['owner_freight']):,}</b>
        </div>
    """, unsafe_allow_html=True)

    # ── Advance Form ──
    with st.form("advance_form", clear_on_submit=True):
        st.markdown("#### 💳 एडवांस की जानकारी")
        c1, c2, c3 = st.columns(3)
        with c1: adv_date = st.date_input("📅 तारीख", datetime.date.today())
        with c2: adv_amount = st.number_input("💵 अमाउंट (₹)", min_value=0, step=500)
        with c3: pay_mode = st.selectbox("🏦 पेमेंट मोड", 
            ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747", "Pump (Shekh Filling)", "Other"])

        c4, c5 = st.columns([3, 1])
        with c4: remarks = st.text_input("📝 विवरण / UTR No.")
        with c5:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("💾 एडवांस सेव करें", use_container_width=True, type="primary")

        if submitted:
            if adv_amount <= 0:
                st.error("⚠️ सही अमाउंट दर्ज करें!")
            else:
                with st.spinner("⏳ सुपरफ़ास्ट सेव हो रहा है..."):
                    if save_advance_to_supabase(adv_date, sel_trip_id, sel_truck_no, pay_mode, remarks, adv_amount):
                        st.success(f"✅ गाड़ी {sel_truck_no} को ₹{adv_amount:,} का एडवांस सेव हो गया!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ एडवांस सेव नहीं हो पाया।")
