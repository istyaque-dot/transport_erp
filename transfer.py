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
def get_all_bank_balances():
    """सारे बैंक खातों का लाइव बैलेंस एक साथ निकालना"""
    try:
        res = supabase.table("bank_ledgers").select("bank_name, amount").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            return df.groupby("bank_name")["amount"].sum().to_dict()
        return {}
    except: return {}

def execute_transfer(date_val, from_acc, to_acc, amount, remarks):
    try:
        amt = int(amount)
        entries = []
        
        # 1. भेजने वाले खाते से पैसा कटा (Debit)
        entries.append({
            "bank_name": str(from_acc),
            "date_val": str(date_val),
            "trip_id": "TRANSFER",
            "gr_no": "N/A",
            "description": f"Transfer To: {to_acc} | {remarks}",
            "amount": -amt
        })
        
        # 2. पाने वाले खाते में पैसा जमा हुआ (Credit)
        # Note: Agar receiver special ledger hai to usme bhi jayega
        entries.append({
            "bank_name": str(to_acc),
            "date_val": str(date_val),
            "trip_id": "TRANSFER",
            "gr_no": "N/A",
            "description": f"Transfer From: {from_acc} | {remarks}",
            "amount": amt
        })

        # Supabase में एक साथ दोनों एंट्री सेव करना
        supabase.table("bank_ledgers").insert(entries).execute()
        
        # अगर Ishtyaque या Universal Ledger में ट्रांसफर है, तो वहां भी रिकॉर्ड डालना
        if "Ishtyaque" in to_acc:
            supabase.table("ishtyaque_ledger").insert({"date_val": str(date_val), "trip_id": "TRANSFER", "gr_no": "N/A", "truck_no": "N/A", "description": f"From: {from_acc}", "amount": amt}).execute()
        elif "Universal" in to_acc:
            supabase.table("universal_ledger").insert({"date_val": str(date_val), "trip_id": "TRANSFER", "gr_no": "N/A", "truck_no": "N/A", "description": f"From: {from_acc}", "amount": amt}).execute()
            
        return True
    except Exception as e:
        st.error(f"Transfer Error: {e}")
        return False

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_transfer_page():
    st.header("🔀 बैंक ट्रांसफर / पेमेंट (V2)")

    # लाइव बैलेंस दिखाना
    st.subheader("🏦 खातों का लाइव बैलेंस")
    bals = get_all_bank_balances()
    
    # खातों की लिस्ट
    accounts = ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747", "Pump (Shekh Filling)", "Ishtyaque Ledger", "Universal Ledger"]
    
    c1, c2, c3, c4 = st.columns(4)
    cols = [c1, c2, c3, c4]
    
    for i, acc in enumerate(accounts[:4]):
        cols[i].metric(acc, f"₹{bals.get(acc, 0):,}")
    
    c5, c6, c7, c8 = st.columns(4)
    cols2 = [c5, c6, c7, c8]
    for i, acc in enumerate(accounts[4:]):
        cols2[i].metric(acc, f"₹{bals.get(acc, 0):,}")

    st.divider()

    # ट्रांसफर फॉर्म
    if "tf_ck" not in st.session_state: st.session_state.tf_ck = 0

    with st.form(key=f"tf_form_{st.session_state.tf_ck}"):
        st.markdown("#### 💸 नया ट्रांसफर दर्ज करें")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            t_date = st.date_input("तारीख", datetime.date.today())
            from_acc = st.selectbox("कहाँ से कटा (Sender)?", ["चुनें..."] + accounts[:5]) # पंप या लेजर से पैसा नहीं कटेगा
            
        with col_b:
            t_amt = st.number_input("अमाउंट (₹)", min_value=0, step=500)
            to_acc = st.selectbox("कहाँ गया (Receiver)?", ["चुनें..."] + accounts)
            
        with col_c:
            t_remarks = st.text_input("विवरण (Remarks/UTR)")
            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("➡️ ट्रांसफर कंफर्म करें", use_container_width=True, type="primary")

    if submit:
        if from_acc == "चुनें..." or to_acc == "चुनें...":
            st.error("⚠️ कृपया दोनों खाते चुनें!")
        elif from_acc == to_acc:
            st.error("⚠️ भेजने वाला और पाने वाला खाता एक नहीं हो सकता!")
        elif t_amt <= 0:
            st.error("⚠️ कृपया सही अमाउंट भरें!")
        else:
            with st.spinner("⏳ सुरक्षित ट्रांसफर हो रहा है..."):
                if execute_transfer(t_date, from_acc, to_acc, t_amt, t_remarks):
                    st.success(f"✅ ₹{t_amt:,} सफलतापूर्वक {from_acc} से {to_acc} में भेज दिए गए!")
                    st.balloons()
                    time.sleep(1.5)
                    st.session_state.tf_ck += 1
                    st.rerun()
