# ==========================================
# 🔄 MASTER SYNC FUNCTION (All 15 Tables)
# ==========================================
def sync_data_to_supabase():
    try:
        from reports import get_sheet_data_for_reports 
        st.info("🚀 गूगल शीट से सारी टेबल्स का डेटा पढ़ा जा रहा है... कृपया प्रतीक्षा करें।")
        
        # 1. डेटाबेस कॉन्फ़िगरेशन (आपकी दी हुई लिस्ट के अनुसार)
        # फॉर्मेट: "Google Sheet Name": {"table": "supabase_table", "sheet_cols": [...], "db_cols": [...], "num_cols": [...]}
        SYNC_CONFIG = {
            "Bookings": {
                "table": "bookings",
                "sheet_cols": ["date", "from_loc", "company", "freight_truck", "freight_company", "weight", "truck_no", "destination", "gr_number", "universal_amount", "connect_person", "totalfright", "truck_freight", "universal_payment", "trip_id", "ishtyaque", "google_url"],
                "db_cols": ["date", "from_loc", "company", "freight_truck", "freight_company", "weight", "truck_no", "destination", "gr_number", "universal_amount", "connect_person", "totalfright", "truck_freight", "universal_payment", "trip_id", "ishtyaque", "google_url"],
                "num_cols": ["freight_truck", "freight_company", "weight", "universal_amount", "totalfright", "truck_freight", "universal_payment", "ishtyaque"]
            },
            "Advances": {
                "table": "advances",
                "sheet_cols": ["Date", "Trip_ID", "truck_no", "Diesel_Amt", "Pump_Name", "Cash_Amt", "Bank_Amt", "Bank_Account", "Total_Advance"],
                "db_cols": ["date", "trip_id", "truck_no", "diesel_amt", "pump_name", "cash_amt", "bank_amt", "bank_account", "total_advance"],
                "num_cols": ["diesel_amt", "cash_amt", "bank_amt", "total_advance"]
            },
            "Owner_Ledger": {
                "table": "owner_ledger",
                "sheet_cols": ["date", "trip number", "gr number", "truck number", "destination", "freight"],
                "db_cols": ["date", "trip_id", "gr_no", "truck_no", "destination", "freight"],
                "num_cols": ["freight"]
            },
            "canara_1747": {
                "table": "canara_1747",
                "sheet_cols": ["date", "comment", "to /from", "amount"],
                "db_cols": ["date", "comment", "to_from", "amount"],
                "num_cols": ["amount"]
            },
            "Company_PODs": {
                "table": "company_pods",
                "sheet_cols": ["Date", "Trip_ID", "GR_No", "Truck_No", "Status", "AMOUNT"],
                "db_cols": ["date", "trip_id", "gr_no", "truck_no", "status", "amount"],
                "num_cols": ["amount"]
            },
            "Cash_Ledger": {
                "table": "cash_ledger",
                "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"],
                "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"],
                "num_cols": ["amount"]
            },
            "Receivables": {
                "table": "receivables",
                "sheet_cols": ["Date", "Trip_ID", "Truck_No", "Company", "Received_Amt", "Bank_Name", "Shortage_Amt", "Remarks"],
                "db_cols": ["date", "trip_id", "truck_no", "company", "received_amt", "bank_name", "shortage_amt", "remarks"],
                "num_cols": ["received_amt", "shortage_amt"]
            },
            "Canara_311_Ledger": {
                "table": "canara_311_ledger",
                "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"],
                "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"],
                "num_cols": ["amount"]
            },
            "Canara_41_Ledger": {
                "table": "canara_41_ledger",
                "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"],
                "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"],
                "num_cols": ["amount"]
            },
            "BOB_Ledger": {
                "table": "bob_ledger",
                "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"],
                "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"],
                "num_cols": ["amount"]
            },
            "Day_Book": {
                "table": "day_book",
                "sheet_cols": ["Date", "Account", "Entry_Type", "Category", "Amount", "Remarks"],
                "db_cols": ["date", "account", "entry_type", "category", "amount", "remarks"],
                "num_cols": ["amount"]
            },
            "Shekh_Filling_Ledger": {
                "table": "shekh_filling_ledger",
                "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"],
                "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"],
                "num_cols": ["amount"]
            },
            "Company_Ledger": {
                "table": "company_ledger",
                "sheet_cols": ["date", "trip number", "gr number", "truck number", "destination", "freight"],
                "db_cols": ["date", "trip_id", "gr_no", "truck_no", "destination", "freight"],
                "num_cols": ["freight"]
            },
            "Universal_Ledger": {
                "table": "universal_ledger",
                "sheet_cols": ["date", "trip date", "gr number", "COMMENT", "truck number", "payment"],
                "db_cols": ["date", "trip_date", "gr_no", "comment", "truck_no", "payment"],
                "num_cols": ["payment"]
            },
            "Ishtyaque_Ledger": {
                "table": "ishtyaque_ledger",
                "sheet_cols": ["date", "trip number", "gr number", "COMMENT", "truck number", "amount"],
                "db_cols": ["date", "trip_id", "gr_no", "comment", "truck_no", "amount"],
                "num_cols": ["amount"]
            }
        }

        # 2. प्रोग्रेस बार सेट करना
        progress_bar = st.progress(0)
        total_tables = len(SYNC_CONFIG)
        current_step = 0
        success_logs = []

        # 3. स्मार्ट लूप (हर शीट का डेटा बारी-बारी से प्रोसेस करना)
        for sheet_name, config in SYNC_CONFIG.items():
            try:
                raw_data = get_sheet_data_for_reports(sheet_name)
                
                if raw_data and len(raw_data) > 1:
                    # डेटाफ्रेम बनाना
                    df = pd.DataFrame(raw_data[1:], columns=config["sheet_cols"])
                    
                    # डेटाबेस के हिसाब से कॉलम का नाम बदलना
                    df.columns = config["db_cols"]

                    # डेटा साफ़ करना (Trim & Clean)
                    df = df.fillna("")
                    for col in df.columns:
                        df[col] = df[col].astype(str).str.strip()

                    # तारीख (Date) वाले कॉलम्स को सही फॉर्मेट (YYYY-MM-DD) में लाना
                    for col in ["date", "trip_date"]:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')

                    # नंबर वाले कॉलम्स को फ्लोट (Float) में बदलना
                    for num_col in config["num_cols"]:
                        if num_col in df.columns:
                            df[num_col] = pd.to_numeric(df[num_col].str.replace(',', ''), errors='coerce').fillna(0.0).astype(float)

                    # खाली जगह को None बनाना (SQL के लिए)
                    df = df.replace(["", "nan", "None", "NaN", "<NA>"], None)
                    
                    # Supabase में भेजना
                    data_dict = df.to_dict(orient='records')
                    supabase.table(config["table"]).upsert(data_dict).execute()
                    
                    success_logs.append(f"✅ {sheet_name}: {len(data_dict)} एंट्रीज़")
                else:
                    success_logs.append(f"⚠️ {sheet_name}: डेटा नहीं मिला")

            except Exception as table_error:
                st.error(f"❌ {sheet_name} टेबल में एरर आया: {table_error}")
            
            # प्रोग्रेस बार अपडेट करना
            current_step += 1
            progress_bar.progress(current_step / total_tables)

        # 4. फाइनल रिपोर्ट
        st.success("🎉 माइग्रेशन पूरा हुआ!")
        with st.expander("📊 सिंक की गई टेबल्स की रिपोर्ट देखें"):
            for log in success_logs:
                st.write(log)

    except Exception as e:
        st.error(f"❌ मुख्य सिंक एरर: {str(e)}")
        st.exception(e)
