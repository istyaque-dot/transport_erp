import json
import streamlit as st
import pandas as pd
import datetime
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
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏦 खाता स्टेटमेंट", "Master Report", "🚚 सिंगल गाड़ी हिसाब", "📅 आज का काम"])

    # --- TAB 1: Ledger Report ---
    with tab1:
        st.markdown("### 📊 लेजर स्टेटमेंट")
        col1, col2, col3 = st.columns(3)
        # 🟢 बदलाव: यहाँ ड्रॉपडाउन में 'canara_1747' जोड़ दिया गया है
        with col1: account_type = st.selectbox("खाता चुनें:", ["Cash_Ledger", "Canara_311_Ledger", "Canara_41_Ledger", "BOB_Ledger", "Shekh_Filling_Ledger", "Company_Ledger", "Owner_Ledger", "Ishtyaque_Ledger", "Universal_Ledger", "canara_1747"])
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
                    amt_col = filtered.columns[-1]
                    filtered[amt_col] = pd.to_numeric(filtered[amt_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    total_amt = filtered[amt_col].sum()
                    st.metric("नेट बैलेंस", f"₹{int(total_amt):,}")
                    csv_data = filtered.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Excel डाउनलोड करें", data=csv_data, file_name=f"{account_type}.csv", mime='text/csv')
                    filtered[date_col] = filtered[date_col].dt.strftime('%Y-%m-%d')
                    st.dataframe(filtered, use_container_width=True)
                else: st.warning("डेटा नहीं मिला।")

    # --- TAB 2: Master Report ---
    with tab2:
        if st.button("Load All Bookings"):
            raw_bk = get_sheet_data_for_reports("Bookings")
            if raw_bk: st.dataframe(pd.DataFrame(raw_bk[1:], columns=raw_bk[0]), use_container_width=True)

    # --- TAB 3: 🟢 SINGLE TRIP PASSBOOK (WITH MUNSHIYANA & WHATSAPP) ---
    with tab3:
        st.markdown("### 🚚 गाड़ी का पक्का हिसाब")
        all_bk = get_sheet_data_for_reports("Bookings")
        if len(all_bk) > 1:
            data_bk = all_bk[1:][::-1]
            trip_options = [f"🚛 {r[6]} | GR: {r[8]} | ID: {r[14]}" for r in data_bk]
            selected = st.selectbox("गाड़ी खोजें:", ["चुनें..."] + trip_options)
            
            if selected != "चुनें...":
                sel_id = selected.split("ID: ")[1].strip()
                trip_row = [r for r in data_bk if r[14] == sel_id][0]
                
                # Basic Details
                truck_no = trip_row[6]
                gr_no = trip_row[8]
                dest = trip_row[7]
                b_date = trip_row[0]
                weight = float(trip_row[5])
                owner_freight = int(float(str(trip_row[12]).replace(',', '')))
                
                # 🟢 MUNSHIYANA LOGIC (₹1 per qty)
                munshiyana = int(weight * 1)
                net_freight_after_munshiyana = owner_freight - munshiyana
                
                # Advance Calc
                all_adv = get_sheet_data_for_reports("Advances")
                total_adv = 0; adv_history = []
                if all_adv:
                    for r in all_adv[1:]:
                        if r[1].strip() == sel_id:
                            amt = int(float(str(r[8]).replace(',', '')))
                            total_adv += amt
                            adv_history.append({"तारीख": r[0], "विवरण": f"Dsl: {r[3]} | Cash: {r[5]} | Bank: {r[6]}", "अमाउंट": f"₹{amt:,}"})

                # Balance Calc (From Owner_PODs)
                all_bal = get_sheet_data_for_reports("Owner_PODs")
                total_bal_paid = 0
                if all_bal:
                    for r in all_bal[1:]:
                        if r[1].strip() == sel_id:
                            try: total_bal_paid += int(float(str(r[7]).replace(',', '')))
                            except: pass

                # Final Remaining
                rem_balance = net_freight_after_munshiyana - total_adv - total_bal_paid
                
                st.write("---")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("कुल भाड़ा", f"₹{owner_freight:,}")
                c2.metric("मुंशीयाना (-)", f"₹{munshiyana:,}")
                c3.metric("कुल एडवांस", f"₹{total_adv:,}")
                c4.metric("बाकी बकाया", f"₹{rem_balance:,}")
                
                if adv_history:
                    st.markdown("#### 📜 एडवांस पेमेंट हिस्ट्री")
                    st.table(pd.DataFrame(adv_history))

                # 🟢 WHATSAPP COPY BOX
                st.markdown("#### 📋 Copy for WhatsApp")
                msg = f"""*गाड़ी का हिसाब *
----------------------------
*गाड़ी नंबर:* {truck_no}
*GR नंबर:* {gr_no}
*तारीख:* {b_date}
*कहाँ तक:* {dest}
----------------------------
*कुल भाड़ा:* ₹{owner_freight:,}
*मुंशीयाना (-):* ₹{munshiyana:,}
*कुल एडवांस दिया:* ₹{total_adv:,}
*बैलेंस पेमेंट:* ₹{total_bal_paid:,}
----------------------------
*बाकी बकाया:* ₹{rem_balance:,}
----------------------------"""
                st.text_area("नीचे से कॉपी करें:", value=msg, height=300)
                st.info("💡 ऊपर दिए गए बॉक्स से टेक्स्ट कॉपी करके मालिक को भेज सकते हैं।")
        else:
            st.info("कोई बुकिंग उपलब्ध नहीं है।")

    # --- TAB 4: DAILY WORK SUMMARY ---
    with tab4:
        st.markdown("### 📅 आज का काम (Payment Summary)")
        rep_date = st.date_input("तारीख चुनें:", datetime.date.today(), key="daily_rep_date")
        s_date = rep_date.strftime('%Y-%m-%d')
        
        st.write("---")
        st.subheader("🚛 आज दिए गए एडवांस (Advances)")
        all_adv = get_sheet_data_for_reports("Advances")
        if all_adv:
            today_adv = [r for r in all_adv[1:] if r[0] == s_date]
            if today_adv:
                df_today_adv = pd.DataFrame(today_adv, columns=all_adv[0])
                st.table(df_today_adv[["truck_no", "Diesel_Amt", "Cash_Amt", "Bank_Amt", "Total_Advance"]])
                st.success(f"कुल एडवांस दिया: ₹{df_today_adv['Total_Advance'].astype(float).sum():,}")
            else: st.info("आज कोई एडवांस नहीं दिया गया।")
        
        st.write("---")
        st.subheader("🏁 आज किए गए फाइनल हिसाब (Balance Payment)")
        all_bal = get_sheet_data_for_reports("Owner_PODs")
        if all_bal:
            today_bal = [r for r in all_bal[1:] if r[0] == s_date]
            if today_bal:
                df_today_bal = pd.DataFrame(today_bal, columns=all_bal[0])
                st.table(df_today_bal[["Truck_No", "GR_No", "Balance_Paid", "Bank_Name"]])
                st.success(f"कुल बैलेंस पेमेंट किया: ₹{df_today_bal['Balance_Paid'].astype(float).sum():,}")
            else: st.info("आज कोई फाइनल हिसाब (Balance) नहीं हुआ।")
