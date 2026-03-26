import json
import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
    # 🟢 FIX: json.loads हटा दिया गया है क्योंकि Streamlit अब सीधा डिक्शनरी देता है
    creds_dict = dict(st.secrets["gcp_service_account"])
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
        
        # 🟢 नया अकाउंट Canara 1747 यहाँ जुड़ गया
        s_name = {
            "Cash":"Cash_Ledger", 
            "canara bank 311":"Canara_311_Ledger", 
            "canara bank 41":"Canara_41_Ledger", 
            "bob":"BOB_Ledger",
            "Canara 1747":"canara_1747"
        }.get(account_name)
        
        if s_name:
            if account_name == "Canara 1747":
                # Canara 1747 का स्पेशल 4-कॉलम फॉर्मेट: Date, Comment, To/From, Amount
                comment = f"{category} - {remarks}" if remarks else category
                to_from_text = "From Daybook (In)" if entry_type == "Credit (पैसा आया / जमा)" else "From Daybook (Out)"
                db.worksheet(s_name).append_row([str(date_val), comment, to_from_text, final_amount], table_range="A1")
            else:
                # पुराने लेजर्स का नॉर्मल 5-कॉलम फॉर्मेट
                db.worksheet(s_name).append_row(base_data + [final_amount], table_range="A1")
        
        st.cache_data.clear()
        return True
    except Exception as e: 
        print(f"Error saving ledger: {e}")
        return False

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
            # 🟢 खाते की लिस्ट में Canara 1747 जोड़ दिया गया है
            account_name = st.selectbox("किस खाते से लेन-देन हुआ?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747"])
            
        with col2:
            amount = st.number_input("अमाउंट (₹)", min_value=1, step=100)
            # 🟢 कैटेगरी में Car EMI और Saving जोड़ दिए गए हैं
            category = st.selectbox("किस मद (Category) में?", 
                                    ["ऑफिस खर्च (Office Expense)", 
                                     "गाड़ी मेंटेनेंस / रिपेयर", 
                                     "ड्राइवर सैलरी / इनाम", 
                                     "लोन / उधार (Borrow/Lend)", 
                                     "मालिक का खर्च (Owner Drawings)", 
                                     "Car EMI (गाड़ी की किश्त)",
                                     "Personal Saving (बचत)",
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
                else:
                    st.error("❌ कुछ तकनीकी ख़राबी हुई। कृपया गूगल शीट चेक करें।")
                
        if c2.button("❌ कैंसिल", key=f"no_db_{c}"):
            st.session_state.db_confirm = False
            st.rerun()
