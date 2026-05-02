import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from supabase import create_client, Client

# ==========================================
# 🔑 CONNECTIONS
# ==========================================
# Supabase
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Google Sheets
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    return gspread.authorize(creds).open("Khan_Transport_ERP")

# Helper to clean numbers
def clean_num(val):
    try:
        val = str(val).replace(',', '').strip()
        return float(val) if val else 0.0
    except: return 0.0

def clean_str(val):
    return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

# ==========================================
# 🚀 MIGRATION FUNCTIONS
# ==========================================
def migrate_bookings():
    st.info("📦 Bookings ट्रांसफर हो रही हैं...")
    db = connect_to_sheet()
    data = db.worksheet("Bookings").get_all_values()
    if len(data) <= 1: return st.warning("Bookings में डेटा नहीं है।")
    
    rows_to_insert = []
    for row in data[1:]: # Skip header
        if len(row) < 15 or not row[14]: continue # Skip if no trip_id
        
        b_dict = {
            "date_val": clean_str(row[0]), "from_loc": clean_str(row[1]), "company": clean_str(row[2]),
            "owner_rate": clean_num(row[3]), "comp_rate": clean_num(row[4]), "weight": clean_num(row[5]),
            "truck_no": clean_str(row[6]), "to_loc": clean_str(row[7]), "gr_no": clean_str(row[8]) or "N/A",
            "uni_amt": int(clean_num(row[9])), "comments": clean_str(row[10]) if len(row)>10 else "",
            "comp_freight": int(clean_num(row[11])) if len(row)>11 else 0,
            "owner_freight": int(clean_num(row[12])) if len(row)>12 else 0,
            "final_uni_amt": int(clean_num(row[13])) if len(row)>13 else 0,
            "trip_id": clean_str(row[14]),
            "ish_amt": int(clean_num(row[15])) if len(row)>15 else 0,
            "gr_link": clean_str(row[16]) if len(row)>16 and "http" in str(row[16]) else None
        }
        rows_to_insert.append(b_dict)
    
    # Bulk Insert in chunks of 500
    for i in range(0, len(rows_to_insert), 500):
        supabase.table("bookings").insert(rows_to_insert[i:i+500]).execute()
    st.success(f"✅ {len(rows_to_insert)} Bookings ट्रांसफर हो गईं!")

def migrate_standard_ledger(sheet_name, table_name):
    st.info(f"📒 {sheet_name} ट्रांसफर हो रहा है...")
    try:
        db = connect_to_sheet()
        data = db.worksheet(sheet_name).get_all_values()
        if len(data) <= 1: return
        
        rows_to_insert = []
        for row in data[1:]:
            if len(row) < 5: continue
            rows_to_insert.append({
                "date_val": clean_str(row[0]), "trip_id": clean_str(row[1]),
                "gr_no": clean_str(row[2]), "truck_no": clean_str(row[3]),
                "description": clean_str(row[4]), "amount": clean_num(row[5]) if len(row)>5 else 0
            })
            
        for i in range(0, len(rows_to_insert), 500):
            supabase.table(table_name).insert(rows_to_insert[i:i+500]).execute()
        st.success(f"✅ {len(rows_to_insert)} रोज़नामचा ({sheet_name}) ट्रांसफर हो गया!")
    except Exception as e:
        st.warning(f"⚠️ {sheet_name} शीट नहीं मिली या एरर: {e}")

# ==========================================
# 🖥️ UI
# ==========================================
st.set_page_config(page_title="Data Migration", layout="centered")
st.title("🚀 Google Sheets ➡️ Supabase Migration")
st.warning("⚠️ कृपया बटन को सिर्फ **एक ही बार** दबाएं, वरना डेटा डबल (Duplicate) हो जाएगा!")

if st.button("🔥 START: सारा डेटा एक साथ ट्रांसफर करें", type="primary", use_container_width=True):
    with st.spinner("डेटा कॉपी हो रहा है, कृपया इंतज़ार करें (1-2 मिनट लग सकते हैं)..."):
        # 1. Bookings
        migrate_bookings()
        
        # 2. All Ledgers
        ledgers_map = {
            "Company_Ledger": "company_ledger",
            "Owner_Ledger": "owner_ledger",
            "Universal_Ledger": "universal_ledger",
            "Ishtyaque_Ledger": "ishtyaque_ledger"
        }
        for sheet, table in ledgers_map.items():
            migrate_standard_ledger(sheet, table)
            
        st.balloons()
        st.success("🎉 बधाई हो! आपका सारा डेटा सफलतापूर्वक नए सुपरफास्ट सिस्टम में आ गया है!")
