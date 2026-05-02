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

@st.cache_data(ttl=10)
def get_trip_financials(trip_id):
    """एक ही बार में सारा हिसाब (Received + Shortage) निकालना"""
    try:
        # 1. रिसीवेबल्स से अब तक आया हुआ पैसा
        rec_res = supabase.table("receivables").select("amount").eq("trip_id", trip_id).execute()
        received = sum(r['amount'] for r in rec_res.data) if rec_res.data else 0
        
        # 2. Company_PODs से शॉर्टेज
        short_res = supabase.table("company_pods").select("shortage").eq("trip_id", trip_id).execute()
        shortage = sum(s['shortage'] for s in short_res.data) if short_res.data else 0
        
        return received, shortage
    except: return 0, 0

def save_receivable_to_supabase(data):
    try:
        # 1. Receivables टेबल में एंट्री
        supabase.table("receivables").insert(data).execute()
        
        # 2. Company Ledger में एंट्री (कंपनी के खाते से बैलेंस कम होगा)
        comp_ledger = {
            "date_val": data["date_val"], "trip_id": data["trip_id"], "gr_no": data.get("gr_no", "N/A"),
            "truck_no": data["truck_no"], "description": f"Payment Received: {data['bank_name']}",
            "amount": -int(data["amount"]) # पेमेंट आया तो बैलेंस माइनस
        }
        supabase.table("company_ledger").insert(comp_ledger).execute()
        
        # 3. Bank Ledger में एंट्री (बैंक में पैसा बढ़ा)
        bank_ledger = {
            "bank_name": data["bank_name"], "date_val": data["date_val"], "trip_id": data["trip_id"],
            "gr_no": data.get("gr_no", "N/A"), "description": f"From {data['comp_name']} | {data['truck_no']}",
            "amount": int(data["amount"]) # बैंक में पैसा प्लस
        }
        supabase.table("bank_ledgers").insert(bank_ledger).execute()
        
        return True
    except: return False

@st.cache_data(ttl=15)
def get_all_bookings():
    try:
        res = supabase.table("bookings").select("*").order("created_at", desc=True).limit(100).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

# ==========================================
# 🎨 CSS
# ==========================================
REC_CSS = """
<style>
.block-container { padding-top: 0.8rem !important; max-width: 98% !important; }
[data-testid="stForm"] { background: #fff !important; border-radius: 10px !important; padding: 12px 16px !important; }
.trip-card { background: linear-gradient(135deg, #f0f4ff, #e8eeff); border-left: 4px solid #003399; border-radius: 8px; padding: 7px 14px; margin: 3px 0; font-size: 0.82rem; }
.section-header { font-size: 0.82rem; font-weight: 700; color: #003399; background: #f0f4ff; border-radius: 6px; padding: 4px 10px; margin: 6px 0; border-left: 3px solid #003399; }
.status-clear { background: #d1e7dd; border-radius: 8px; padding: 7px; color: #0f5132; font-weight: 700; text-align: center; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================
def show_receivable_page():
    st.markdown(REC_CSS, unsafe_allow_html=True)
    st.header("📥 कंपनी से पैसा आया (Receivables V2)")

    if "rec_ck" not in st.session_state: st.session_state.rec_ck = 0
    
    df = get_all_bookings()
    if df.empty:
        st.info("कोई बुकिंग नहीं मिली।")
        return

    # ── Trip Selector ──
    df['label'] = "🚛 " + df['truck_no'] + " | 🏢 " + df['company'] + " | 📍 " + df['to_loc'] + " | 📅 " + df['date_val']
    
    selected = st.selectbox("गाड़ी खोजें:", ["चुनें..."] + df['label'].tolist(), key=f"sel_rec_{st.session_state.rec_ck}")

    if selected == "चुनें...":
        st.info("👆 गाड़ी नंबर या कंपनी का नाम टाइप करके ऊपर से चुनें।")
        return

    # ── Calculations ──
    row = df[df['label'] == selected].iloc[0]
    trip_id = row['trip_id']
    
    comp_total = int(row['comp_freight'])
    tds = int(comp_total * 0.01)
    
    # Supabase से लाइव हिसाब लाना
    already_received, shortage = get_trip_financials(trip_id)
    
    net_receivable = comp_total - tds - shortage
    holding_10 = int((comp_total * 0.10) // 100) * 100
    pending_bal = net_receivable - already_received
    
    kitna_milega = (pending_bal - holding_10) if pending_bal > holding_10 else pending_bal

    # ── UI Layout ──
    st.markdown(f"<div class='trip-card'>🚛 <b>{row['truck_no']}</b> | 🏢 <b>{row['company']}</b> | 📄 GR: {row['gr_no']}</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>📊 बिल का हिसाब</div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Total Bill", f"₹{comp_total:,}")
    m2.metric("📉 TDS (1%)", f"- ₹{tds:,}")
    m3.metric("✂️ Shortage", f"- ₹{int(shortage):,}")
    m4.metric("🔒 10% रोक", f"- ₹{holding_10:,}")

    st.markdown("<div class='section-header'>💸 पेमेंट स्टेटस</div>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    s1.metric("📥 अब तक आया", f"₹{already_received:,}")
    s2.metric("⏳ कुल बाकी", f"₹{max(0, int(pending_bal)):,}")
    s3.metric("🟢 अब मिलेगा", f"₹{max(0, int(kitna_milega)):,}")

    if pending_bal <= 0:
        st.markdown("<div class='status-clear'>✅ हिसाब पूरा हो चुका है।</div>", unsafe_allow_html=True)
        return

    # ── Entry Form ──
    st.markdown("<hr>", unsafe_allow_html=True)
    with st.form(key=f"rec_form_{st.session_state.rec_ck}"):
        st.markdown("#### 💳 पेमेंट एंट्री")
        c1, c2, c3 = st.columns(3)
        with c1: rec_date = st.date_input("📅 तारीख", datetime.date.today())
        with c2: amt = st.number_input("💵 अमाउंट (₹)", min_value=0, value=int(max(0, kitna_milega)))
        with c3: bank = st.selectbox("🏦 खाता", ["Cash", "Canara 311", "Canara 41", "BOB", "Other"])

        remarks = st.text_input("📝 Remarks / Reference No.")
        
        if st.form_submit_button("💾 पेमेंट सेव करें", use_container_width=True, type="primary"):
            if amt <= 0:
                st.error("⚠️ अमाउंट दर्ज करें!")
            elif amt > (pending_bal + 5): # 5 rs buffer for rounding
                st.error(f"⛔ अमाउंट बाकी ₹{int(pending_bal):,} से ज़्यादा नहीं हो सकता।")
            else:
                with st.spinner("⏳ सेव हो रहा है..."):
                    data = {
                        "date_val": str(rec_date), "trip_id": trip_id, "truck_no": row['truck_no'],
                        "comp_name": row['company'], "amount": int(amt), "bank_name": bank,
                        "description": remarks, "gr_no": row['gr_no']
                    }
                    if save_receivable_to_supabase(data):
                        st.success("✅ पेमेंट सेव हो गई!")
                        st.balloons()
                        time.sleep(1.5)
                        st.session_state.rec_ck += 1
                        st.rerun()
