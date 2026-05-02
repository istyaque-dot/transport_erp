import streamlit as st
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
    return client.open("Khan_Transport_ERP")

def clean_amt(val):
    try:
        if str(val).strip() == "": return 0
        return float(str(val).replace(',', '').replace('₹', '').strip())
    except: return 0

@st.cache_data(ttl=30) # 30 सेकंड में ऑटो-रिफ्रेश
def get_ledger_balance(sheet_name):
    try:
        db = connect_to_sheet()
        data = db.worksheet(sheet_name).get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            # आखिरी कॉलम का टोटल निकालना
            vals = df.iloc[:, -1].astype(str).str.replace(',', '').str.replace('₹', '').str.strip()
            return int(pd.to_numeric(vals, errors='coerce').fillna(0).sum())
    except: pass
    return 0

@st.cache_data(ttl=60)
def get_truck_payable():
    try:
        db = connect_to_sheet()
        bk_raw = db.worksheet("Bookings").get_all_values()
        adv_raw = db.worksheet("Advances").get_all_values()
        own_raw = db.worksheet("Owner_Ledger").get_all_values()

        df_bk = pd.DataFrame(bk_raw[1:], columns=bk_raw[0])

        adv_map = {}
        if len(adv_raw) > 1:
            for r in adv_raw[1:]:
                if len(r) > 8:
                    tid = str(r[1]).strip()
                    adv_map[tid] = adv_map.get(tid, 0) + clean_amt(r[8])

        own_ledg_map = {}
        if len(own_raw) > 1:
            for r in own_raw[1:]:
                if len(r) > 5:
                    tid = str(r[1]).strip()
                    desc = str(r[4])
                    if any(x in desc for x in ["Final Balance", "Shortage", "Extra", "Detention"]):
                        own_ledg_map[tid] = own_ledg_map.get(tid, 0) + clean_amt(r[5])

        total_dena = 0
        for _, row in df_bk.iterrows():
            if len(row) < 15: continue
            tid = str(row.iloc[14]).strip()
            try:
                own_fr = clean_amt(row.iloc[12])
                if own_fr > 0:
                    munshiyana = clean_amt(row.iloc[5]) * 1
                    adv_given = adv_map.get(tid, 0)
                    own_settlement = own_ledg_map.get(tid, 0) 
                    o_bal = (own_fr - munshiyana) - adv_given + own_settlement
                    
                    if o_bal > 10: 
                        total_dena += o_bal
            except: pass
        return total_dena
    except: return 0

# ==========================================
# 🖥️ USER INTERFACE (डैशबोर्ड पेज)
# ==========================================
def show_dashboard_page():
    # --- मॉडर्न UI के लिए Custom CSS ---
    st.markdown("""
        <style>
        /* मेट्रिक कार्ड्स को मॉडर्न बॉक्स में बदलना */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e6e6e6;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
            border-left: 5px solid #007bff; /* डिफ़ॉल्ट नीली पट्टी */
        }
        
        /* माउस ले जाने पर 3D इफ़ेक्ट (Hover) */
        div[data-testid="metric-container"]:hover {
            transform: translateY(-5px);
            box-shadow: 0px 8px 20px rgba(0, 0, 0, 0.12);
        }

        /* डार्क मोड सपोर्ट */
        @media (prefers-color-scheme: dark) {
            div[data-testid="metric-container"] {
                background-color: #1e1e1e;
                border: 1px solid #333;
            }
        }

        /* हेडर्स को और प्रोफेशनल बनाना */
        h2, h3 {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-weight: 600;
            padding-bottom: 10px;
        }
        
        /* रिफ्रेश बटन का डिज़ाइन */
        .stButton>button {
            border-radius: 8px;
            font-weight: bold;
            transition: 0.3s;
        }
        .stButton>button:hover {
            border-color: #007bff;
            color: #007bff;
        }
        </style>
    """, unsafe_allow_html=True)

    st.header("📊 बिज़नेस समरी (Dashboard)")
    st.write("आपके पूरे ट्रांसपोर्ट बिज़नेस का 'लाइव' हिसाब-किताब एक ही जगह पर।")
    
    if st.button("🔄 रिफ्रेश करें (Refresh)"):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # --- सेक्शन 1: बैंक और नकद ---
    st.subheader("🏦 बैंक और नकद (Bank & Cash)")
    c1, c2, c3 = st.columns(3)
    c1.metric("💵 गल्ला (Cash)", f"₹ {get_ledger_balance('Cash_Ledger'):,}")
    c2.metric("🏦 Canara 311", f"₹ {get_ledger_balance('Canara_311_Ledger'):,}")
    c3.metric("🏦 Canara 41", f"₹ {get_ledger_balance('Canara_41_Ledger'):,}")

    c4, c5, c6 = st.columns(3)
    c4.metric("🏦 BOB (Bank of Baroda)", f"₹ {get_ledger_balance('BOB_Ledger'):,}")
    c5.metric("🏦 Canara 1747", f"₹ {get_ledger_balance('canara_1747'):,}")
    c6.empty() # जगह खाली रखने के लिए

    st.divider()

    # --- सेक्शन 2: खास खाते और पंप ---
    st.subheader("👤 खास खाते (Special Ledgers)")
    col1, col2, col3 = st.columns(3)
    col1.metric("इश्तियाक भाई (Ishtyaque)", f"₹ {get_ledger_balance('Ishtyaque_Ledger'):,}")
    col2.metric("यूनिवर्सल (Universal)", f"₹ {get_ledger_balance('Universal_Ledger'):,}")

    pump_bal = get_ledger_balance('Shekh_Filling_Ledger')
    if pump_bal < 0:
        col3.metric("⛽ शेख फिलिंग (Pump)", f"₹ {abs(pump_bal):,}", "- देना बाकी है ⏳", delta_color="inverse")
    elif pump_bal > 0:
        col3.metric("⛽ शेख फिलिंग (Pump)", f"₹ {pump_bal:,}", "+ एडवांस जमा है ✅", delta_color="normal")
    else:
        col3.metric("⛽ शेख फिलिंग (Pump)", f"₹ 0", "हिसाब क्लियर ✅", delta_color="off")

    st.divider()

    # --- सेक्शन 3: देनदारी (Payables) ---
    st.subheader("🚛 मार्केट की देनदारी (Market Payables)")
    truck_payable = get_truck_payable()
    
    # देनदारी वाले कार्ड को थोड़ा अलग दिखाने के लिए कॉलम का इस्तेमाल
    pay_col1, pay_col2 = st.columns([1, 2])
    with pay_col1:
        st.metric("🔴 गाड़ी वालों को कुल देना है", f"₹ {int(truck_payable):,}")
    with pay_col2:
        st.info("💡 नोट: गाड़ी वालों का पूरा 'डिटेल हिसाब' देखने के लिए साइड मेनू से 'लेना - देना (Outstanding)' पेज पर जाएँ।")

# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="Dashboard - Khan Transport ERP", layout="wide")
    show_dashboard_page()
