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
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏦 खाता स्टेटमेंट", "Master Report", "🚚 सिंगल गाड़ी हिसाब", "📅 आज का काम", "📄 डॉक्यूमेंट प्रिंट"])

    # --- TAB 1: Ledger Report ---
    with tab1:
        st.markdown("### 📊 लेजर स्टेटमेंट")
        col1, col2, col3 = st.columns(3)
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

    # --- TAB 3: SINGLE TRIP PASSBOOK (WITH GR & POD TOGETHER) ---
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
                
                truck_no = trip_row[6]
                gr_no = trip_row[8]
                dest = trip_row[7]
                b_date = trip_row[0]
                weight = float(trip_row[5])
                owner_freight = int(float(str(trip_row[12]).replace(',', '')))
                
                munshiyana = int(weight * 1)
                net_freight_after_munshiyana = owner_freight - munshiyana
                
                all_adv = get_sheet_data_for_reports("Advances")
                total_adv = 0; adv_history = []
                if all_adv:
                    for r in all_adv[1:]:
                        if r[1].strip() == sel_id:
                            amt = int(float(str(r[8]).replace(',', '')))
                            total_adv += amt
                            adv_history.append({"तारीख": r[0], "विवरण": f"Dsl: {r[3]} | Cash: {r[5]} | Bank: {r[6]}", "अउंट": f"₹{amt:,}"})

                all_bal = get_sheet_data_for_reports("Owner_Ledger")
                total_bal_paid = 0
                pod_link = ""
                if all_bal:
                    for r in all_bal[1:]:
                        if len(r) > 5 and r[1].strip() == sel_id:
                            desc = str(r[4])
                            if "POD Link:" in desc:
                                pod_link = desc.replace("POD Link:", "").strip()
                            if "Final Balance" in desc or "Shortage" in desc or "Extra" in desc or "Detention" in desc:
                                try: total_bal_paid += int(float(str(r[5]).replace(',', '')))
                                except: pass
                total_bal_paid = abs(total_bal_paid)
                
                gr_link = ""
                if len(trip_row) > 16 and "http" in str(trip_row[16]):
                    gr_link = str(trip_row[16]).strip()

                rem_balance = net_freight_after_munshiyana - total_adv - total_bal_paid
                
                st.write("---")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("कुल भाड़ा", f"₹{owner_freight:,}")
                c2.metric("मुंशीयाना (-)", f"₹{munshiyana:,}")
                c3.metric("कुल एडवांस", f"₹{total_adv:,}")
                c4.metric("बाकी बकाया", f"₹{rem_balance:,}")
                
                if gr_link or pod_link:
                    st.write("---")
                    cc1, cc2 = st.columns(2)
                    if gr_link: cc1.link_button("📄 GR (बिल्टी) कॉपी देखें", gr_link, use_container_width=True)
                    if pod_link: cc2.link_button("🏁 POD (रिसीविंग) कॉपी देखें", pod_link, use_container_width=True)

                if adv_history:
                    st.markdown("#### 📜 एडवांस पेमेंट हिस्ट्री")
                    st.table(pd.DataFrame(adv_history))

                st.markdown("#### 📋 Copy for WhatsApp")
                link_text = ""
                if gr_link: link_text += f"\n*GR कॉपी:* {gr_link}"
                if pod_link: link_text += f"\n*POD कॉपी:* {pod_link}"
                
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
*सेटलमेंट / कटिंग:* ₹{total_bal_paid:,}
----------------------------
*बाकी बकाया:* ₹{rem_balance:,}
----------------------------{link_text}"""
                st.text_area("नीचे से कॉपी करें:", value=msg, height=350)
                st.info("💡 ऊपर बॉक्स से एक ही बार में हिसाब और दोनों कॉपियों (GR + POD) के लिंक कॉपी करें।")
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
        st.subheader("🏁 आज किए गए फाइनल हिसाब (Owner Ledger Entries)")
        all_bal = get_sheet_data_for_reports("Owner_Ledger")
        if all_bal:
            today_bal = [r for r in all_bal[1:] if r[0] == s_date and "POD Link:" not in str(r[4])]
            if today_bal:
                df_today_bal = pd.DataFrame(today_bal, columns=all_bal[0])
                st.table(df_today_bal[["Trip_ID", "Truck_No", "Description", "Credit_Debit_Amt"]])
            else: st.info("आज कोई फाइनल हिसाब (Balance) नहीं हुआ।")

    # --- TAB 5: 🟢 NAYA TAB (GR & POD PRINT) - SUPER FAST SEARCH ---
    with tab5:
        st.markdown("### 🖨️ डॉक्यूमेंट प्रिंट (GR और POD कॉपी)")
        st.write("GR नंबर दर्ज करें और एक ही जगह पर GR और POD दोनों की कॉपी पाएँ।")
        
        search_gr = st.text_input("🔍 GR नंबर टाइप करें (उदा. 5050) और Enter दबाएँ:")
        
        if search_gr:
            all_bk = get_sheet_data_for_reports("Bookings")
            found_trip = None
            
            if len(all_bk) > 1:
                for r in all_bk[1:]:
                    if str(r[8]).strip().lower() == search_gr.strip().lower():
                        found_trip = r
                        break
            
            if found_trip:
                sel_id = found_trip[14]
                st.success(f"✅ गाड़ी {found_trip[6]} (कहाँ तक: {found_trip[7]}) का डेटा मिल गया!")
                
                gr_link = None
                if len(found_trip) > 16 and "http" in str(found_trip[16]):
                    gr_link = str(found_trip[16]).strip()
                    
                pod_link = None
                owner_data = get_sheet_data_for_reports("Owner_Ledger")
                if owner_data:
                    for r in owner_data[1:]:
                        if len(r) > 4 and r[1].strip() == sel_id and "POD Link:" in str(r[4]):
                            pod_link = str(r[4]).replace("POD Link:", "").strip()
                            break
                
                st.write("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📄 GR (बिल्टी) कॉपी")
                    if gr_link:
                        st.link_button("🖨️ GR कॉपी प्रिंट करें / देखें", gr_link, type="primary", use_container_width=True)
                    else:
                        st.warning("⚠️ GR कॉपी अभी अपलोड नहीं है।")
                        
                with col2:
                    st.subheader("🏁 POD (रिसीविंग) कॉपी")
                    if pod_link:
                        st.link_button("🖨️ POD कॉपी प्रिंट करें / देखें", pod_link, type="primary", use_container_width=True)
                    else:
                        st.warning("⚠️ POD कॉपी अभी अपलोड नहीं है।")
            else:
                st.error("❌ इस GR नंबर से कोई गाड़ी नहीं मिली। कृपया सही नंबर टाइप करें।")
