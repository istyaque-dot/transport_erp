import streamlit as st
from supabase import create_client, Client
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# सुपबेस सेटअप
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def show_migration_page():
    st.header("🚀 ALL-IN-ONE Data Migration (Direct Sync)")

    if st.button("🔥 START: डेटा सिंक करें", type="primary"):
        with st.spinner("प्रोसेस चल रहा है..."):
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
            db = gspread.authorize(creds).open("Khan_Transport_ERP")

            # 1. Bookings सिंक
            st.write("📦 बुकिंग्स सिंक हो रही हैं...")
            bk_data = db.worksheet("Bookings").get_all_records()
            bk_rows = []
            for r in bk_data:
                if not r.get('trip number'): continue
                bk_rows.append({
                    "date": str(r.get('date', '')),
                    "from_loc": str(r.get('from', '')),
                    "comapny": str(r.get('comapny', '')),
                    "freight_truck": float(str(r.get('freight_truck', 0)).replace(',', '') or 0),
                    "freight_company": float(str(r.get('freight_company', 0)).replace(',', '') or 0),
                    "weight": float(str(r.get('weight', 0)).replace(',', '') or 0),
                    "truck_no": str(r.get('truck_no', '')),
                    "destination": str(r.get('destination', '')),
                    "gr_number": str(r.get('gr number', '')),
                    "universal_amount": int(float(str(r.get('universal amount', 0)).replace(',', '') or 0)),
                    "connect_person": str(r.get('connect person', '')),
                    "total_fright": int(float(str(r.get('total fright', 0)).replace(',', '') or 0)),
                    "truck_freight": int(float(str(r.get('truck freight', 0)).replace(',', '') or 0)),
                    "universal_payment": int(float(str(r.get('universal payment', 0)).replace(',', '') or 0)),
                    "trip_number": str(r.get('trip number', '')),
                    "ishtyaque": int(float(str(r.get('ishtyaque', 0)).replace(',', '') or 0)),
                    "gr_link": str(r.get('', '')) # Q कॉलम का लिंक
                })
            if bk_rows:
                supabase.table("bookings").upsert(bk_rows, on_conflict="trip_number").execute()
                st.success(f"✅ {len(bk_rows)} बुकिंग्स सिंक हो गईं।")

            # इसी तरह बाकी बैंक टेबल्स के लिए कोड चलेगा...
            st.balloons()
