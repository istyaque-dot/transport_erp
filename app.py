import streamlit as st
import datetime
import pandas as pd
from supabase import create_client

# ==========================================
# ⚙️ APP CONFIGURATION
# ==========================================
st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🔐 SUPABASE SETUP
# ==========================================
try:
    clean_url = str(st.secrets["supabase"]["url"]).strip()
    clean_key = str(st.secrets["supabase"]["key"]).strip()
    supabase = create_client(clean_url, clean_key)
except Exception as e:
    st.error(f"Supabase Secrets Setup Error: {e}")

# ==========================================
# 🎨 GLOBAL CSS
# ==========================================
st.markdown("""
<style>
[data-testid="stSidebar"] { background: linear-gradient(180deg, #001f5b 0%, #003399 60%, #0055cc 100%) !important; }
[data-testid="stSidebar"] * { color: white !important; }
.block-container { padding-top: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 LOGIN SYSTEM
# ==========================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<div style='text-align:center; padding-top:10vh;'><div style='font-size:4rem;'>🚛</div><h1 style='color:#003399;'>BAZPUR UP TRANSPORT</h1></div>", unsafe_allow_html=True)
    
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form_new"):
            u = st.text_input("👤 Username")
            p = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("🚀 Login करें"):
                if u == "admin" and p == "khan786":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ गलत यूजरनाम या पासवर्ड")
    return False

# ==========================================
# 🔄 MASTER SYNC FUNCTION (All 15 Tables)
# ==========================================
# ==========================================
# 🔄 MASTER SYNC FUNCTION (100% Pure Python NaN Fix)
# ==========================================
def sync_data_to_supabase():
    try:
        from reports import get_sheet_data_for_reports 
        st.info("🚀 गूगल शीट से सारी टेबल्स का डेटा पढ़ा जा रहा है... कृपया प्रतीक्षा करें।")
        
        SYNC_CONFIG = {
            "Bookings": {"table": "bookings", "sheet_cols": ["date", "from_loc", "company", "freight_truck", "freight_company", "weight", "truck_no", "destination", "gr_number", "universal_amount", "connect_person", "totalfright", "truck_freight", "universal_payment", "trip_id", "ishtyaque", "google_url"], "db_cols": ["date", "from_loc", "company", "freight_truck", "freight_company", "weight", "truck_no", "destination", "gr_number", "universal_amount", "connect_person", "totalfright", "truck_freight", "universal_payment", "trip_id", "ishtyaque", "google_url"], "num_cols": ["freight_truck", "freight_company", "weight", "universal_amount", "totalfright", "truck_freight", "universal_payment", "ishtyaque"]},
            "Advances": {"table": "advances", "sheet_cols": ["Date", "Trip_ID", "truck_no", "Diesel_Amt", "Pump_Name", "Cash_Amt", "Bank_Amt", "Bank_Account", "Total_Advance"], "db_cols": ["date", "trip_id", "truck_no", "diesel_amt", "pump_name", "cash_amt", "bank_amt", "bank_account", "total_advance"], "num_cols": ["diesel_amt", "cash_amt", "bank_amt", "total_advance"]},
            "Owner_Ledger": {"table": "owner_ledger", "sheet_cols": ["date", "trip number", "gr number", "truck number", "destination", "freight"], "db_cols": ["date", "trip_id", "gr_no", "truck_no", "destination", "freight"], "num_cols": ["freight"]},
            "canara_1747": {"table": "canara_1747", "sheet_cols": ["date", "comment", "to /from", "amount"], "db_cols": ["date", "comment", "to_from", "amount"], "num_cols": ["amount"]},
            "Company_PODs": {"table": "company_pods", "sheet_cols": ["Date", "Trip_ID", "GR_No", "Truck_No", "Status", "AMOUNT"], "db_cols": ["date", "trip_id", "gr_no", "truck_no", "status", "amount"], "num_cols": ["amount"]},
            "Cash_Ledger": {"table": "cash_ledger", "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"], "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"], "num_cols": ["amount"]},
            "Receivables": {"table": "receivables", "sheet_cols": ["Date", "Trip_ID", "Truck_No", "Company", "Received_Amt", "Bank_Name", "Shortage_Amt", "Remarks"], "db_cols": ["date", "trip_id", "truck_no", "company", "received_amt", "bank_name", "shortage_amt", "remarks"], "num_cols": ["received_amt", "shortage_amt"]},
            "Canara_311_Ledger": {"table": "canara_311_ledger", "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"], "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"], "num_cols": ["amount"]},
            "Canara_41_Ledger": {"table": "canara_41_ledger", "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"], "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"], "num_cols": ["amount"]},
            "BOB_Ledger": {"table": "bob_ledger", "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"], "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"], "num_cols": ["amount"]},
            "Day_Book": {"table": "day_book", "sheet_cols": ["Date", "Account", "Entry_Type", "Category", "Amount", "Remarks"], "db_cols": ["date", "account", "entry_type", "category", "amount", "remarks"], "num_cols": ["amount"]},
            "Shekh_Filling_Ledger": {"table": "shekh_filling_ledger", "sheet_cols": ["Date", "Trip_ID", "GR_No", "Destination", "Amount"], "db_cols": ["date", "trip_id", "gr_no", "destination", "amount"], "num_cols": ["amount"]},
            "Company_Ledger": {"table": "company_ledger", "sheet_cols": ["date", "trip number", "gr number", "truck number", "destination", "freight"], "db_cols": ["date", "trip_id", "gr_no", "truck_no", "destination", "freight"], "num_cols": ["freight"]},
            "Universal_Ledger": {"table": "universal_ledger", "sheet_cols": ["date", "trip date", "gr number", "COMMENT", "truck number", "payment"], "db_cols": ["date", "trip_date", "gr_no", "comment", "truck_no", "payment"], "num_cols": ["payment"]},
            "Ishtyaque_Ledger": {"table": "ishtyaque_ledger", "sheet_cols": ["date", "trip number", "gr number", "COMMENT", "truck number", "amount"], "db_cols": ["date", "trip_id", "gr_no", "comment", "truck_no", "amount"], "num_cols": ["amount"]}
        }

        progress_bar = st.progress(0)
        total_tables = len(SYNC_CONFIG)
        current_step = 0
        success_logs = []

        for sheet_name, config in SYNC_CONFIG.items():
            try:
                raw_data = get_sheet_data_for_reports(sheet_name)
                
                if raw_data and len(raw_data) > 1:
                    df = pd.DataFrame(raw_data[1:], columns=config["sheet_cols"])
                    df.columns = config["db_cols"]
                    
                    # 1. डेटा क्लीनिंग
                    for col in df.columns:
                        df[col] = df[col].astype(str).str.strip()

                    # 2. डेट फॉर्मेटिंग
                    for col in ["date", "trip_date"]:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')

                    # 3. नंबर फॉर्मेटिंग
                    for num_col in config["num_cols"]:
                        if num_col in df.columns:
                            df[num_col] = pd.to_numeric(df[num_col].astype(str).str.replace(',', ''), errors='coerce')

                    # डेटा को डिक्शनरी में बदला
                    raw_dict_list = df.to_dict(orient='records')
                    
                    # 🔥 4. सबसे बड़ा फिक्स (Pure Python Clean-up): 
                    # Pandas को दरकिनार करके एक-एक सेल चेक करना ताकि कोई NaN बच ही न पाए
                    clean_data_list = []
                    for row in raw_dict_list:
                        clean_row = {}
                        for key, val in row.items():
                            # अगर वैल्यू NaN है, खाली है, या 'nan' टेक्स्ट है, तो उसे पक्का 'None' कर दो
                            if pd.isna(val) or val == 'nan' or val == '':
                                clean_row[key] = None
                            else:
                                clean_row[key] = val
                        clean_data_list.append(clean_row)
                    
                    # साफ किया हुआ डेटा Supabase में भेजें
                    supabase.table(config["table"]).upsert(clean_data_list).execute()
                    
                    success_logs.append(f"✅ {sheet_name}: {len(clean_data_list)} एंट्रीज़")
                else:
                    success_logs.append(f"⚠️ {sheet_name}: डेटा नहीं मिला")

            except Exception as table_error:
                st.error(f"❌ {sheet_name} टेबल में एरर आया: {table_error}")
            
            current_step += 1
            progress_bar.progress(current_step / total_tables)

        st.success("🎉 माइग्रेशन पूरा हुआ!")
        with st.expander("📊 सिंक की गई टेबल्स की रिपोर्ट देखें"):
            for log in success_logs:
                st.write(log)

    except Exception as e:
        st.error(f"❌ मुख्य सिंक एरर: {str(e)}")
        st.exception(e)# ==========================================
# 🖥️ MAIN APP LOGIC (Routing & Sidebar)
# ==========================================
if check_password():
    try:
        from booking import show_booking_page
        from advance import show_advance_page
        from dashboard import show_dashboard_page
        from reports import show_reports_page
        # अगर आपके और भी पेजेज हैं (जैसे receivable), तो उन्हें यहाँ इम्पोर्ट कर लें
    except Exception as e:
        st.error(f"⚠️ फाइल इम्पोर्ट एरर: {e}")
        st.stop()

    st.sidebar.title("🚛 ERP Menu")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    PAGES = ["🏠 होम", "बुकिंग", "एडवांस", "📊 डैशबोर्ड", "रिपोर्ट्स"]
    choice = st.sidebar.radio("नेविगेशन", PAGES)

    if choice == "🏠 होम":
        st.title("BAZPUR UP TRANSPORT")
        st.write(f"आज की तारीख: {datetime.date.today()}")
        st.divider()
        st.subheader("⚙️ डेटा सिंक्रोनाइजेशन")
        if st.button("📤 सिंक करें (Google -> Supabase)", type="primary"):
            sync_data_to_supabase()

    elif choice == "बुकिंग": show_booking_page()
    elif choice == "एडवांस": show_advance_page()
    elif choice == "📊 डैशबोर्ड": show_dashboard_page()
    elif choice == "रिपोर्ट्स": show_reports_page()
