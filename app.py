def sync_data_to_supabase():
    try:
        from reports import get_sheet_data_for_reports 
        st.info("🚀 माइग्रेशन शुरू हो रहा है...")
        
        # 1. Bookings डेटा गूगल शीट से लाना
        raw_bk = get_sheet_data_for_reports("Bookings")
        
        if raw_bk and len(raw_bk) > 1:
            # कॉलम के नाम सेट करना
            cols = [
                "date", "from_loc", "company", "freight_truck", "freight_company", 
                "weight", "truck_no", "destination", "gr_number", "universal_amount", 
                "connect_person", "totalfright", "truck_freight", "universal_payment", 
                "trip_id", "ishtyaque", "google_url"
            ]
            
            df_bk = pd.DataFrame(raw_bk[1:], columns=cols)

            # --- 🔥 मुख्य फिक्स: Encoding और डेटा क्लीनिंग ---
            def clean_text(text):
                if text is None or str(text).lower() in ['nan', 'none', '']:
                    return None
                # किसी भी भाषा (हिंदी/इंग्लिश) को सुरक्षित UTF-8 में बदलना
                return str(text).encode('utf-8', errors='ignore').decode('utf-8')

            # पूरे डेटाफ्रेम पर क्लीनिंग लागू करना
            for col in df_bk.columns:
                df_bk[col] = df_bk[col].apply(clean_text)
            
            # नंबर वाले कॉलम्स को सही फॉर्मेट में बदलना
            num_cols = ["freight_truck", "freight_company", "weight", "universal_amount", 
                        "totalfright", "truck_freight", "universal_payment", "ishtyaque"]
            
            for col in num_cols:
                df_bk[col] = pd.to_numeric(df_bk[col], errors='coerce').fillna(0)

            # डेटा को Supabase में भेजना
            data_dict = df_bk.to_dict(orient='records')
            supabase.table("bookings").upsert(data_dict).execute()
            
            st.success(f"✅ {len(data_dict)} बुकिंग्स सफलतापूर्वक सिंक हो गईं!")
        else:
            st.warning("⚠️ गूगल शीट में डेटा नहीं मिला।")
            
    except Exception as e:
        # एरर को विस्तार से दिखाएं ताकि समझने में आसानी हो
        st.error(f"❌ सिंक एरर: {str(e)}")
