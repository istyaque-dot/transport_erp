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
    # 🟢 CSS Injection (डब्बों के बीच खाली जगह कम करने के लिए)
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

    st.header("📥 कंपनी से पैसा आया (Receivables)")

    # 🟢 SESSION STATES (डबल क्लिक और फॉर्म क्लियर करने के लिए)
    if "rec_ck" not in st.session_state: st.session_state.rec_ck = 0
    if "show_rec_confirm" not in st.session_state: st.session_state.show_rec_confirm = False
    
    c = st.session_state.rec_ck

    df = get_all_trips()
    if not df.empty:
        df_last = df.tail(20).iloc[::-1].copy()
        df_last['label'] = (
            "📅 " + df_last.iloc[:, 0].astype(str) + " | " +
            "🚛 " + df_last.iloc[:, 6].astype(str) + " | " +
            "🏢 " + df_last.iloc[:, 2].astype(str) + " | " + 
            "📍 " + df_last.iloc[:, 7].astype(str) + " | " + 
            "🆔 " + df_last.iloc[:, 14].astype(str)
        )

        selected = st.selectbox("गाड़ी खोजें (तारीख | गाड़ी | कंपनी | कहाँ तक | ID)", ["चुनें..."] + df_last['label'].tolist(), key=f"sel_rec_{c}")

        if selected != "चुनें...":
            row_data = df_last[df_last['label'] == selected].iloc[0]
            trip_id = row_data[14]
            truck_no = row_data[6]
            comp_name = row_data[2]
            gr_no = row_data[8] if len(row_data) > 8 else "N/A" 
            
            comp_total = int(row_data[11]) 
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
            col_x.metric("✂️ Shortage कटी (POD)", f"- ₹{int(company_shortage):,}") 
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

            # 1. डेटा भरने वाला फॉर्म (सिर्फ तभी दिखेगा जब कन्फर्मेशन बंद हो)
            if not st.session_state.show_rec_confirm:
                with st.form(key=f"rec_form_{c}"):
                    rec_date = st.date_input("पैसा आने की तारीख", datetime.date.today())

                    col1, col2 = st.columns(2)
                    with col1:
                        received_amt = st.number_input("आया हुआ अमाउंट (₹)", min_value=0, value=int(max(0, ab_kitna_milega)), step=100)
                        bank_name = st.selectbox("किस खाते में आया?", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob"])
                    with col2:
                        remarks = st.text_input("Remarks / Reference No.")

                    submit_rec = st.form_submit_button("➡️ आगे बढ़ें (Next)")

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

            # 2. कन्फर्मेशन वाली स्क्रीन (बटन गायब करने वाला सिस्टम)
            if st.session_state.show_rec_confirm:
                d = st.session_state.rec_temp_data
                st.warning(f"❓ क्या आप पक्का **₹{int(d['received_amt']):,}** की एंट्री सेव करना चाहते हैं?")
                
                # 🟢 st.empty() का इस्तेमाल ताकि क्लिक करते ही बटन गायब हो जाएं
                action_container = st.empty()
                
                with action_container.container():
                    c1, c2 = st.columns([1, 4])
                    save_clicked = c1.button("👍 हाँ, सेव करें", type="primary")
                    cancel_clicked = c2.button("❌ कैंसिल")

                if save_clicked:
                    action_container.empty()  # क्लिक होते ही दोनों बटन तुरंत गायब!
                    with st.spinner("⏳ डेटा सेव हो रहा है, कृपया 2 सेकंड रुकें..."):
                        row = [str(d['rec_date']), str(d['trip_id']), str(d['truck_no']), str(d['comp_name']), int(d['received_amt']), d['bank_name'], 0, d['remarks']]
                        
                        if save_receivable_to_db(row):
                            save_receivable_ledgers(d['rec_date'], d['trip_id'], d['gr_no'], d['comp_name'], d['truck_no'], d['received_amt'], d['bank_name'])
                            st.success("✅ पेमेंट सफलतापूर्वक सेव और खाते में अपडेट हो गई!")
                            time.sleep(1.5)
                            # सब कुछ साफ़ कर दो
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
