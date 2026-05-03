# ==========================================
# 🔄 MASTER SYNC FUNCTION (All Tables)
# ==========================================
def sync_data_to_supabase():
    try:
        from reports import get_sheet_data_for_reports 
        st.info("🚀 गूगल शीट से डेटा पढ़ा जा रहा है...")
        
        # -----------------------------------------
        # 1. BOOKINGS SYNC
        # -----------------------------------------
        raw_bk = get_sheet_data_for_reports("Bookings")
        if raw_bk and len(raw_bk) > 1:
            bk_cols = ["date", "from_loc", "company", "freight_truck", "freight_company", "weight", "truck_no", "destination", "gr_number", "universal_amount", "connect_person", "totalfright", "truck_freight", "universal_payment", "trip_id", "ishtyaque", "google_url"]
            df_bk = pd.DataFrame(raw_bk[1:], columns=bk_cols)

            df_bk = df_bk.fillna("")
            for col in df_bk.columns:
                df_bk[col] = df_bk[col].astype(str).str.strip()
            
            # गलत डेट को इग्नोर करना (kashipur वाले एरर से बचने के लिए)
            df_bk["date"] = pd.to_datetime(df_bk["date"], errors='coerce').dt.strftime('%Y-%m-%d')
            
            num_cols = ["freight_truck", "freight_company", "weight", "universal_amount", "totalfright", "truck_freight", "universal_payment", "ishtyaque"]
            for col in num_cols:
                df_bk[col] = pd.to_numeric(df_bk[col].str.replace(',', ''), errors='coerce').fillna(0.0).astype(float)

            df_bk = df_bk.replace(["", "nan", "None", "NaN", "<NA>"], None)
            
            bk_data = df_bk.to_dict(orient='records')
            supabase.table("bookings").upsert(bk_data).execute()
            st.success(f"✅ {len(bk_data)} बुकिंग्स सफलतापूर्वक सिंक हो गईं!")

        # -----------------------------------------
        # 2. ADVANCES SYNC
        # -----------------------------------------
        raw_adv = get_sheet_data_for_reports("Advances")
        if raw_adv and len(raw_adv) > 1:
            # 💡 इश्तियाक भाई, यहाँ अपने एडवांस के कॉलम नाम चेक कर लें:
            adv_cols = ["date", "truck_no", "pump_name", "diesel_amount", "cash_advance", "total_advance", "trip_id"] 
            
            df_adv = pd.DataFrame(raw_adv[1:], columns=adv_cols)

            df_adv = df_adv.fillna("")
            for col in df_adv.columns:
                df_adv[col] = df_adv[col].astype(str).str.strip()
            
            # डेट कॉलम सुरक्षित करना
            if "date" in df_adv.columns:
                df_adv["date"] = pd.to_datetime(df_adv["date"], errors='coerce').dt.strftime('%Y-%m-%d')
            
            # नंबर वाले कॉलम्स को सही करना (ताकि Supabase मना न करे)
            adv_num_cols = ["diesel_amount", "cash_advance", "total_advance"]
            for col in adv_num_cols:
                if col in df_adv.columns:
                    df_adv[col] = pd.to_numeric(df_adv[col].str.replace(',', ''), errors='coerce').fillna(0.0).astype(float)

            df_adv = df_adv.replace(["", "nan", "None", "NaN", "<NA>"], None)
            
            adv_data = df_adv.to_dict(orient='records')
            supabase.table("advances").upsert(adv_data).execute()
            st.success(f"✅ {len(adv_data)} एडवांसेस सफलतापूर्वक सिंक हो गए!")

    except Exception as e:
        st.error(f"❌ सिंक एरर: {str(e)}")
        st.exception(e)
