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
@st.cache_data(ttl=60)
def get_sheet_data_for_reports(sheet_name):
    try:
        db = connect_to_sheet()
        data = db.worksheet(sheet_name).get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_ledger_stats(sheet_name):
    df = get_sheet_data_for_reports(sheet_name)
    if not df.empty:
        df.iloc[:, -1] = pd.to_numeric(df.iloc[:, -1], errors='coerce').fillna(0)
        return {"balance": int(df.iloc[:, -1].sum())}
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
            "Canara 1747": "canara_1747"  # 🟢 नया अकाउंट यहाँ जुड़ गया
        }
        
        f_s = s_map.get(from_acc)
        t_s = s_map.get(to_acc)
        
        # जहाँ से पैसा कटा (Sender)
        if f_s:
            if from_acc == "Canara 1747":
                # Canara 1747 का स्पेशल 4-कॉलम फॉर्मेट: Date, Comment, To/From, Amount
                db.worksheet(f_s).append_row([str(date_val), remarks if remarks else "Transfer Out", f"To: {to_acc}", -amt], table_range="A1")
            else:
                # नॉर्मल 5-कॉलम फॉर्मेट
                db.worksheet(f_s).append_row([str(date_val), "Transfer", "Debit", f"To: {to_acc} | {remarks}", -amt], table_range="A1")
        
        # जहाँ पैसा गया (Receiver)
        if t_s:
            if to_acc == "Canara 1747":
                # Canara 1747 का स्पेशल 4-कॉलम फॉर्मेट: Date, Comment, To/From, Amount
                db.worksheet(t_s).append_row([str(date_val), remarks if remarks else "Transfer In", f"From: {from_acc}", amt], table_range="A1")
            elif to_acc in ["Ishtyaque Ledger", "Universal Ledger"]:
                # Ishtyaque और Universal के 6-कॉलम लेजर के लिए (इसे बिल्कुल नहीं छेड़ा गया है)
                db.worksheet(t_s).append_row([str(date_val), "Transfer", "N/A", "N/A", f"From: {from_acc}", amt], table_range="A1")
            else:
                db.worksheet(t_s).append_row([str(date_val), "Transfer", "Credit", f"From: {from_acc} | {remarks}", amt], table_range="A1")
        
        st.cache_data.clear()
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE (ट्रांसफर पेज)
# ==========================================

def show_transfer_page():
    # 🟢 CSS Injection
    st.markdown("""
        <style>
            div[data-testid="stForm"] > div > div {
                gap: 0.5rem;
            }
            .stTextInput > div > div > input,
            .stNumberInput > div > div > input,
            .stSelectbox > div > div > select {
                padding-top: 0.25rem;
                padding-bottom: 0.25rem;
            }
            .stMarkdown p {
                margin-bottom: 0.2rem;
            }
        </style>
    """, unsafe_allow_html=True)

    st.header("🔀 ट्रांसफर / पेमेंट (Bank to Bank / Cash / Pump)")
    st.write("यहाँ से आप अपने एक खाते से दूसरे खाते में पैसे भेज सकते हैं, या पंप वाले का पेमेंट कर सकते हैं।")

    st.markdown("### 🏦 ट्रांसफर करने से पहले खातों का लाइव बैलेंस देखें:")
    
    # 🟢 नया अकाउंट दिखाने के लिए कॉलम्स को 6 कर दिया गया है
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    cash_stat = get_ledger_stats("Cash_Ledger")
    c311_stat = get_ledger_stats("Canara_311_Ledger")
    c41_stat = get_ledger_stats("Canara_41_Ledger")
    bob_stat = get_ledger_stats("BOB_Ledger")
    c1747_stat = get_ledger_stats("canara_1747")  # नया कैनरा 1747 बैलेंस
    pump_stat = get_ledger_stats("Shekh_Filling_Ledger")
    
    c1.metric("💵 Cash", f"₹{cash_stat['balance']:,}")
    c2.metric("🏦 Canara 311", f"₹{c311_stat['balance']:,}")
    c3.metric("🏦 Canara 41", f"₹{c41_stat['balance']:,}")
    c4.metric("🏦 BOB", f"₹{bob_stat['balance']:,}")
    c5.metric("🏦 Canara 1747", f"₹{c1747_stat['balance']:,}") # 🟢 नया मीटर जुड़ गया
    
    if pump_stat['balance'] < 0:
        c6.metric("⛽ Pump (उधार)", f"₹{abs(pump_stat['balance']):,}", "देना बाकी है ⏳", delta_color="inverse")
    else:
        c6.metric("⛽ Pump (हिसाब)", f"₹{pump_stat['balance']:,}", "क्लियर ✅", delta_color="normal")

    st.write("---")

    # 🟢 SESSION STATES 
    if "tf_ck" not in st.session_state: st.session_state.tf_ck = 0
    if "show_tf_confirm" not in st.session_state: st.session_state.show_tf_confirm = False
    
    c = st.session_state.tf_ck

    # 1. डेटा भरने वाला फॉर्म
    if not st.session_state.show_tf_confirm:
        with st.form(key=f"transfer_form_{c}"):
            t_date = st.date_input("लेन-देन की तारीख", datetime.date.today())
            
            col1, col2 = st.columns(2)
            with col1:
                # 🟢 Sender लिस्ट में Canara 1747 जोड़ दिया
                from_acc = st.selectbox("कहाँ से पैसा कटा (Sender)?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747"])
            with col2:
                # 🟢 Receiver लिस्ट में Canara 1747 जोड़ दिया
                to_acc = st.selectbox("कहाँ पैसा गया (Receiver)?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747", "Shekh Filling (Pump)", "Ishtyaque Ledger", "Universal Ledger"])

            t_amt = st.number_input("कितना अमाउंट भेजा (₹)?", min_value=0, step=500)
            t_remarks = st.text_input("विवरण (Remarks / UTR No.)")

            submit_tf = st.form_submit_button("➡️ आगे बढ़ें (Next)")

        if submit_tf:
            if from_acc == "चुनें..." or to_acc == "चुनें...":
                st.error("⚠️ कृपया Sender और Receiver दोनों खाते चुनें!")
            elif from_acc == to_acc:
                st.error("⚠️ एक ही खाते में पैसा ट्रांसफर नहीं हो सकता!")
            elif t_amt <= 0:
                st.error("⚠️ कृपया सही अमाउंट भरें!")
            else:
                st.session_state.tf_temp_data = {
                    "t_date": t_date, "from_acc": from_acc, "to_acc": to_acc,
                    "t_amt": t_amt, "t_remarks": t_remarks
                }
                st.session_state.show_tf_confirm = True
                st.rerun()

    # 2. कन्फर्मेशन वाली स्क्रीन
    if st.session_state.show_tf_confirm:
        d = st.session_state.tf_temp_data
        st.warning(f"❓ क्या आप पक्का **₹{d['t_amt']:,}** को **{d['from_acc']}** से **{d['to_acc']}** में ट्रांसफर करना चाहते हैं?")
        
        action_container = st.empty()
        
        with action_container.container():
            c1, c2 = st.columns([1, 4])
            save_clicked = c1.button("👍 हाँ, ट्रांसफर करें", type="primary")
            cancel_clicked = c2.button("❌ कैंसिल")

        if save_clicked:
            action_container.empty() 
            with st.spinner("⏳ ट्रांसफर हो रहा है, कृपया 2 सेकंड रुकें..."):
                if save_transfer_ledgers(d['t_date'], d['from_acc'], d['to_acc'], d['t_amt'], d['t_remarks']):
                    st.success(f"✅ ₹{d['t_amt']:,} सफलतापूर्वक {d['from_acc']} से {d['to_acc']} में ट्रांसफर हो गए!")
                    time.sleep(1.5)
                    st.session_state.show_tf_confirm = False
                    st.session_state.tf_ck += 1 
                    st.rerun()
                else:
                    st.error("❌ कुछ तकनीकी ख़राबी हुई। कृपया गूगल शीट चेक करें।")
                    
        if cancel_clicked:
            st.session_state.show_tf_confirm = False
            st.rerun()
