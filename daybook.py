import json
import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🗄️ DATABASE FUNCTIONS (अब सीधा यहीं पर)
# ==========================================

@st.cache_resource(ttl=86400)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    # 🟢 बदलाव: अब कोड Streamlit की तिजोरी (Secrets) से चाबी लेगा
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    client = gspread.authorize(creds)
    sheet = client.open("Khan_Transport_ERP")
    return sheet

def save_daybook_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Day_Book").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

def save_daybook_ledgers(date_val, account_name, entry_type, category, amount, remarks):
    try:
        db = connect_to_sheet()
        final_amount = int(amount) if entry_type == "Credit (पैसा आया / जमा)" else -int(amount)
        base_data = [str(date_val), "Manual Entry", str(entry_type), f"{category} - {remarks}" if remarks else category]
        
        s_name = {
            "Cash":"Cash_Ledger", 
            "canara bank 311":"Canara_311_Ledger", 
            "canara bank 41":"Canara_41_Ledger", 
            "bob":"BOB_Ledger"
        }.get(account_name)
        
        if s_name:
            db.worksheet(s_name).append_row(base_data + [final_amount], table_range="A1")
        
        st.cache_data.clear()
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE (डे बुक पेज)
# ==========================================

def show_daybook_page():
    st.header("📓 अन्य जमा और खर्च (Credit / Debit)")
    st.write("यहाँ आप ऑफिस का खर्चा, मेंटेनेंस, या कोई भी अन्य लेन-देन सेव कर सकते हैं जो गाड़ी की बुकिंग से अलग हो।")

    if "db_ck" not in st.session_state: st.session_state.db_ck = 0
    if "db_confirm" not in st.session_state: st.session_state.db_confirm = False
    if "last_db_c" not in st.session_state: st.session_state.last_db_c = -1
    
    c = st.session_state.db_ck

    with st.form(key=f"daybook_form_{c}"):
        entry_date = st.date_input("तारीख", datetime.date.today())
        
        col1, col2 = st.columns(2)
        with col1:
            entry_type = st.radio("एंट्री का प्रकार चुनें:", ["Debit (पैसा गया / खर्चा)", "Credit (पैसा आया / जमा)"], horizontal=True)
            account_name = st.selectbox("किस खाते से लेन-देन हुआ?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob"])
            
        with col2:
            amount = st.number_input("अमाउंट (₹)", min_value=1, step=100)
            category = st.selectbox("किस मद (Category) में?", 
                                    ["ऑफिस खर्च (Office Expense)", 
                                     "गाड़ी मेंटेनेंस / रिपेयर", 
                                     "ड्राइवर सैलरी / इनाम", 
                                     "लोन / उधार (Borrow/Lend)", 
                                     "मालिक का खर्च (Owner Drawings)", 
                                     "अन्य (Others)"])
            
        remarks = st.text_input("विवरण (Remarks / किसको दिया या किससे लिया?)")

        submit_db = st.form_submit_button("✅ एंट्री सेव करें")

    if submit_db:
        if account_name == "चुनें...":
            st.error("⚠️ कृपया खाता (Cash/Bank) चुनें!")
        elif amount <= 0:
            st.error("⚠️ कृपया सही अमाउंट भरें!")
        else:
            st.session_state.db_confirm = True

    if st.session_state.db_confirm:
        color = "green" if "Credit" in entry_type else "red"
        st.markdown(f"❓ क्या आप पक्का **<span style='color:{color}'>₹{int(amount):,} ({entry_type})</span>** की एंट्री सेव करना चाहते हैं?", unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 4])
        if c1.button("👍 हाँ, सेव करें", key=f"yes_db_{c}"):
            if st.session_state.last_db_c == c:
                st.warning("⏳ डाटा सेव हो रहा है, कृपया इंतज़ार करें...")
            else:
                st.session_state.last_db_c = c 
                row = [str(entry_date), account_name, entry_type, category, int(amount), remarks]
                
                if save_daybook_to_db(row):
                    save_daybook_ledgers(entry_date, account_name, entry_type, category, amount, remarks)
                    st.success("✅ लेन-देन सफलतापूर्वक सेव और खाते में अपडेट हो गया!")
                    st.session_state.db_confirm = False
                    time.sleep(2)
                    st.session_state.db_ck += 1
                    st.rerun()
                
        if c2.button("❌ कैंसिल", key=f"no_db_{c}"):
            st.session_state.db_confirm = False
            st.rerun()
