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

def get_all_trips():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def save_advance_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Advances").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

@st.cache_data(ttl=60)
def get_total_advance_for_trip(trip_id):
    try:
        db = connect_to_sheet()
        records = db.worksheet("Advances").get_all_values()
        return sum([int(float(row[8])) for row in records[1:] if len(row) > 8 and row[1] == trip_id])
    except: return 0

def save_advance_ledgers(date_val, trip_id, gr_no, dest, cash_amt, bank_amt, bank_name, diesel_amt, pump_name):
    try:
        db = connect_to_sheet()
        gr = str(gr_no) if gr_no else "N/A"
        base = [str(date_val), str(trip_id), gr, str(dest)]
        
        if int(cash_amt) > 0: db.worksheet("Cash_Ledger").append_row(base + [-int(cash_amt)], table_range="A1")
        
        if int(bank_amt) > 0:
            s_name = {"canara bank 311":"Canara_311_Ledger", "canara bank 41":"Canara_41_Ledger", "bob":"BOB_Ledger"}.get(bank_name)
            if s_name: db.worksheet(s_name).append_row(base + [-int(bank_amt)], table_range="A1")
            
        if int(diesel_amt) > 0: db.worksheet("Shekh_Filling_Ledger").append_row(base + [-int(diesel_amt)], table_range="A1")
        
        st.cache_data.clear()
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE (एडवांस पेज)
# ==========================================

def show_advance_page():
    st.markdown("""
        <style>
            div[data-testid="stForm"] > div > div { gap: 0.5rem; }
            .stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div > select { padding-top: 0.25rem; padding-bottom: 0.25rem; }
            .stMarkdown p { margin-bottom: 0.2rem; }
        </style>
    """, unsafe_allow_html=True)

    st.header("💸 गाड़ी का एडवांस (Advances)")

    if "adv_ck" not in st.session_state: st.session_state.adv_ck = 0
    if "show_adv_confirm" not in st.session_state: st.session_state.show_adv_confirm = False
    if "adv_saving_lock" not in st.session_state: st.session_state.adv_saving_lock = False
    
    c = st.session_state.adv_ck

    df = get_all_trips()
    if not df.empty:
        # 🟢 BUG FIXED: '.tail(20)' हटा दिया गया है ताकि पूरी लिस्ट आए
        df_last = df.iloc[::-1].copy()
        
        df_last['label'] = (
            "📅 " + df_last.iloc[:, 0].astype(str) + " | " + 
            "🚛 " + df_last.iloc[:, 6].astype(str) + " | " +
            "📄 GR: " + df_last.iloc[:, 8].astype(str) + " | " +
            "📍 " + df_last.iloc[:, 7].astype(str) + " | " + 
            "🆔 " + df_last.iloc[:, 14].astype(str)
        )

        st.info("💡 **टिप:** नीचे वाले डब्बे पर क्लिक करें और सीधे **GR नंबर** या **गाड़ी नंबर** टाइप करके सर्च करें।")
        selected = st.selectbox("🔍 गाड़ी खोजें (तारीख | गाड़ी | GR नंबर | कहाँ तक | ID)", ["चुनें..."] + df_last['label'].tolist(), key=f"sel_{c}")

        if selected != "चुनें...":
            row_data = df_last[df_last['label'] == selected].iloc[0]
            
            trip_id = row_data.iloc[14]; truck_no = row_data.iloc[6]; dest = row_data.iloc[7]; gr_no = row_data.iloc[8]     
            weight = float(row_data.iloc[5])  
            owner_total_freight = int(row_data.iloc[12])  

            munshiyana = weight * 1  
            net_freight = owner_total_freight - munshiyana
            max_limit = net_freight * 0.90 
            
            already_given = get_total_advance_for_trip(trip_id)
            remaining_limit = max_limit - already_given

            st.markdown("### 📊 गाड़ी का हिसाब-किताब")
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("कुल भाड़ा", f"₹{int(owner_total_freight):,}")
            col_b.metric("मुंशीयाना कटा", f"- ₹{int(munshiyana):,}")
            col_c.metric("देने की लिमिट (90%)", f"₹{int(max_limit):,}")
            
            if remaining_limit < 0:
                col_d.metric("अब तक दिया गया", f"₹{int(already_given):,}", delta=f"ओवर-पेमेंट: ₹{int(abs(remaining_limit)):,}", delta_color="inverse")
            else:
                col_d.metric("अब तक दिया गया", f"₹{int(already_given):,}", delta=f"बची हुई लिमिट: ₹{int(remaining_limit):,}", delta_color="normal")

            st.write("---")

            if not st.session_state.show_adv_confirm:
                with st.form(key=f"adv_form_{c}"):
                    adv_date = st.date_input("एडवांस की तारीख", datetime.date.today())

                    col1, col2 = st.columns(2)
                    with col1:
                        diesel_amt = st.number_input("डीज़ल (₹)", min_value=0, step=500)
                        pump_name = st.text_input("पंप का नाम (Optional)", value="shekh filling")
                    with col2:
                        cash_amt = st.number_input("नकद (Cash ₹)", min_value=0, step=500)
                        bank_amt = st.number_input("बैंक / FasTag (₹)", min_value=0, step=500)
                        bank_name = st.selectbox("किस बैंक खाते से दिया?", ["N/A", "canara bank 311", "canara bank 41", "bob"])

                    total_given = diesel_amt + cash_amt + bank_amt
                    st.info(f"🧾 **इस बार दिया जाने वाला कुल एडवांस:** ₹{int(total_given):,}")

                    submit_adv = st.form_submit_button("➡️ आगे बढ़ें (Next)")

                if submit_adv:
                    if total_given <= 0: st.error("⚠️ कृपया एडवांस का अमाउंट भरें!")
                    elif bank_amt > 0 and bank_name == "N/A": st.error("⚠️ बैंक अमाउंट डाला है, तो कृपया बैंक खाता भी चुनें!")
                    elif total_given > remaining_limit: st.error(f"⛔ **रुकिए!** आप लिमिट से ज़्यादा पैसा दे रहे हैं। आप इस गाड़ी को सिर्फ **₹{int(remaining_limit):,}** और दे सकते हैं।")
                    else:
                        st.session_state.adv_temp_data = {
                            "adv_date": adv_date, "diesel_amt": diesel_amt, "pump_name": pump_name,
                            "cash_amt": cash_amt, "bank_amt": bank_amt, "bank_name": bank_name,
                            "total_given": total_given, "trip_id": trip_id, "truck_no": truck_no,
                            "gr_no": gr_no, "dest": dest
                        }
                        st.session_state.show_adv_confirm = True
                        st.rerun()

            if st.session_state.show_adv_confirm:
                d = st.session_state.adv_temp_data
                st.warning(f"❓ क्या आप पक्का **₹{int(d['total_given']):,}** का एडवांस सेव करना चाहते हैं?")
                
                c1, c2 = st.columns([1, 4])
                
                if c1.button("👍 हाँ, सेव करें", type="primary"):
                    if st.session_state.adv_saving_lock:
                        st.toast("⏳ प्रोसेस हो रहा है, कृपया रुकें...")
                    else:
                        st.session_state.adv_saving_lock = True 
                        with st.spinner("⏳ डेटा सेव हो रहा है..."):
                            final_bank = d['bank_name'] if d['bank_amt'] > 0 else "N/A"
                            row = [str(d['adv_date']), str(d['trip_id']), str(d['truck_no']), int(d['diesel_amt']), d['pump_name'], int(d['cash_amt']), int(d['bank_amt']), final_bank, int(d['total_given'])]
                            
                            if save_advance_to_db(row):
                                save_advance_ledgers(d['adv_date'], d['trip_id'], d['gr_no'], d['dest'], d['cash_amt'], d['bank_amt'], final_bank, d['diesel_amt'], d['pump_name'])
                                st.success("✅ एडवांस सफलतापूर्वक सेव और खाते में अपडेट हो गया!")
                                time.sleep(1.5)
                                st.session_state.adv_saving_lock = False
                                st.session_state.show_adv_confirm = False
                                st.session_state.adv_ck += 1 
                                st.rerun()
                            else:
                                st.session_state.adv_saving_lock = False
                                st.error("❌ कुछ खराबी आ गई, सेव नहीं हो पाया।")
                            
                if c2.button("❌ कैंसिल"):
                    st.session_state.show_adv_confirm = False
                    st.rerun()
    else:
        st.info("कोई बुकिंग नहीं मिली। पहले गाड़ी लोड करें।")
