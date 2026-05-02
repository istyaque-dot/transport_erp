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
    return client.open("Khan_Transport_ERP")

def get_all_trips():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame()
    except: return pd.DataFrame()

def save_advance_to_db(date_val, trip_id, truck_no, mode, remarks, amount):
    try:
        db = connect_to_sheet()
        # आपके Outstanding लॉजिक के हिसाब से अमाउंट 9वें कॉलम (Index 8) में होना चाहिए
        row_data = [str(date_val), str(trip_id), str(truck_no), str(mode), str(remarks), "", "", "", int(amount)]
        db.worksheet("Advances").append_row(row_data, table_range="A1")
        
        # अगर कैश या बैंक से पेमेंट हुआ है, तो उस लेज़र से भी पैसे काटने का लॉजिक यहाँ जोड़ सकते हैं (Optional)
        s_map = {
            "Cash": "Cash_Ledger", 
            "Canara 311": "Canara_311_Ledger", 
            "Canara 41": "Canara_41_Ledger", 
            "BOB": "BOB_Ledger", 
            "Canara 1747": "canara_1747",
            "Pump (Shekh Filling)": "Shekh_Filling_Ledger"
        }
        ledger_name = s_map.get(mode)
        if ledger_name:
            if mode == "Canara 1747":
                db.worksheet(ledger_name).append_row([str(date_val), "Advance", f"Truck: {truck_no}", -int(amount)], table_range="A1")
            else:
                db.worksheet(ledger_name).append_row([str(date_val), "Advance", "Debit", f"Truck: {truck_no} | {remarks}", -int(amount)], table_range="A1")
        
        st.cache_data.clear()
        return True
    except Exception as e:
        return False

# ==========================================
# 🖥️ USER INTERFACE (एडवांस पेज)
# ==========================================
def show_advance_page():
    # 🟢 11-INCH MAC COMPACT CSS (बिल्कुल बुकिंग पेज जैसा)
    st.markdown("""
        <style>
            .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
            h2 { font-size: 1.4rem !important; margin-bottom: 0 !important; padding-bottom: 0 !important; }
            h4 { font-size: 1.05rem !important; margin-bottom: 8px !important; color: #003399; }
            div[data-testid="stForm"] { padding: 20px !important; margin-bottom: 10px !important; }
            div[data-testid="stVerticalBlock"] { gap: 0.8rem !important; } 
            div[data-testid="stHorizontalBlock"] { gap: 0.8rem !important; }
            .stTextInput > div > div > input, 
            .stNumberInput > div > div > input, 
            .stSelectbox > div > div > select { 
                padding-top: 4px !important; padding-bottom: 4px !important; min-height: 2.2rem !important; font-size: 0.9rem !important;
            }
            label { font-size: 0.85rem !important; font-weight: 600 !important; margin-bottom: 2px !important; padding-bottom: 0px !important; }
            div[data-testid="stAlert"] { padding: 8px 12px !important; min-height: 35px !important; margin-top: 8px !important; margin-bottom: 8px !important;}
            .stButton > button { min-height: 2.2rem !important; padding: 2px 10px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.header("💸 एडवांस पेमेंट (Advance to Trucks)")
    
    df_trips = get_all_trips()
    
    if not df_trips.empty:
        # हाल ही की 50 गाड़ियां निकाल रहे हैं
        df_last = df_trips.tail(50).iloc[::-1]
        labels = []
        trip_ids = []
        truck_nos = []
        
        for _, row in df_last.iterrows():
            try:
                # Format: 🚛 UP 75AT8951 | 📅 2026-05-02 | 📍 Raebareily
                labels.append(f"🚛 {row.iloc[6]} | 📅 {row.iloc[0]} | 📍 {row.iloc[7]}")
                trip_ids.append(str(row.iloc[14]))
                truck_nos.append(str(row.iloc[6]))
            except: pass
        
        st.markdown("#### गाड़ी चुनें और एडवांस दें")
        selected_label = st.selectbox("गाड़ी चुनें (Select Trip):", ["चुनें..."] + labels)
        
        if selected_label != "चुनें...":
            idx = labels.index(selected_label)
            sel_trip_id = trip_ids[idx]
            sel_truck_no = truck_nos[idx]
            
            with st.form("advance_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    adv_date = st.date_input("तारीख (Date)", datetime.date.today())
                with col2:
                    adv_amount = st.number_input("एडवांस अमाउंट (₹)", min_value=0, step=500)
                with col3:
                    pay_mode = st.selectbox("पेमेंट मोड (Mode)", ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747", "Pump (Shekh Filling)", "Other"])
                
                col4, col5 = st.columns([2, 1])
                with col4:
                    remarks = st.text_input("विवरण (Remarks / UTR No.)")
                with col5:
                    st.markdown("<br>", unsafe_allow_html=True)
                    submitted = st.form_submit_button("💾 एडवांस सेव करें", use_container_width=True)
                
                if submitted:
                    if adv_amount <= 0:
                        st.error("⚠️ कृपया सही अमाउंट दर्ज करें!")
                    else:
                        with st.spinner("⏳ एडवांस सेव हो रहा है..."):
                            if save_advance_to_db(adv_date, sel_trip_id, sel_truck_no, pay_mode, remarks, adv_amount):
                                st.success(f"✅ गाड़ी {sel_truck_no} को ₹{adv_amount:,} का एडवांस सफलतापूर्वक सेव हो गया!")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("❌ एडवांस सेव करने में दिक्कत आई।")
    else:
        st.info("⚠️ सिस्टम में कोई बुकिंग नहीं मिली। कृपया पहले 'बुकिंग' पेज से गाड़ी लगाएँ।")
