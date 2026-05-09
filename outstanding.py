import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 🗄️ DATABASE CONNECTION
# ==========================================

@st.cache_resource
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Khan_Transport_ERP")

def clean_amt(val):
    try:
        return float(str(val).replace(',','').replace('₹','').strip()) if str(val).strip() else 0
    except: return 0

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================

def show_outstanding_page():
    st.header("💸 लेना - देना (Outstanding Report)")
    st.write("यहाँ आप गाड़ी वालों का बाकी बकाया हिसाब देख सकते हैं।")

    if st.button("🔄 डेटा रिफ्रेश करें", type="primary"):
        st.cache_data.clear()
        st.rerun()

    try:
        with st.spinner("हिसाब किताब निकाला जा रहा है..."):
            db = connect_to_sheet()
            
            # 1. डेटा लोड करना
            bk_raw = db.worksheet("Bookings").get_all_values()
            adv_raw = db.worksheet("Advances").get_all_values()
            own_raw = db.worksheet("Owner_Ledger").get_all_values()

            df_bk = pd.DataFrame(bk_raw[1:], columns=bk_raw[0])
            
            # 2. एडवांस की मैपिंग
            adv_map = {}
            for r in adv_raw[1:]:
                if len(r) > 1:
                    tid = str(r[1]).strip()
                    # New schema: total at index 8. Old schema: amount at index 5.
                    amt_cell = r[8] if len(r) > 8 else (r[5] if len(r) > 5 else 0)
                    adv_map[tid] = adv_map.get(tid, 0) + clean_amt(amt_cell)

            # 3. लेजर एडजस्टमेंट (Shortage/Extra)
            own_map = {}
            for r in own_raw[1:]:
                if len(r) > 5:
                    tid = str(r[1]).strip()
                    desc = str(r[4])
                    if any(x in desc for x in ["Final Balance","Shortage","Extra","Detention"]):
                        own_map[tid] = own_map.get(tid, 0) + clean_amt(r[5])

            # 4. फाइनल लिस्ट तैयार करना
            report_data = []
            total_pending = 0

            for _, row in df_bk.iterrows():
                tid = str(row.iloc[14]).strip()
                truck = str(row.iloc[6])
                total_fr = clean_amt(row.iloc[12]) # Owner Freight
                munshiyana = clean_amt(row.iloc[13]) # Commission
                
                paid_adv = adv_map.get(tid, 0)
                other_adj = own_map.get(tid, 0)
                
                # फार्मूला: (कुल भाड़ा - मुंशीयाना) - दिया गया एडवांस + अन्य एडजस्टमेंट
                balance = (total_fr - munshiyana) - paid_adv + other_adj
                
                if balance > 10: # सिर्फ वो गाड़ियाँ जिनका 10 रुपये से ज्यादा बकाया है
                    report_data.append({
                        "तारीख": row.iloc[0],
                        "गाड़ी नंबर": truck,
                        "कहाँ तक": row.iloc[7],
                        "कुल भाड़ा": f"₹{total_fr:,.0f}",
                        "एडवांस भुगतान": f"₹{paid_adv:,.0f}",
                        "बकाया राशि": balance
                    })
                    total_pending += balance

            # 5. रिपोर्ट दिखाना
            if report_data:
                df_final = pd.DataFrame(report_data)
                st.error(f"🔴 कुल मार्केट बकाया: ₹{int(total_pending):,}")
                
                # टेबल को स्टाइल करना
                st.dataframe(
                    df_final.sort_values(by="बकाया राशि", ascending=False), 
                    use_container_width=True,
                    column_config={
                        "बकाया राशि": st.column_config.NumberColumn(format="₹%d")
                    }
                )
            else:
                st.success("✅ कोई पेमेंट बकाया नहीं है!")

    except Exception as e:
        st.error(f"रिपोर्ट लोड करने में एरर आया: {e}")
