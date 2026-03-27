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
        if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame()
    except: return pd.DataFrame()

def get_company_balance_details(trip_id):
    try:
        db = connect_to_sheet()
        comp_data = db.worksheet("Company_Ledger").get_all_values()
        total_balance = 0
        if len(comp_data) > 1:
            for row in comp_data[1:]:
                if len(row) > 5 and str(row[1]) == str(trip_id):
                    try: total_balance += int(float(str(row[5]).replace(',', '')))
                    except: pass
        return total_balance
    except: return 0

def save_company_payment(date_val, trip_id, gr_no, truck_no, pay_received, bank_name, shortage, extra_km, remarks):
    try:
        db = connect_to_sheet()
        if extra_km > 0:
            db.worksheet("Company_Ledger").append_row([str(date_val), trip_id, gr_no, truck_no, f"Detention/Extra: {remarks}", int(extra_km)])
        if shortage > 0:
            db.worksheet("Company_Ledger").append_row([str(date_val), trip_id, gr_no, truck_no, f"Shortage: {remarks}", -int(shortage)])
        if pay_received > 0:
            db.worksheet("Company_Ledger").append_row([str(date_val), trip_id, gr_no, truck_no, f"Payment Recvd: {remarks}", -int(pay_received)])
            
            s_map = {"Cash": "Cash_Ledger", "canara bank 311": "Canara_311_Ledger", "canara bank 41": "Canara_41_Ledger", "bob": "BOB_Ledger", "Canara 1747": "canara_1747"}
            s_name = s_map.get(bank_name)
            if s_name:
                if s_name == "canara_1747":
                    db.worksheet(s_name).append_row([str(date_val), f"Company Pay ({gr_no}) - {truck_no}", "From: Company", int(pay_received)], table_range="A1")
                else:
                    db.worksheet(s_name).append_row([str(date_val), trip_id, gr_no, f"Comp Pay: {truck_no} | {remarks}", int(pay_received)], table_range="A1")
        return True
    except: return False

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================
def show_company_page():
    st.header("🏢 कंपनी खाता और सेटलमेंट")
    st.write("यहाँ आप किसी भी GR का पेमेंट रिसीव कर सकते हैं और उसका हिसाब चुकता कर सकते हैं।")

    st.divider()

    # गाड़ी/GR सर्च और पेमेंट सेक्शन
    st.subheader("🔍 गाड़ी या GR का हिसाब करें")
    df_trips = get_all_trips()

    if not df_trips.empty:
        df_last = df_trips.tail(150).iloc[::-1]
        labels, trip_ids = [], []
        for _, row in df_last.iterrows():
            try:
                gr = str(row.iloc[8]) if str(row.iloc[8]) else "No GR"
                labels.append(f"GR: {gr} | 🚛 {row.iloc[6]} | 🏢 {row.iloc[2]} | 📅 {row.iloc[0]}")
                trip_ids.append(str(row.iloc[14]))
            except: pass
        
        selected_label = st.selectbox("गाड़ी या GR नंबर सर्च करें:", ["चुनें..."] + labels)
        
        if selected_label != "चुनें...":
            idx = labels.index(selected_label)
            selected_trip_id = trip_ids[idx]
            row_data = df_last[df_last.iloc[:, 14].astype(str) == selected_trip_id].iloc[0]
            
            gr_no = str(row_data.iloc[8])
            truck_no = str(row_data.iloc[6])
            company_name = str(row_data.iloc[2])
            
            # 🟢 गाड़ी की डिटेल और GR कॉपी का लिंक
            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**🏢 कंपनी:** {company_name}")
                st.write(f"**🚛 गाड़ी नंबर:** {truck_no}")
            with c2:
                if len(row_data) > 16 and pd.notna(row_data.iloc[16]) and "http" in str(row_data.iloc[16]):
                    st.success("✅ GR कॉपी अपलोड है")
                    st.link_button("📄 बिल्टी (GR) देखें", str(row_data.iloc[16]))
                else:
                    st.warning("⚠️ GR कॉपी अभी अपलोड नहीं है (बुकिंग एडिट से करें)")
                    
            # 🟢 लाइव बैलेंस मीटर (सिर्फ इस गाड़ी के लिए)
            comp_balance = get_company_balance_details(selected_trip_id)
            if comp_balance <= 0:
                st.success(f"✅ इस गाड़ी का कंपनी से हिसाब क्लियर है! (बैलेंस: ₹{comp_balance:,})")
            else:
                st.warning(f"💰 **इस गाड़ी का बकाया: ₹{comp_balance:,}**")
                
                with st.form("payment_form"):
                    st.write("👇 **पेमेंट, शॉर्टेज या एक्स्ट्रा KM चढ़ाएं:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        pay_rec = st.number_input("💵 पेमेंट प्राप्त हुआ (+ ₹)", min_value=0, step=100)
                        bank = st.selectbox("🏦 बैंक चुनें", ["N/A", "Cash", "canara bank 311", "canara bank 41", "bob", "Canara 1747"])
                        shortage = st.number_input("📉 शॉर्टेज / कटी (- ₹)", min_value=0, step=50)
                    with col2:
                        extra = st.number_input("📈 Detention/Extra (+ ₹)", min_value=0, step=100)
                        remark = st.text_input("📝 विवरण (e.g. UTR No.)")
                    
                    if st.form_submit_button("✅ हिसाब अपडेट करें", type="primary"):
                        if pay_rec > 0 and bank == "N/A":
                            st.error("⚠️ कृपया बैंक चुनें!")
                        elif pay_rec == 0 and shortage == 0 and extra == 0:
                            st.error("⚠️ कृपया कोई अमाउंट भरें!")
                        else:
                            with st.spinner("अपडेट हो रहा है..."):
                                t_date = str(datetime.date.today())
                                if save_company_payment(t_date, selected_trip_id, gr_no, truck_no, pay_rec, bank, shortage, extra, remark):
                                    st.cache_data.clear()
                                    st.success("✅ कंपनी खाता अपडेट हो गया!")
                                    time.sleep(1.5); st.rerun()
                                else: st.error("❌ एरर! गूगल शीट चेक करें।")
    else: st.info("कोई डेटा नहीं मिला।")
