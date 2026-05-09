import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 🗄️ DATABASE FUNCTIONS
# ==========================================

from sheet_utils import connect_to_sheet

@st.cache_data(ttl=5) 
def get_sheet_data_for_reports(sheet_name):
    try:
        db = connect_to_sheet()
        data = db.worksheet(sheet_name).get_all_values()
        return data if len(data) > 1 else []
    except: return []

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_reports_page():
    st.header("📑 बिज़नेस रिपोर्ट्स (Khan ERP)")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏦 खाता स्टेटमेंट", 
        "Master Report", 
        "🚚 सिंगल गाड़ी हिसाब", 
        "📅 आज का काम", 
        "💸 आज की पेमेंट्स", 
        "📄 डॉक्यूमेंट प्रिंट"
    ])

    # --- TAB 1: लेजर रिपोर्ट ---
    with tab1:
        st.markdown("### 📊 लेजर स्टेटमेंट")
        col1, col2, col3 = st.columns(3)
        with col1: 
            account_type = st.selectbox("खाता चुनें:", 
                ["Cash_Ledger", "Canara_311_Ledger", "Canara_41_Ledger", "BOB_Ledger", 
                 "Shekh_Filling_Ledger", "Company_Ledger", "Owner_Ledger", 
                 "Ishtyaque_Ledger", "Universal_Ledger", "canara_1747"])
        with col2: start_date = st.date_input("कब से?", datetime.date.today().replace(day=1), key="rep_start")
        with col3: end_date = st.date_input("कब तक?", datetime.date.today(), key="rep_end")

        if st.button("📊 स्टेटमेंट दिखाएं"):
            raw = get_sheet_data_for_reports(account_type)
            if raw:
                df = pd.DataFrame(raw[1:], columns=raw[0])
                date_col = df.columns[0]
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                mask = (df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)
                filtered = df.loc[mask].copy()
                if not filtered.empty:
                    # आखिरी कॉलम को अमाउंट मानकर टोटल निकालना
                    amt_col = filtered.columns[-1]
                    filtered[amt_col] = pd.to_numeric(filtered[amt_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    total_amt = filtered[amt_col].sum()
                    st.metric("नेट बैलेंस", f"₹{int(total_amt):,}")
                    st.dataframe(filtered, use_container_width=True)
                else: st.warning("इस तारीख के बीच कोई डेटा नहीं मिला।")

    # --- TAB 2: Master Report ---
    with tab2:
        if st.button("Load All Bookings"):
            raw_bk = get_sheet_data_for_reports("Bookings")
            if raw_bk: st.dataframe(pd.DataFrame(raw_bk[1:], columns=raw_bk[0]), use_container_width=True)

    # --- TAB 3: सिंगल गाड़ी पासबुक ---
    with tab3:
        st.markdown("### 🚚 गाड़ी का पक्का हिसाब")
        all_bk = get_sheet_data_for_reports("Bookings")
        if len(all_bk) > 1:
            data_bk = all_bk[1:][::-1]
            trip_options = [f"🚛 {r[6]} | GR: {r[8]} | ID: {r[14]}" for r in data_bk if len(r) > 14]
            selected = st.selectbox("गाड़ी खोजें:", ["चुनें..."] + trip_options)
            
            if selected != "चुनें...":
                sel_id = selected.split("ID: ")[1].strip()
                trip_row = [r for r in data_bk if len(r) > 14 and r[14] == sel_id][0]
                
                # भाड़ा और मुंशीयाना कैलकुलेशन
                owner_freight = int(float(str(trip_row[12]).replace(',', '') or 0))
                munshiyana = int(float(trip_row[5]) * 1) 
                
                # एडवांस का विवरण निकालना
                all_adv = get_sheet_data_for_reports("Advances")
                def adv_amount(row):
                    try:
                        if len(row) > 8:
                            return int(float(str(row[8]).replace(',', '') or 0))
                        if len(row) > 5:
                            return int(float(str(row[5]).replace(',', '') or 0))
                    except Exception:
                        return 0
                    return 0
                total_adv = sum(adv_amount(r) for r in all_adv[1:] if len(r) > 1 and r[1].strip() == sel_id)

                # फाइनल पेमेंट और POD लिंक
                all_bal = get_sheet_data_for_reports("Owner_Ledger")
                total_bal_paid, pod_link = 0, ""
                if all_bal:
                    for r in all_bal[1:]:
                        if len(r) > 5 and r[1].strip() == sel_id:
                            if "POD Link:" in str(r[4]): pod_link = str(r[4]).replace("POD Link:", "").strip()
                            if any(k in str(r[4]) for k in ["Final Balance", "Shortage", "Extra"]):
                                total_bal_paid += int(float(str(r[5]).replace(',', '') or 0))
                
                total_bal_paid = abs(total_bal_paid)
                rem_balance = (owner_freight - munshiyana) - total_adv - total_bal_paid

                st.write("---")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("कुल भाड़ा", f"₹{owner_freight:,}")
                c2.metric("मुंशीयाना (-)", f"₹{munshiyana:,}")
                c3.metric("कुल एडवांस", f"₹{total_adv:,}")
                c4.metric("बाकी बकाया", f"₹{rem_balance:,}")

                if pod_link: st.link_button("🏁 POD (रिसीविंग) कॉपी देखें", pod_link, use_container_width=True)

    # --- TAB 4: आज का काम ---
    with tab4:
        st.markdown("### 📅 आज का काम (Booking & Owner Payments)")
        rep_date = st.date_input("तारीख चुनें:", datetime.date.today(), key="daily_rep_date")
        s_date = rep_date.strftime('%Y-%m-%d')
        
        st.subheader("🚛 आज दिए गए एडवांस")
        all_adv = get_sheet_data_for_reports("Advances")
        if all_adv:
            today_adv = [r for r in all_adv[1:] if len(r) > 0 and r[0] == s_date]
            if today_adv:
                max_cols = max(len(r) for r in today_adv)
                norm_rows = [r + [""] * (max_cols - len(r)) for r in today_adv]
                df_today_adv = pd.DataFrame(norm_rows)
                show_cols = [i for i in [2, 3, 4, 5, 6, 7, 8] if i < df_today_adv.shape[1]]
                st.table(df_today_adv.iloc[:, show_cols])
            else: st.info("आज कोई एडवांस नहीं दिया गया।")

    # --- TAB 5: आज की पेमेंट्स (Cash Flow) ---
    with tab5:
        st.markdown("### 💸 आज की कुल पेमेंट्स (Day_Book)")
        pay_date = st.date_input("पेमेंट की तारीख चुनें:", datetime.date.today(), key="payment_date")
        s_pay_date = pay_date.strftime('%Y-%m-%d')
        
        if st.button("🔄 पेमेंट्स लोड करें", type="primary"):
            raw_daybook = get_sheet_data_for_reports("Day_Book") #
            if raw_daybook:
                df = pd.DataFrame(raw_daybook[1:], columns=raw_daybook[0])
                df_today = df[df[df.columns[0]] == s_pay_date]
                if not df_today.empty:
                    total_p = pd.to_numeric(df_today.iloc[:, 4].astype(str).str.replace(',', ''), errors='coerce').sum()
                    st.error(f"💸 कुल आउटफ्लो: ₹{total_p:,.2f}")
                    st.dataframe(df_today, use_container_width=True)
                else: st.info("कोई एंट्री नहीं मिली।")

    # --- TAB 6: डॉक्यूमेंट प्रिंट ---
    with tab6:
        st.markdown("### 🖨️ डॉक्यूमेंट प्रिंट (GR और POD)")
        search_gr = st.text_input("🔍 GR नंबर टाइप करें:")
        if search_gr:
            all_bk = get_sheet_data_for_reports("Bookings")
            found = next((r for r in all_bk[1:] if len(r) > 8 and str(r[8]).strip() == search_gr.strip()), None)
            if found:
                st.success(f"गाड़ी {found[6]} का डेटा मिल गया!")
                if len(found) > 16 and "http" in str(found[16]):
                    st.link_button("📄 GR प्रिंट करें", found[16].strip(), type="primary")
            else: st.error("GR नहीं मिली।")
