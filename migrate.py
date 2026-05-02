import streamlit as st
from supabase import create_client, Client
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# सुपबेस क्रेडेंशियल्स
url = "https://tsyghmvqrlxwicipkvqw.supabase.co"
key = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"
supabase = create_client(url, key)

def show_migration_page():
    st.header("🚀 Final Data Migration")

    if st.button("🔥 START SYNC", type="primary"):
        try:
            with st.spinner("Connecting to Google Sheets..."):
                creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
                client = gspread.authorize(creds)
                sheet = client.open("Khan_Transport_ERP").worksheet("Bookings")
                data = sheet.get_all_values() # सारा डेटा लिस्ट के रूप में[cite: 1]

            st.write(f"कुल {len(data)-1} ट्रिप्स मिलीं। ट्रांसफर शुरू...")[cite: 1]
            
            rows_to_send = []
            # पहली लाइन हेडर है, इसलिए index 1 से शुरू करेंगे
            for r in data[1:]:
                if len(r) < 15 or not r[14]: continue # अगर Trip Number गायब है तो छोड़ दें[cite: 1]
                
                rows_to_send.append({
                    "date": str(r[0]), "from_loc": str(r[1]), "comapny": str(r[2]),
                    "freight_truck": str(r[3]), "freight_company": str(r[4]),
                    "weight": str(r[5]), "truck_no": str(r[6]), "destination": str(r[7]),
                    "gr_number": str(r[8]), "universal_amount": str(r[9]),
                    "connect_person": str(r[10]), "total_fright": str(r[11]),
                    "truck_freight": str(r[12]), "universal_payment": str(r[13]),
                    "trip_number": str(r[14]), "ishtyaque": str(r[15]),
                    "gr_link": str(r[16]) if len(r) > 16 else ""
                })

            if rows_to_send:
                # 50-50 के बैच में भेजेंगे ताकि लोड न पड़े
                for i in range(0, len(rows_to_send), 50):
                    supabase.table("bookings").upsert(rows_to_send[i:i+50], on_conflict="trip_number").execute()
                st.success("✅ बुकिंग्स सिंक हो गई हैं!")
                st.balloons()

        except Exception as e:
            st.error(f"Error: {str(e)}")
