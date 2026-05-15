import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 🗄️ DATABASE FUNCTIONS
# ==========================================

from sheet_utils import connect_to_sheet, invalidate_sheet_cache

@st.cache_data(ttl=600)
def get_ledger_stats(sheet_name):
    """लेजर के आखिरी कॉलम की अंतिम वैल्यू (Current Balance) उठाना"""
    try:
        db = connect_to_sheet()
        data = db.worksheet(sheet_name).get_all_values()
        if len(data) > 1:
            # आखिरी रो (Last Row) का आखिरी कॉलम (Last Column) बैलेंस होता है
            last_row = data[-1]
            last_val = str(last_row[-1]).replace(',', '').replace('₹', '').strip()
            return {"balance": int(float(last_val or 0))}
    except: pass
    return {"balance": 0}

def save_transfer_ledgers(date_val, from_acc, to_acc, amount, remarks):
    try:
        db = connect_to_sheet()
        amt = int(amount)
        s_map = {
            "Cash": "Cash_Ledger", 
            "canara bank 311": "Canara_311_Ledger", 
            "canara bank 41": "Canara_41_Ledger", 
            "bob": "BOB_Ledger", 
            "Shekh Filling (Pump)": "Shekh_Filling_Ledger",
            "Ishtyaque Ledger": "Ishtyaque_Ledger",
            "Universal Ledger": "Universal_Ledger",
            "Canara 1747": "canara_1747"
        }
        
        f_s = s_map.get(from_acc)
        t_s = s_map.get(to_acc)
        
        # 1. जहाँ से पैसा कटा (Sender - Debit)
        if f_s:
            if from_acc == "Canara 1747":
                db.worksheet(f_s).append_row([str(date_val), remarks if remarks else "Transfer Out", f"To: {to_acc}", -amt], table_range="A1")
            else:
                db.worksheet(f_s).append_row([str(date_val), "Transfer", "Debit", f"To: {to_acc} | {remarks}", -amt], table_range="A1")
        
        # 2. जहाँ पैसा गया (Receiver - Credit)
        if t_s:
            if to_acc == "Canara 1747":
                db.worksheet(t_s).append_row([str(date_val), remarks if remarks else "Transfer In", f"From: {from_acc}", amt], table_range="A1")
            elif to_acc in ["Ishtyaque Ledger", "Universal Ledger"]:
                db.worksheet(t_s).append_row([str(date_val), "Transfer", "N/A", "N/A", f"From: {from_acc}", amt], table_range="A1")
            else:
                db.worksheet(t_s).append_row([str(date_val), "Transfer", "Credit", f"From: {from_acc} | {remarks}", amt], table_range="A1")
        
        invalidate_sheet_cache()
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_transfer_page():
    st.markdown("""
        <style>
            .block-container { padding-top: 1.5rem; }
            div[data-testid="metric-container"] {
                background-color: #ffffff; border: 1px solid #e0e0e0;
                padding: 5px 10px; border-radius: 8px; border-left: 4px solid #007bff;
            }
            .stTextInput > div > div > input { min-height: 2.2rem; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🔀 ट्रांसफर / पेमेंट (Bank / Cash / Pump)")
    
    # खातों का लाइव बैलेंस
    st.markdown("### 🏦 खातों का लाइव बैलेंस:")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    cash_stat = get_ledger_stats("Cash_Ledger")
    c311_stat = get_ledger_stats("Canara_311_Ledger")
    c41_stat = get_ledger_stats("Canara_41_Ledger")
    bob_stat = get_ledger_stats("BOB_Ledger")
    c1747_stat = get_ledger_stats("canara_1747")
    pump_stat = get_ledger_stats("Shekh_Filling_Ledger")
    
    c1.metric("💵 Cash", f"₹{cash_stat['balance']:,}")
    c2.metric("🏦 Canara 311", f"₹{c311_stat['balance']:,}")
    c3.metric("🏦 Canara 41", f"₹{c41_stat['balance']:,}")
    c4.metric("🏦 BOB", f"₹{bob_stat['balance']:,}")
    c5.metric("🏦 Canara 1747", f"₹{c1747_stat['balance']:,}")
    
    p_bal = pump_stat['balance']
    c6.metric("⛽ Pump", f"₹{abs(p_bal):,}", "देना है" if p_bal < 0 else "जमा है", delta_color="inverse" if p_bal < 0 else "normal")

    st.write("---")

    if "tf_ck" not in st.session_state: st.session_state.tf_ck = 0
    if "show_tf_confirm" not in st.session_state: st.session_state.show_tf_confirm = False
    
    c = st.session_state.tf_ck

    if not st.session_state.show_tf_confirm:
        with st.form(key=f"transfer_form_{c}"):
            col1, col2, col3 = st.columns([1, 1.5, 1.5])
            with col1: t_date = st.date_input("तारीख", datetime.date.today())
            with col2: from_acc = st.selectbox("कहाँ से कटा?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747"])
            with col3: to_acc = st.selectbox("कहाँ गया?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747", "Shekh Filling (Pump)", "Ishtyaque Ledger", "Universal Ledger"])

            col4, col5, col6 = st.columns([1, 2, 1])
            with col4: t_amt = st.number_input("अमाउंट (₹)", min_value=0, step=500)
            with col5: t_remarks = st.text_input("विवरण (UTR / Remarks)")
            with col6: 
                st.markdown("<br>", unsafe_allow_html=True)
                submit_tf = st.form_submit_button("➡️ ट्रांसफर करें", use_container_width=True)

        if submit_tf:
            if from_acc == "चुनें..." or to_acc == "चुनें..." or t_amt <= 0:
                st.error("⚠️ कृपया सही खाते और अमाउंट भरें!")
            elif from_acc == to_acc:
                st.error("⚠️ सेम खातों में ट्रांसफर नहीं हो सकता!")
            else:
                st.session_state.tf_temp_data = {"t_date": t_date, "from_acc": from_acc, "to_acc": to_acc, "t_amt": t_amt, "t_remarks": t_remarks}
                st.session_state.show_tf_confirm = True
                st.rerun()

    if st.session_state.show_tf_confirm:
        d = st.session_state.tf_temp_data
        st.warning(f"❓ क्या आप पक्का ₹{d['t_amt']:,} को **{d['from_acc']}** से **{d['to_acc']}** में ट्रांसफर करना चाहते हैं?")
        c1, c2 = st.columns([1, 4])
        if c1.button("👍 हाँ", type="primary"):
            with st.spinner("⏳ प्रोसेस हो रहा है..."):
                if save_transfer_ledgers(d['t_date'], d['from_acc'], d['to_acc'], d['t_amt'], d['t_remarks']):
                    st.success("✅ सफलतापूर्वक ट्रांसफर हो गया!"); time.sleep(1.5)
                    st.session_state.show_tf_confirm = False
                    st.session_state.tf_ck += 1; st.rerun()
        if c2.button("❌ कैंसिल"):
            st.session_state.show_tf_confirm = False; st.rerun()
