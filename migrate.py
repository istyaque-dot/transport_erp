elif choice == "🛠️ Admin: Data Migration":
        st.header("🚀 ALL-IN-ONE Data Migration (Fix)")
        st.warning("⚠️ यह टूल छूटा हुआ सारा डेटा (Banks, Petrol, Trips) दोबारा भरेगा।")

        if st.button("🔥 START: छूटा हुआ सारा डेटा ट्रांसफर करें", type="primary"):
            with st.spinner("एक-एक करके सारी शीट्स चेक हो रही हैं..."):
                import gspread
                from oauth2client.service_account import ServiceAccountCredentials
                import pandas as pd

                # Connection
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
                db = gspread.authorize(creds).open("Khan_Transport_ERP")

                def clean_num(val):
                    try: return float(str(val).replace(',', '').replace('₹', '').strip()) if val else 0.0
                    except: return 0.0
                def clean_str(val):
                    return str(val).strip() if pd.notna(val) and str(val).lower() != "nan" else ""

                # --- 1. बैंक और नकद (Bank Ledgers) ---
                # आपकी शीट के नाम: Cash_Ledger, Canara_311_Ledger, Canara_41_Ledger, BOB_Ledger, canara_1747, Shekh_Filling_Ledger
                banks_map = {
                    "Cash_Ledger": "Cash",
                    "Canara_311_Ledger": "Canara 311",
                    "Canara_41_Ledger": "Canara 41",
                    "BOB_Ledger": "BOB",
                    "canara_1747": "Canara 1747",
                    "Shekh_Filling_Ledger": "Pump (Shekh Filling)"
                }

                for s_name, b_name in banks_map.items():
                    st.write(f"🏦 {b_name} का डेटा ला रहे हैं...")
                    try:
                        rows = db.worksheet(s_name).get_all_values()
                        if len(rows) > 1:
                            to_insert = []
                            for r in rows[1:]:
                                # बैंक लेजर में आमतौर पर 4 या 5 कॉलम होते हैं
                                # हम आखिरी कॉलम को Amount मानेंगे
                                amt = clean_num(r[-1])
                                if amt == 0: continue
                                
                                to_insert.append({
                                    "bank_name": b_name,
                                    "date_val": clean_str(r[0]),
                                    "trip_id": clean_str(r[1]) if len(r)>1 else "OLD",
                                    "gr_no": clean_str(r[2]) if len(r)>2 else "N/A",
                                    "description": clean_str(r[3]) if len(r)>3 else "Old Entry",
                                    "amount": int(amt)
                                })
                            # 500-500 के टुकड़ों में अपलोड
                            for i in range(0, len(to_insert), 500):
                                supabase.table("bank_ledgers").insert(to_insert[i:i+500]).execute()
                            st.success(f"✅ {b_name} के {len(to_insert)} रिकॉर्ड आ गए।")
                    except: st.error(f"❌ {s_name} नहीं मिली।")

                # --- 2. छूटी हुई बुकिंग्स (Bookings) ---
                st.write("📦 सभी Bookings दोबारा चेक हो रही हैं...")
                bk_data = db.worksheet("Bookings").get_all_values()
                if len(bk_data) > 1:
                    bk_rows = []
                    for r in bk_data[1:]:
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
                    # पहले वाली डिलीट करके फ्रेश डालने के लिए (ताकि कोई डुप्लीकेट न रहे)
                    # supabase.table("bookings").delete().neq("trip_id", "0").execute() 
                    for i in range(0, len(bk_rows), 500):
                        supabase.table("bookings").upsert(bk_rows[i:i+500], on_conflict="trip_id").execute()
                    st.success(f"✅ कुल {len(bk_rows)} बुकिंग्स अपडेट हो गईं।")

                # --- 3. एडवांसेज (Advances) ---
                st.write("💸 Advances ट्रांसफर हो रहे हैं...")
                try:
                    adv_data = db.worksheet("Advances").get_all_values()
                    if len(adv_data) > 1:
                        adv_rows = []
                        for r in adv_data[1:]:
                            if len(r) < 9: continue
                            adv_rows.append({
                                "date_val": clean_str(r[0]), "trip_id": clean_str(r[1]), "truck_no": clean_str(r[2]),
                                "bank_name": clean_str(r[7]) if len(r)>7 else "OLD", 
                                "description": clean_str(r[4]), "amount": int(clean_num(r[8])), "zero_col": 0
                            })
                        for i in range(0, len(adv_rows), 500):
                            supabase.table("advances").insert(adv_rows[i:i+500]).execute()
                        st.success(f"✅ {len(adv_rows)} एडवांस रिकॉर्ड आ गए।")
                except: pass

                st.balloons()
                st.success("🏁 माइग्रेशन पूरा हुआ! अब डैशबोर्ड और रिपोर्ट्स चेक करें।")
