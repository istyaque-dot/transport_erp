import streamlit as st
from supabase import create_client, Client
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Supabase Setup
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def show_migration_page():
    st.header("🚀 ALL-IN-ONE Data Migration (Separate Accounts Fix)")
    st.warning("⚠️ यह टूल आपके सभी बैंक और नकद खातों को अलग-अलग टेबल में सिंक करेगा।")

    if st.button("🔥 START: सभी खातों का डेटा ट्रांसफर करें", type="primary"):
        with st.spinner("प्रोसेस शुरू हो रहा है... कृपया इंतज़ार करें।"):
            # Google Sheets Connection
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            db = gspread.authorize(creds).open("Khan_Transport_ERP")

            def clean_num(val):
                try: 
                    s = str(val).replace(',', '').replace('₹', '').strip()
                    return float(s) if s else 0.0
                except: return 0.0
            
            def clean_str(val):
                return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

            # --- खातों की मैपिंग (Sheet Name -> Supabase Table Name) ---
            separate_accounts = {
                "Cash_Ledger": "cash_ledger",
                "Canara_311_Ledger": "canara_311_ledger",
                "Canara_41_Ledger": "canara_41_ledger",
                "BOB_Ledger": "bob_ledger",
                "canara_1747": "canara_1747",
                "Shekh_Filling_Ledger": "shekh_filling_ledger"
            }

            for s_name, t_name in separate_accounts.items():
                st.write(f"📊 {s_name} का डेटा ट्रांसफर हो रहा है...")
                try:
                    rows = db.worksheet(s_name).get_all_values()
                    if len(rows) > 1:
                        to_in = []
                        for r in rows[1:]:
                            if not r[0]: continue
                            amt = clean_num(r[-1])
                            if amt == 0: continue
                            
                            # Canara 1747 का स्पेशल फॉर्मेट (4 कॉलम)
                            if t_name == "canara_1747":
                                to_in.append({
                                    "date_val": clean_str(r[0]),
                                    "description": clean_str(r[1]) if len(r)>1 else "",
                                    "to_from": clean_str(r[2]) if len(r)>2 else "",
                                    "amount": int(amt)
                                })
                            else:
                                # बाकी सभी के लिए स्टैंडर्ड फॉर्मेट
                                to_in.append({
                                    "date_val": clean_str(r[0]),
                                    "trip_id": clean_str(r[1]) if len(r)>1 else "OLD",
                                    "gr_no": clean_str(r[2]) if len(r)>2 else "N/A",
                                    "description": clean_str(r[3]) if len(r)>3 else "Migration",
                                    "amount": int(amt)
                                })
                        
                        if to_in:
                            # पुराने डेटा को साफ़ करके नया डालना (ताकि डबल न हो)
                            supabase.table(t_name).delete().neq("amount", 99999999).execute()
                            for i in range(0, len(to_in), 500):
                                supabase.table(t_name).insert(to_in[i:i+500]).execute()
                        st.success(f"✅ {s_name} की {len(to_in)} एंट्रीज़ सिंक हो गईं।")
                except Exception as e:
                    st.error(f"❌ {s_name} में एरर: {e}")

            st.balloons()
            st.success("🎉 बधाई हो! आपके सभी बैंक और नकद खाते अब अलग-अलग सुपबेस में सिंक हो गए हैं।")
