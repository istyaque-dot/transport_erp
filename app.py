import streamlit as st
import datetime
import pandas as pd
import json
from supabase import create_client

# ==========================================
# ⚙️ APP CONFIGURATION
# ==========================================
st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🔐 SUPABASE SETUP
# ==========================================
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)
except Exception as e:
    st.error("Supabase Secrets missing! Please check Streamlit Cloud Settings.")

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
# 🔒 LOGIN SYSTEM (Double Check Fix)
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
# 🔄 SYNC FUNCTION (Anti-ASCII Error Version)
# ==========================================
# ==========================================
# 🔄 SYNC FUNCTION (Super Safe JSON Version)
# ==========================================
def sync_data_to_supabase():
    try:
        from reports import get_sheet_data_for_reports 
        st.info("🚀 गूगल शीट से डेटा पढ़ा जा रहा है...")
        
        raw_bk = get_sheet_data_for_reports("Bookings")
        
        if raw_bk and len(raw_bk) > 1:
            cols = ["date", "from_loc", "company", "freight_truck", "freight_company", "weight", "truck_no", "destination", "gr_number", "universal_amount", "connect_person", "totalfright", "truck_freight", "universal_payment", "trip_id", "ishtyaque", "google_url"]
            df_bk = pd.DataFrame(raw_bk[1:], columns=cols)

            # 1. डेटा को साफ करना और हर चीज़ को 'String' बनाना
            df_bk = df_bk.fillna("")
            for col in df_bk.columns:
                df_bk[col] = df_bk[col].astype(str).str.strip()
            
            # 2. नंबर वाले कॉलम को सही तरीके से Float (दशमलव) में बदलना
            num_cols = ["freight_truck", "freight_company", "weight", "universal_amount", "totalfright", "truck_freight", "universal_payment", "ishtyaque"]
            for col in num_cols:
                df_bk[col] = pd.to_numeric(df_bk[col].str.replace(',', ''), errors='coerce').fillna(0.0).astype(float)

            # 3. खाली स्ट्रिंग को 'None' (Null) में बदलना ताकि Supabase एरर न दे
            df_bk = df_bk.replace(["", "nan", "None", "NaN", "<NA>"], None)

            # 4. 🔥 सबसे अहम फिक्स: JSON डंप और लोड
            # यह Numpy या Pandas के किसी भी खराब डेटा को शुद्ध पाइथन डेटा में बदल देगा (हिंदी को सुरक्षित रखते हुए)
            data_dict = df_bk.to_dict(orient='records')
            safe_data = json.loads(json.dumps(data_dict, ensure_ascii=False))

            st.info("☁️ Supabase में सेव किया जा रहा है...")
            
            # 5. डेटा भेजना
            supabase.table("bookings").upsert(safe_data).execute()
            
            st.success(f"✅ {len(safe_data)} बुकिंग्स सफलतापूर्वक सिंक हो गईं!")
        else:
            st.warning("⚠️ गूगल शीट में डेटा नहीं मिला।")
            
    except Exception as e:
        st.error(f"❌ सिंक एरर: {str(e)}")
        # अगर फिर भी एरर आता है, तो यह लाल बॉक्स में पूरी डिटेल दिखाएगा
        st.exception(e)

# ==========================================
# 🖥️ MAIN APP LOGIC
# ==========================================
if check_password():
    try:
        # यहाँ पक्का करें कि ये फाइलें आपके GitHub फोल्डर में हैं
        from booking import show_booking_page
        from advance import show_advance_page
        from dashboard import show_dashboard_page
        from reports import show_reports_page
        # बाकी इम्पोर्ट्स यहाँ जोड़ें...
    except Exception as e:
        st.error(f"⚠️ फाइल इम्पोर्ट एरर: {e}")
        st.stop()

    # Sidebar
    st.sidebar.title("🚛 ERP Menu")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    choice = st.sidebar.radio("नेविगेशन", ["🏠 होम", "बुकिंग", "एडवांस", "📊 डैशबोर्ड"])

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
