def sync_data_to_supabase():
    from reports import get_sheet_data_for_reports 
    st.info("🚀 माइग्रेशन शुरू हो रहा है...")
    
    try:
        # 1. Bookings डेटा लाना
        raw_bk = get_sheet_data_for_reports("Bookings")
        
        if raw_bk and len(raw_bk) > 1:
            # डेटा को साफ़ करना और सही कॉलम नाम देना
            df_bk = pd.DataFrame(raw_bk[1:], columns=[
                "date", "from_loc", "company", "freight_truck", "freight_company", 
                "weight", "truck_no", "destination", "gr_number", "universal_amount", 
                "connect_person", "totalfright", "truck_freight", "universal_payment", 
                "trip_id", "ishtyaque", "google_url"
            ])

            # --- एरर फिक्स: हिंदी और स्पेशल करैक्टर को साफ़ करना ---
            for col in df_bk.columns:
                # हर वैल्यू को स्ट्रिंग में बदलकर साफ़ करना
                df_bk[col] = df_bk[col].astype(str).apply(lambda x: x.encode('utf-8', 'ignore').decode('utf-8'))
            
            # खाली वैल्यू (NaN) को SQL के हिसाब से None बनाना
            df_bk = df_bk.replace(['', 'nan', 'None'], None)
            
            # डेटा को डिक्शनरी में बदलकर Supabase में डालना
            data_dict = df_bk.to_dict(orient='records')
            
            # 'upsert' कमांड से डेटा भेजना (अगर trip_id पहले से है तो अपडेट होगा)
            supabase.table("bookings").upsert(data_dict).execute()
            
            st.success(f"✅ {len(data_dict)} बुकिंग्स सफलतापूर्वक सिंक हो गईं!")
        else:
            st.warning("⚠️ गूगल शीट में कोई डेटा नहीं मिला।")
            
    except Exception as e:
        # अगर अभी भी कोई एरर आये तो उसे साफ़ दिखाएँ
        st.error(f"❌ सिंक एरर: {str(e)}")
