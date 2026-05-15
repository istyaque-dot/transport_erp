import streamlit as st
from supabase import create_client, Client
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# सुपबेस क्रेडेंशियल्स
url = "https://tsyghmvqrlxwicipkvqw.supabase.co"
key = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase = create_client(url, key)

def show_migration_page():
    st.header("🚀 Diagnostic Migration Mode")
    st.write("यह मोड बताएगा कि डेटा क्यों नहीं जा रहा है।")

    if st.button("🔍 Run Diagnostic Sync", type="primary"):
        try:
            # 1. गूगल शीट से जुड़ना
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            
            st.write("✅ गूगल शीट से कनेक्शन जुड़ गया।")
            
            # 2. शीट खोलना
            sheet = client.open("Khan_Transport_ERP").worksheet("Bookings")
            data = sheet.get_all_values()
            st.write(f"📊 शीट में कुल {len(data)} लाइनें मिलीं (हेडर समेत)।")[cite: 1]

            if len(data) <= 1:
                st.error("❌ शीट खाली दिख रही है!")
                return

            # 3. डेटा तैयार करना
            rows_to_send = []
            for i, r in enumerate(data[1:], start=2):
                # पक्का करें कि कम से कम 15 कॉलम हैं[cite: 1]
                if len(r) < 15:
                    st.warning(f"⚠️ लाइन {i} में कॉलम कम हैं ({len(r)} कॉलम)।")
                    continue
                
                # Trip Number (Index 14) चेक करें[cite: 1]
                trip_id = str(r[14]).strip()
                if not trip_id:
                    continue

                rows_to_send.append({
                    "date": str(r[0]), "from_loc": str(r[1]), "comapny": str(r[2]),
                    "freight_truck": str(r[3]), "freight_company": str(r[4]),
                    "weight": str(r[5]), "truck_no": str(r[6]), "destination": str(r[7]),
                    "gr_number": str(r[8]), "universal_amount": str(r[9]),
                    "connect_person": str(r[10]), "total_fright": str(r[11]),
                    "truck_freight": str(r[12]), "universal_payment": str(r[13]),
                    "trip_number": trip_id, "ishtyaque": str(r[15]) if len(r) > 15 else "0",
                    "gr_link": str(r[16]) if len(r) > 16 else ""
                })

            st.write(f"📦 भेजने के लिए {len(rows_to_send)} रिकॉर्ड तैयार हैं।")

            # 4. सुपबेस में भेजना
            if rows_to_send:
                st.write("📤 सुपबेस में डेटा भेजा जा रहा है...")
                res = supabase.table("bookings").insert(rows_to_send).execute()
                st.success(f"✅ सफलतापूर्वक {len(rows_to_send)} ट्रिप्स ट्रांसफर हो गईं!")
                st.balloons()
            else:
                st.error("❌ कोई वैध डेटा (Valid Data) नहीं मिला भेजने के लिए।")

        except Exception as e:
            st.error(f"‼️ गड़बड़ यहाँ है: {str(e)}")
            st.info("कृपया ऊपर दिए गए एरर का स्क्रीनशॉट मुझे भेजें।")
