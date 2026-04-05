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
    st.header("💸 लेना और देना (Outstanding)")
    st.write("यहाँ मार्केट (पार्टी) से लेने वाला और गाड़ी वालों को देने वाला पूरा हिसाब एक साथ देखें।")

    db = connect_to_sheet()
    try:
        with st.spinner("सारा हिसाब कैलकुलेट हो रहा है..."):
            # डेटा लोड करना
            bk_raw = db.worksheet("Bookings").get_all_values()
            adv_raw = db.worksheet("Advances").get_all_values()
            own_raw = db.worksheet("Owner_Ledger").get_all_values()
            comp_raw = db.worksheet("Company_Ledger").get_all_values()
            
            # रिसीवेबल और POD शीट को भी लोड करना (ताकि कोई पेमेंट न छूटे)
            try: rec_raw = db.worksheet("Receivables").get_all_values()
            except: rec_raw = []
            try: pod_raw = db.worksheet("Company_PODs").get_all_values()
            except: pod_raw = []
            
            df_bk = pd.DataFrame(bk_raw[1:], columns=bk_raw[0])
            
            # 1. गाड़ी वालों का एडवांस
            adv_map = {}
            if len(adv_raw) > 1:
                for r in adv_raw[1:]:
                    if len(r) > 8:
                        tid = str(r[1]).strip()
                        adv_map[tid] = adv_map.get(tid, 0) + clean_amt(r[8])
                    
            # 2. गाड़ी वालों का फाइनल सेटलमेंट
            own_ledg_map = {}
            if len(own_raw) > 1:
                for r in own_raw[1:]:
                    if len(r) > 5:
                        tid = str(r[1]).strip()
                        desc = str(r[4])
                        if any(x in desc for x in ["Final Balance", "Shortage", "Extra", "Detention"]):
                            own_ledg_map[tid] = own_ledg_map.get(tid, 0) + clean_amt(r[5])

            # 3. कंपनी (पार्टी) का सेटलमेंट / आया हुआ पैसा (🟢 DOUBLE COUNTING BUG FIXED)
            comp_ledg_map = {}
            
            # A. Company Ledger से सिर्फ पेमेंट, TDS और शॉर्टेज उठाएं (भाड़ा नहीं)
            if len(comp_raw) > 1:
                for r in comp_raw[1:]:
                    if len(r) > 5:
                        tid = str(r[1]).strip()
                        desc = str(r[4])
                        if any(x in desc for x in ["Payment", "TDS", "Shortage", "Extra", "Detention"]):
                            comp_ledg_map[tid] = comp_ledg_map.get(tid, 0) + clean_amt(r[5])
            
            # B. Receivables शीट से आया हुआ पैसा जोड़ें
            if len(rec_raw) > 1:
                for r in rec_raw[1:]:
                    if len(r) > 4:
                        tid = str(r[1]).strip()
                        comp_ledg_map[tid] = comp_ledg_map.get(tid, 0) - clean_amt(r[4])
                        
            # C. Company PODs शीट से शॉर्टेज जोड़ें
            if len(pod_raw) > 1:
                for r in pod_raw[1:]:
                    if len(r) > 5:
                        tid = str(r[1]).strip()
                        comp_ledg_map[tid] = comp_ledg_map.get(tid, 0) - clean_amt(r[5])

            lena_data = []  # कंपनी से लेना है
            dena_data = []  # गाड़ी वालों को देना है
            total_lena = 0
            total_dena = 0

            for _, row in df_bk.iterrows():
                try:
                    tid = str(row.iloc[14]).strip()
                    date = str(row.iloc[0])
                    truck = str(row.iloc[6])
                    dest = str(row.iloc[7]) 
                    gr = str(row.iloc[8]) if str(row.iloc[8]).strip() != "" else "N/A"
                    comp_name = str(row.iloc[2])

                    # ==========================================
                    # 🟢 कंपनी/पार्टी से लेना है (Company Receivables)
                    # ==========================================
                    comp_fr = clean_amt(row.iloc[11])
                    comp_settlement = comp_ledg_map.get(tid, 0) # (TDS, Payment माइनस में होते हैं)
                    c_bal = comp_fr + comp_settlement 
                    comp_received = comp_fr - c_bal # कितना पैसा या टीडीएस कट/आ चुका है
                    
                    # 10% से ज्यादा रुका हो तभी लिस्ट में आएगा
                    if comp_fr > 0 and c_bal > (0.10 * comp_fr):
                        lena_data.append({
                            "तारीख": date,
                            "गाड़ी नंबर": truck,
                            "GR नंबर": gr,
                            "कहाँ तक": dest,
                            "कंपनी (पार्टी)": comp_name,
                            "कुल भाड़ा": int(comp_fr),
                            "आ चुका / कटा": int(comp_received),
                            "बाकी लेना है": int(c_bal)
                        })
                        total_lena += c_bal

                    # ==========================================
                    # 🔴 गाड़ी वालों को देना है (Owner Payables)
                    # ==========================================
                    own_fr = clean_amt(row.iloc[12])
                    munshiyana = clean_amt(row.iloc[5]) * 1
                    
                    adv_given = adv_map.get(tid, 0)
                    own_settlement = own_ledg_map.get(tid, 0) 
                    
                    o_bal = (own_fr - munshiyana) - adv_given + own_settlement
                    
                    if o_bal > 10: 
                        dena_data.append({
                            "तारीख": date,
                            "गाड़ी नंबर": truck,
                            "GR नंबर": gr,
                            "कहाँ तक": dest,
                            "कुल भाड़ा": int(own_fr),
                            "मुंशीयाना": int(munshiyana),
                            "कुल एडवांस": int(adv_given),
                            "बाकी देना है": int(o_bal)
                        })
                        total_dena += o_bal

                except Exception as e:
                    continue 

        # 🟢 डैशबोर्ड कार्ड्स (Cards)
        c1, c2 = st.columns(2)
        c1.metric("🟢 पार्टी/मार्केट से कुल लेना है (>10%)", f"₹ {int(total_lena):,}")
        c2.metric("🔴 गाड़ी वालों को कुल देना है", f"₹ {int(total_dena):,}")

        st.divider()

        # 🟢 टेबल्स (Tabs)
        t1, t2 = st.tabs(["🟢 कंपनियों / पार्टी से लेना है", "🔴 गाड़ी वालों को देना है"])

        with t1:
            st.subheader("🏢 मार्केट में फँसा पैसा (Receivables)")
            if lena_data:
                df_lena = pd.DataFrame(lena_data)
                df_lena = df_lena.sort_values(by=["तारीख", "गाड़ी नंबर"], ascending=[False, True])
                st.dataframe(df_lena, use_container_width=True, hide_index=True)
                
                csv_lena = df_lena.to_csv(index=False).encode('utf-8')
                st.download_button("📥 पार्टी लिस्ट डाउनलोड करें", csv_lena, "Party_Outstanding.csv", "text/csv", key="lena_dl")
            else:
                st.success("🎉 मार्केट में कोई बड़ा पेमेंट नहीं फँसा है! सब क्लियर है।")

        with t2:
            st.subheader("🚛 गाड़ी वालों का बकाया (Payables)")
            if dena_data:
                df_dena = pd.DataFrame(dena_data)
                df_dena = df_dena.sort_values(by=["तारीख", "गाड़ी नंबर"], ascending=[False, True])
                st.dataframe(df_dena, use_container_width=True, hide_index=True)
                
                csv_dena = df_dena.to_csv(index=False).encode('utf-8')
                st.download_button("📥 गाड़ी लिस्ट डाउनलोड करें", csv_dena, "Truck_Outstanding.csv", "text/csv", key="dena_dl")
            else:
                st.success("🎉 सब क्लियर है! किसी गाड़ी वाले का कोई बकाया नहीं है।")

    except Exception as e:
        st.error(f"डेटा लोड करने में दिक्कत आई: {e}")
