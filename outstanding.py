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

# ==========================================
# 🖥️ USER INTERFACE
# ==========================================
def show_outstanding_page():
    st.header("💸 गाड़ी मालिकों का बकाया (Truck-wise Payables)")
    st.write("यहाँ हर गाड़ी का कुल भाड़ा, एडवांस और बचा हुआ बैलेंस एक साथ देखें।")

    db = connect_to_sheet()
    try:
        # डेटा लोड करना
        bk_raw = db.worksheet("Bookings").get_all_values()
        adv_raw = db.worksheet("Advances").get_all_values()
        own_raw = db.worksheet("Owner_Ledger").get_all_values()
        
        df_bk = pd.DataFrame(bk_raw[1:], columns=bk_raw[0])
        
        # एडवांस और लेजर को डिक्शनरी में डालना (फास्ट सर्च के लिए)
        adv_map = {}
        if len(adv_raw) > 1:
            for r in adv_raw[1:]:
                if len(r) > 8:
                    tid = str(r[1]).strip()
                    adv_map[tid] = adv_map.get(tid, 0) + clean_amt(r[8])
                
        ledg_map = {}
        if len(own_raw) > 1:
            for r in own_raw[1:]:
                if len(r) > 5:
                    tid = str(r[1]).strip()
                    ledg_map[tid] = ledg_map.get(tid, 0) + clean_amt(r[5])

        dena_data = []
        total_payable = 0

        for _, row in df_bk.iterrows():
            try:
                tid = str(row.iloc[14]).strip()
                truck = str(row.iloc[6])
                dest = str(row.iloc[7]) # 🟢 नया: कहाँ तक (Destination)
                gr = str(row.iloc[8]) if str(row.iloc[8]).strip() != "" else "N/A" # 🟢 नया: GR नंबर
                
                # मालिक का कुल भाड़ा
                total_fr = clean_amt(row.iloc[12])
                # मुंशीयाना (वजन * 1 रुपये)
                munshiyana = clean_amt(row.iloc[5]) * 1
                
                adv_given = adv_map.get(tid, 0)
                settlement = ledg_map.get(tid, 0) # शॉर्टेज या एक्स्ट्रा
                
                # असली बकाया = (कुल भाड़ा - मुंशीयाना) - एडवांस + सेटलमेंट
                balance = (total_fr - munshiyana) - adv_given + settlement
                
                if balance > 10: # 10 रुपये से ज्यादा का ही बकाया दिखाएगा
                    dena_data.append({
                        "गाड़ी नंबर": truck,
                        "तारीख": row.iloc[0],
                        "GR नंबर": gr,        # 🟢 लिस्ट में जोड़ा गया
                        "कहाँ तक": dest,      # 🟢 लिस्ट में जोड़ा गया
                        "कुल भाड़ा": int(total_fr),
                        "मुंशीयाना": int(munshiyana),
                        "कुल एडवांस": int(adv_given),
                        "बाकी बकाया": int(balance)
                    })
                    total_payable += balance
            except:
                continue # अगर किसी लाइन में डेटा खाली हो तो उसे छोड़ दे

        # डिस्प्ले कार्ड
        st.metric("🔴 गाड़ी वालों को कुल देना है", f"₹ {int(total_payable):,}")
        
        if dena_data:
            df_dena = pd.DataFrame(dena_data)
            # 🟢 गाड़ी नंबर के हिसाब से ग्रुप करना (नई तारीख पहले)
            df_dena = df_dena.sort_values(by=["तारीख", "गाड़ी नंबर"], ascending=[False, True])
            st.dataframe(df_dena, use_container_width=True, hide_index=True)
            
            # एक्सेल डाउनलोड
            csv = df_dena.to_csv(index=False).encode('utf-8')
            st.download_button("📥 पूरी लिस्ट डाउनलोड करें", csv, "Truck_Outstanding.csv", "text/csv")
        else:
            st.success("सब क्लियर है! किसी गाड़ी वाले का कोई बकाया नहीं है।")

    except Exception as e:
        st.error(f"डेटा लोड करने में दिक्कत आई: {e}")
