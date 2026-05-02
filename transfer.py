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
        last_col_data = df.iloc[:, -1].astype(str).str.replace(',', '').str.replace('₹', '').str.strip()
        total_balance = pd.to_numeric(last_col_data, errors='coerce').fillna(0).sum()
        return {"balance": int(total_balance)}
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
        
        # जहाँ से पैसा कटा (Sender)
        if f_s:
            if from_acc == "Canara 1747":
                db.worksheet(f_s).append_row([str(date_val), remarks if remarks else "Transfer Out", f"To: {to_acc}", -amt], table_range="A1")
            else:
                db.worksheet(f_s).append_row([str(date_val), "Transfer", "Debit", f"To: {to_acc} | {remarks}", -amt], table_range="A1")
        
        # जहाँ पैसा गया (Receiver)
        if t_s:
            if to_acc == "Canara 1747":
                db.worksheet(t_s).append_row([str(date_val), remarks if remarks else "Transfer In", f"From: {from_acc}", amt], table_range="A1")
            elif to_acc in ["Ishtyaque Ledger", "Universal Ledger"]:
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
    # 🟢 मॉडर्न और कॉम्पैक्ट CSS Injection
    st.markdown("""
        <style>
            /* टॉप पैडिंग कम करना ताकि ऊपर से जगह बचे */
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 1rem;
            }
            
            /* हेडर्स का साइज़ छोटा करना */
            h2 { font-size: 1.5rem !important; margin-bottom: 0px !important; padding-bottom: 0px !important; }
            h3 { font-size: 1.1rem !important; margin-bottom: 5px !important; }
            p { margin-bottom: 0.2rem !important; }

            /* फॉर्म के अंदर की स्पेसिंग खत्म करना */
            div[data-testid="stForm"] > div > div {
                gap: 0.1rem !important;
            }
            
            /* मेट्रिक कार्ड्स (बैंक बैलेंस) का कॉम्पैक्ट और 3D डिज़ाइन */
            div[data-testid="metric-container"] {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                padding: 5px 10px;
                border-radius: 8px;
                box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.05);
                border-left: 4px solid #007bff;
            }
            
            div[data-testid="metric-container"]:hover {
                box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
            }

            @media (prefers-color-scheme: dark) {
                div[data-testid="metric-container"] {
                    background-color: #1e1e1e;
                    border-color: #333;
                }
            }
            
            /* इनपुट फील्ड्स को स्लिम बनाना */
            .stTextInput > div > div > input,
            .stNumberInput > div > div > input,
            .stSelectbox > div > div > select {
                padding-top: 0.1rem;
                padding-bottom: 0.1rem;
                min-height: 2.2rem;
            }
            
            /* एक्स्ट्रा खाली डिवाइडर लाइन छिपाना */
            hr { margin: 0.5em 0px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.header("🔀 ट्रांसफर / पेमेंट (Bank to Bank / Cash / Pump)")
    
    st.markdown("### 🏦 खातों का लाइव बैलेंस:")
    
    # 🟢 6 कॉलम वाला कॉम्पैक्ट मीटर
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
    
    if pump_stat['balance'] < 0:
        c6.metric("⛽ Pump (उधार)", f"₹{abs(pump_stat['balance']):,}", "देना है", delta_color="inverse")
    else:
        c6.metric("⛽ Pump (हिसाब)", f"₹{pump_stat['balance']:,}", "क्लियर", delta_color="normal")

    st.write("---")

    # 🟢 SESSION STATES 
    if "tf_ck" not in st.session_state: st.session_state.tf_ck = 0
    if "show_tf_confirm" not in st.session_state: st.session_state.show_tf_confirm = False
    
    c = st.session_state.tf_ck

    # 1. कॉम्पैक्ट डेटा फॉर्म (ग्रिड लेआउट)
    if not st.session_state.show_tf_confirm:
        with st.form(key=f"transfer_form_{c}"):
            # पहली लाइन: तारीख, भेजने वाला, पाने वाला
            col1, col2, col3 = st.columns([1, 1.5, 1.5])
            with col1:
                t_date = st.date_input("तारीख", datetime.date.today())
            with col2:
                from_acc = st.selectbox("कहाँ से कटा (Sender)?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747"])
            with col3:
                to_acc = st.selectbox("कहाँ गया (Receiver)?", ["चुनें...", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747", "Shekh Filling (Pump)", "Ishtyaque Ledger", "Universal Ledger"])

            # दूसरी लाइन: अमाउंट, विवरण, और बटन
            col4, col5, col6 = st.columns([1, 2, 1])
            with col4:
                t_amt = st.number_input("अमाउंट (₹)", min_value=0, step=500)
            with col5:
                t_remarks = st.text_input("विवरण (Remarks/UTR)")
            with col6:
                st.markdown("<br>", unsafe_allow_html=True) # बटन को अलाइन करने के लिए
                submit_tf = st.form_submit_button("➡️ ट्रांसफर करें", use_container_width=True)

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
            with st.spinner("⏳ ट्रांसफर हो रहा है..."):
                if save_transfer_ledgers(d['t_date'], d['from_acc'], d['to_acc'], d['t_amt'], d['t_remarks']):
                    st.success(f"✅ ₹{d['t_amt']:,} सफलतापूर्वक ट्रांसफर हो गए!")
                    time.sleep(1.5)
                    st.session_state.show_tf_confirm = False
                    st.session_state.tf_ck += 1 
                    st.rerun()
                else:
                    st.error("❌ कुछ तकनीकी ख़राबी हुई। कृपया गूगल शीट चेक करें।")
                    
        if cancel_clicked:
            st.session_state.show_tf_confirm = False
            st.rerun()

# अगर आप इसे अकेले टेस्ट करना चाहें तो:
# if __name__ == "__main__":
#     st.set_page_config(layout="wide")
#     show_transfer_page()
