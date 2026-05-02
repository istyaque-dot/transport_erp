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

# ⚠️ यहाँ से cache हटा दिया ताकि लिस्ट तुरंत अपडेट हो
def get_all_trips():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def save_receivable_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Receivables").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

@st.cache_data(ttl=60)
def get_total_received_for_trip(trip_id):
    try:
        db = connect_to_sheet()
        records = db.worksheet("Receivables").get_all_values()
        return sum([int(float(row[4])) for row in records[1:] if len(row) > 4 and row[1] == trip_id])
    except: return 0

@st.cache_data(ttl=60)
def get_company_shortage(trip_id):
    try:
        db = connect_to_sheet()
        records = db.worksheet("Company_PODs").get_all_values()
        return sum([int(float(row[5])) for row in records[1:] if len(row) > 5 and row[1] == trip_id])
    except: return 0

def save_receivable_ledgers(date_val, trip_id, gr_no, comp_name, truck_no, received_amt, bank_name):
    try:
        db = connect_to_sheet()
        desc = f"{comp_name} | {truck_no}"
        base = [str(date_val), str(trip_id), str(gr_no), desc]
        
        s_name = {
            "Cash": "Cash_Ledger", 
            "canara bank 311": "Canara_311_Ledger", 
            "canara bank 41": "Canara_41_Ledger", 
            "bob": "BOB_Ledger"
        }.get(bank_name)
        
        if s_name:
            db.worksheet(s_name).append_row(base + [int(received_amt)], table_range="A1")
            
        st.cache_data.clear()
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE (रिसीवेबल पेज)
# ==========================================

def show_receivable_page():
    # 🟢 11-INCH MAC COMPACT CSS
    st.markdown("""
        <style>
            .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
            h2 { font-size: 1.4rem !important; margin-bottom: 0 !important; padding-bottom: 0 !important; }
            h3 { font-size: 1.1rem !important; margin-bottom: 5px !important; padding-bottom: 0px !important;}
            h4 { font-size: 1.05rem !important; margin-bottom: 8px !important; color: #003399; }
            
            div[data-testid="stForm"] { padding: 15px !important; margin-bottom: 10px !important; }
            div[data-testid="stVerticalBlock"] { gap: 0.6rem !important; } 
            div[data-testid="stHorizontalBlock"] { gap: 0.6rem !important; }
            
            .stTextInput > div > div > input, 
            .stNumberInput > div > div > input, 
            .stSelectbox > div > div > select { 
                padding-top: 4px !important; 
                padding-bottom: 4px !important; 
                min-height: 2.2rem !important; 
                font-size: 0.9rem !important;
            }
            
            label { font-size: 0.85rem !important; font-weight: 600 !important; margin-bottom: 2px !important; padding-bottom: 0px !important; }
            
            div[data-testid="stAlert"] { padding: 8px 12px !important; min-height: 35px !important; margin-top: 8px !important; margin-bottom: 8px !important;}
            div[data-testid="stAlert"] p { font-size: 0.9rem !important; margin: 0px !important; }
            
            div[data-testid="metric-container"] {
                background-color: #ffffff; border: 1px solid #e0e0e0;
                padding: 5px 10px; border-radius: 8px;
                box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
            }
            @media (prefers-color-scheme: dark) {
                div[data-testid="metric-container"] { background-color: #1e1e1e; border-color: #333; }
            }
            div[data-testid="stMetricValue"] { font-size: 1.1rem !important; }
            
            hr { margin: 0.6em 0px !important; }
            .stButton > button { min-height: 2.2rem !important; padding: 2px 10px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.header("📥 कंपनी से पैसा आया (Receivables)")

    # 🟢 SESSION STATES 
    if "rec_ck" not in st.session_state: st.session_state.rec_ck = 0
    if "show_rec_confirm" not in st.session_state: st.session_state.show_rec_confirm = False
    
    c = st.session_state.rec_ck

    df = get_all_trips()
    if not df.empty:
        df_last = df.iloc[::-1].copy()
        
        df_last['label'] = (
            "📅 " + df_last.iloc[:, 0].astype(str) + " | " +
            "🚛 " + df_last.iloc[:, 6].astype(str) + " | " +
            "🏢 " + df_last.iloc[:, 2].astype(str) + " | " + 
            "📄 GR: " + df_last.iloc[:, 8].astype(str) + " | " +
            "📍 " + df_last.iloc[:, 7].astype(str) + " | " + 
            "🆔 " + df_last.iloc[:, 14].astype(str)
        )

        st.info("💡 **टिप:** नीचे क्लिक करें और सीधे **GR नंबर**, **गाड़ी नंबर** या **कंपनी** का नाम टाइप करके सर्च करें।")
        selected = st.selectbox("🔍 गाड़ी खोजें (तारीख | गाड़ी | GR नंबर | कंपनी | कहाँ तक)", ["चुनें..."] + df_last['label'].tolist(), key=f"sel_rec_{c}", label_visibility="collapsed")

        if selected != "चुनें...":
            row_data = df_last[df_last['label'] == selected].iloc[0]
            
            trip_id = str(row_data.iloc[14])
            truck_no = str(row_data.iloc[6])
            comp_name = str(row_data.iloc[2])
            gr_no = str(row_data.iloc[8]) if len(row_data) > 8 else "N/A" 
            
            comp_total = int(row_data.iloc[11]) 
            tds_amount = comp_total * 0.01 
            company_shortage = get_company_shortage(trip_id)
            net_receivable = comp_total - tds_amount - company_shortage
            
            ten_percent_exact = comp_total * 0.10
            ruka_hua_paisa = int(ten_percent_exact // 100) * 100 
            already_received = get_total_received_for_trip(trip_id)
            pending_balance = net_receivable - already_received

            if pending_balance > ruka_hua_paisa:
                ab_kitna_milega = pending_balance - ruka_hua_paisa
                balance_msg = "TDS, शॉर्टेज, और 10% रोक काटकर"
            else:
                ab_kitna_milega = pending_balance
                balance_msg = "सिर्फ रुका हुआ बैलेंस बाकी है"

            st.markdown("### 📊 पार्टी/कंपनी बिल का हिसाब")
            col_a, col_b, col_c, col_x = st.columns(4)
            col_a.metric("💰 Total Bill", f"₹{int(comp_total):,}")
            col_b.metric("📉 TDS कटी (1%)", f"- ₹{int(tds_amount):,}")
            col_x.metric("✂️ Shortage कटी", f"- ₹{int(company_shortage):,}") 
            col_c.metric("🔒 10% रोक", f"- ₹{int(ruka_hua_paisa):,}")
            
            st.markdown("#### 💸 इस वक़्त का पेमेंट स्टेटस")
            col_d, col_e, col_f = st.columns(3)
            col_d.metric("📥 अब तक आ चुका है", f"₹{int(already_received):,}")
            
            if pending_balance <= 0:
                col_e.metric("कुल बाकी (Total Pending)", f"₹0")
                col_f.metric("🟢 अब कितना मिलेगा", f"₹0", "हिसाब क्लियर ✅", delta_color="normal")
            else:
                col_e.metric("कुल बाकी (Total Pending)", f"₹{int(pending_balance):,}")
                col_f.metric("🟢 अब कितना मिलेगा", f"₹{int(max(0, ab_kitna_milega)):,}", balance_msg, delta_color="normal")

            st.write("---")

            # 1. डेटा भरने वाला फॉर्म (Compact)
            if not st.session_state.show_rec_confirm:
                with st.form(key=f"rec_form_{c}"):
                    # 🟢 फॉर्म को 3-कॉलम और 1-कॉलम में बाँटा ताकि जगह कम ले
                    col1, col2, col3 = st.columns([1, 1, 1.5])
                    with col1:
                        rec_date = st.date_input("तारीख", datetime.date.today())
                    with col2:
                        received_amt = st.number_input("अमाउंट (₹)", min_value=0, value=int(max(0, ab_kitna_milega)), step=100)
                    with col3:
                        bank_name = st.selectbox("खाता", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])
                        
                    remarks = st.text_input("Remarks / Reference No.")

                    submit_rec = st.form_submit_button("➡️ सेव करने के लिए आगे बढ़ें", use_container_width=True)

                if submit_rec:
                    if received_amt <= 0:
                        st.error("⚠️ कृपया Received Amount भरें!")
                    elif received_amt > 0 and bank_name == "N/A":
                        st.error("⚠️ अमाउंट डाला है तो कृपया बैंक खाता भी चुनें!")
                    elif received_amt > pending_balance:
                        st.error(f"⛔ **रुकिए!** अमाउंट कुल पेंडिंग से ज़्यादा नहीं हो सकता।")
                    else:
                        st.session_state.rec_temp_data = {
                            "rec_date": rec_date, "received_amt": received_amt, 
                            "bank_name": bank_name, "remarks": remarks,
                            "trip_id": trip_id, "truck_no": truck_no, 
                            "comp_name": comp_name, "gr_no": gr_no
                        }
                        st.session_state.show_rec_confirm = True
                        st.rerun()

            # 2. कन्फर्मेशन वाली स्क्रीन
            if st.session_state.show_rec_confirm:
                d = st.session_state.rec_temp_data
                st.warning(f"❓ क्या आप पक्का **₹{int(d['received_amt']):,}** की एंट्री सेव करना चाहते हैं?")
                
                action_container = st.empty()
                
                with action_container.container():
                    c1, c2 = st.columns([1, 4])
                    save_clicked = c1.button("👍 हाँ, सेव करें", type="primary")
                    cancel_clicked = c2.button("❌ कैंसिल")

                if save_clicked:
                    action_container.empty() 
                    with st.spinner("⏳ डेटा सेव हो रहा है..."):
                        row = [str(d['rec_date']), str(d['trip_id']), str(d['truck_no']), str(d['comp_name']), int(d['received_amt']), d['bank_name'], 0, d['remarks']]
                        
                        if save_receivable_to_db(row):
                            save_receivable_ledgers(d['rec_date'], d['trip_id'], d['gr_no'], d['comp_name'], d['truck_no'], d['received_amt'], d['bank_name'])
                            st.success("✅ पेमेंट सफलतापूर्वक सेव और खाते में अपडेट हो गई!")
                            time.sleep(1.5)
                            st.session_state.show_rec_confirm = False
                            st.session_state.rec_ck += 1 
                            st.rerun()
                        else:
                            st.error("❌ कुछ खराबी आ गई, सेव नहीं हो पाया।")
                            
                if cancel_clicked:
                    st.session_state.show_rec_confirm = False
                    st.rerun()
    else:
        st.info("कोई बुकिंग नहीं मिली। पहले गाड़ी लोड करें।")
