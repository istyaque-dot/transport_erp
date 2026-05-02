import streamlit as st
from supabase import create_client, Client
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Supabase Setup
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def show_migration_page():
    st.header("🚀 ALL-IN-ONE Data Migration (Fixing Errors)")
    st.info("यह कोड आपकी शीट के 'comapny' स्पेलिंग और खाली रोज़ को ऑटो-फिक्स करेगा।")

    if st.button("🔥 START: डेटा ट्रांसफर दोबारा शुरू करें", type="primary"):
        try:
            with st.spinner("गूगल शीट से हाथ मिलाया जा रहा है..."):
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
                client = gspread.authorize(creds)
                db = client.open("Khan_Transport_ERP")

            def clean_num(val):
                try: 
                    s = str(val).replace(',', '').replace('₹', '').strip()
                    return float(s) if s and s != '-' else 0.0
                except: return 0.0
            
            def clean_str(val):
                return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

            # --- 1. बुक़िंग्स सिंक (Bookings Fix) ---
            st.write("📦 बुकिंग्स चेक हो रही हैं...")
            bk_sheet = db.worksheet("Bookings")
            bk_df = pd.DataFrame(bk_sheet.get_all_records())
            
            if not bk_df.empty:
                # स्पेलिंग मिस्टेक फिक्स (comapny -> company)
                if 'comapny' in bk_df.columns:
                    bk_df.rename(columns={'comapny': 'company'}, inplace=True)
                
                bk_rows = []
                for _, r in bk_df.iterrows():
                    # Trip ID होना ज़रूरी है
                    tid = clean_str(r.get('trip number', ''))
                    if not tid: continue
                    
                    bk_rows.append({
                        "date_val": clean_str(r.get('date', '')),
                        "from_loc": clean_str(r.get('from', '')),
                        "company": clean_str(r.get('company', '')),
                        "owner_rate": clean_num(r.get('freight_truck', 0)),
                        "comp_rate": clean_num(r.get('freight_company', 0)),
                        "weight": clean_num(r.get('weight', 0)),
                        "truck_no": clean_str(r.get('truck_no', '')),
                        "to_loc": clean_str(r.get('destination', '')),
                        "gr_no": clean_str(r.get('gr number', '')),
                        "uni_amt": int(clean_num(r.get('universal amount', 0))),
                        "comp_freight": int(clean_num(r.get('total fright', 0))),
                        "owner_freight": int(clean_num(r.get('truck freight', 0))),
                        "trip_id": tid,
                        "ish_amt": int(clean_num(r.get('ishtyaque', 0)))
                    })
                
                if bk_rows:
                    for i in range(0, len(bk_rows), 100):
                        supabase.table("bookings").upsert(bk_rows[i:i+100], on_conflict="trip_id").execute()
                    st.success(f"✅ {len(bk_rows)} बुकिंग्स सुरक्षित पहुँच गईं।")

            # --- 2. अलग-अलग बैंक खाते (Bank Accounts) ---
            separate_accounts = {
                "Cash_Ledger": "cash_ledger",
                "Canara_311_Ledger": "canara_311_ledger",
                "Canara_41_Ledger": "canara_41_ledger",
                "BOB_Ledger": "bob_ledger",
                "canara_1747": "canara_1747",
                "Shekh_Filling_Ledger": "shekh_filling_ledger"
            }

            for s_name, t_name in separate_accounts.items():
                try:
                    st.write(f"🏦 {s_name} सिंक हो रहा है...")
                    rows = db.worksheet(s_name).get_all_values()
                    if len(rows) > 1:
                        to_in = []
                        for r in rows[1:]:
                            if not r[0]: continue
                            amt = clean_num(r[-1])
                            if amt == 0: continue
                            
                            if t_name == "canara_1747":
                                to_in.append({"date_val": clean_str(r[0]), "description": clean_str(r[1]), "to_from": clean_str(r[2]), "amount": int(amt)})
                            else:
                                to_in.append({
                                    "date_val": clean_str(r[0]), "trip_id": clean_str(r[1]) if len(r)>1 else "OLD",
                                    "gr_no": clean_str(r[2]) if len(r)>2 else "N/A", "description": clean_str(r[3]) if len(r)>3 else "Migration",
                                    "amount": int(amt)
                                })
                        
                        if to_in:
                            supabase.table(t_name).delete().neq("id", 0).execute() # पुराना साफ़ करें
                            for i in range(0, len(to_in), 200):
                                supabase.table(t_name).insert(to_in[i:i+200]).execute()
                            st.success(f"✅ {s_name} अपडेट हो गया।")
                except: st.warning(f"⚠️ {s_name} शीट नहीं मिली या खाली है।")

            st.balloons()
            st.success("🎉 मिशन पूरा हुआ! अब डेटा सुपबेस में चेक करें।")
            
        except Exception as e:
            st.error(f"❌ गड़बड़ हो गई: {str(e)}")
