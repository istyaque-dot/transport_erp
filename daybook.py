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

def save_daybook_entry(date_val, account, e_type, category, amount, remarks):
    try:
        final_amt = int(amount) if "Credit" in e_type else -int(amount)
        
        # 1. Day Book Table में मुख्य एंट्री
        db_entry = {
            "date_val": str(date_val),
            "account_name": str(account),
            "entry_type": str(e_type),
            "category": str(category),
            "amount": int(amount),
            "remarks": str(remarks)
        }
        supabase.table("day_book").insert(db_entry).execute()

        # 2. Bank Ledgers Table में एंट्री (ताकि बैंक बैलेंस अपडेट रहे)
        bank_entry = {
            "bank_name": str(account),
            "date_val": str(date_val),
            "trip_id": "DAYBOOK",
            "gr_no": "N/A",
            "description": f"{category} | {remarks}",
            "amount": final_amt
        }
        supabase.table("bank_ledgers").insert(bank_entry).execute()
        
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_daybook_page():
    st.header("📓 अन्य जमा और खर्च (Day Book V2)")
    st.write("ऑफिस खर्च, मेंटेनेंस या अन्य पर्सनल लेन-देन यहाँ दर्ज करें।")

    if "db_ck" not in st.session_state: st.session_state.db_ck = 0
    
    # Form Setup
    with st.form(key=f"daybook_form_{st.session_state.db_ck}"):
        entry_date = st.date_input("तारीख", datetime.date.today())
        
        col1, col2 = st.columns(2)
        with col1:
            entry_type = st.radio("एंट्री का प्रकार:", ["Debit (खर्चा/गया)", "Credit (जमा/आया)"], horizontal=True)
            account_name = st.selectbox("खाता चुनें:", ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747"])
            
        with col2:
            amount = st.number_input("अमाउंट (₹)", min_value=0, step=100)
            category = st.selectbox("कैटेगरी:", 
                ["ऑफिस खर्च", "गाड़ी मेंटेनेंस", "ड्राइवर सैलरी", "लोन / उधार", 
                 "मालिक का खर्च", "Car EMI", "Personal Saving", "अन्य"])
            
        remarks = st.text_input("विवरण (Remarks)")
        submit_db = st.form_submit_button("✅ एंट्री सेव करें", use_container_width=True, type="primary")

    if submit_db:
        if amount <= 0:
            st.error("⚠️ कृपया सही अमाउंट भरें!")
        else:
            with st.spinner("⏳ सुपरफ़ास्ट सेव हो रहा है..."):
                if save_daybook_entry(entry_date, account_name, entry_type, category, amount, remarks):
                    st.success(f"✅ {category} के ₹{amount:,} सेव हो गए और {account_name} अपडेट हो गया!")
                    st.balloons()
                    time.sleep(1.5)
                    st.session_state.db_ck += 1
                    st.rerun()
                else:
                    st.error("❌ सेव नहीं हो पाया।")

    # हालिया एंट्रीज की लिस्ट
    st.markdown("---")
    st.subheader("📋 हालिया 10 लेन-देन")
    try:
        res = supabase.table("day_book").select("*").order("created_at", desc=True).limit(10).execute()
        if res.data:
            st.table(pd.DataFrame(res.data)[['date_val', 'account_name', 'entry_type', 'category', 'amount', 'remarks']])
    except:
        st.info("अभी कोई एंट्री नहीं है।")
