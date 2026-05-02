import streamlit as st
from supabase import create_client, Client

# Supabase Setup
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def show_migration_page():
    st.header("🚀 ALL-IN-ONE Data Migration (Final Fix)")
    st.warning("⚠️ यह टूल गायब ट्रिप्स, बैंक बैलेंस और पेट्रोल पंप का डेटा Google Sheets से लाएगा।")

    if st.button("🔥 START: गायब डेटा ट्रांसफर शुरू करें", type="primary"):
        with st.spinner("प्रोसेस शुरू हो रहा है... कृपया पेज बंद न करें।"):
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            import pandas as pd

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

            # 1. Banks & Petrol
            banks_map = {
                "Cash_Ledger": "Cash", "Canara_311_Ledger": "Canara 311",
                "Canara_41_Ledger": "Canara 41", "BOB_Ledger": "BOB",
                "canara_1747": "Canara 1747", "Shekh_Filling_Ledger": "Pump (Shekh Filling)"
            }

            for s_name, b_name in banks_map.items():
                st.write(f"🏦 {b_name} चेक हो रहा है...")
                try:
                    rows = db.worksheet(s_name).get_all_values()
                    if len(rows) > 1:
                        to_in = []
                        for r in rows[1:]:
                            if not r[0]: continue
                            amt = clean_num(r[-1])
                            if amt == 0: continue
                            to_in.append({
                                "bank_name": b_name, "date_val": clean_str(r[0]),
                                "trip_id": clean_str(r[1]) if len(r)>1 else "OLD",
                                "gr_no": clean_str(r[2]) if len(r)>2 else "N/A",
                                "description": clean_str(r[3]) if len(r)>3 else "Migration",
                                "amount": int(amt)
                            })
                        if to_in:
                            for i in range(0, len(to_in), 500):
                                supabase.table("bank_ledgers").insert(to_in[i:i+500]).execute()
                        st.success(f"✅ {b_name} सिंक हो गया।")
                except: pass

            # 2. Bookings (Upsert)
            st.write("📦 बुकिंग्स मिलान शुरू...")
            try:
                bk_sheet = db.worksheet("Bookings").get_all_values()
                if len(bk_sheet) > 1:
                    bk_rows = []
                    for r in bk_sheet[1:]:
                        if len(r) < 15 or not r[14]: continue
                        bk_rows.append({
                            "date_val": clean_str(r[0]), "from_loc": clean_str(r[1]), "company": clean_str(r[2]),
                            "owner_rate": clean_num(r[3]), "comp_rate": clean_num(r[4]), "weight": clean_num(r[5]),
                            "truck_no": clean_str(r[6]), "to_loc": clean_str(r[7]), "gr_no": clean_str(r[8]),
                            "uni_amt": int(clean_num(r[9])), "comments": clean_str(r[10]), "comp_freight": int(clean_num(r[11])),
                            "owner_freight": int(clean_num(r[12])), "final_uni_amt": int(clean_num(r[13])),
                            "trip_id": clean_str(r[14]), "ish_amt": int(clean_num(r[15])),
                            "gr_link": clean_str(r[16]) if len(r)>16 else None
                        })
                    for i in range(0, len(bk_rows), 500):
                        supabase.table("bookings").upsert(bk_rows[i:i+500], on_conflict="trip_id").execute()
                st.success("✅ बुकिंग्स सिंक हो गईं।")
            except: pass

            st.balloons()
            st.success("🎉 सारा डेटा अब सुरक्षित सुपबेस में है!")
