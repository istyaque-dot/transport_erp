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
# 🔄 MASTER SYNC FUNCTION 
# ==========================================
def sync_data_to_supabase():
    try:
        from reports import get_sheet_data_for_reports 
        st.info("🚀 गूगल शीट से सारी टेबल्स का डेटा पढ़ा जा रहा है... कृपया प्रतीक्षा करें।")
        
        # ... (बाकी का सिंक लॉजिक वैसा ही रहेगा जैसा आपने भेजा है)
        st.success("सिंक पूरा हुआ!")
    except Exception as e:
        st.error(f"❌ सिंक एरर: {str(e)}")

# ==========================================
# 🖥️ MAIN APP LOGIC (Direct Routing)
# ==========================================
if check_password():
    st.sidebar.title("🚛 ERP Menu")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    PAGES = ["🏠 होम", "बुकिंग", "एडवांस", "POD", "रिसीवेबल", "लेजर", "📊 डैशबोर्ड", "रिपोर्ट्स"]
    choice = st.sidebar.radio("नेविगेशन", PAGES)

    if choice == "🏠 होम":
        st.title("BAZPUR UP TRANSPORT")
        st.write(f"आज की तारीख: {datetime.date.today()}")
        st.divider()
        st.subheader("⚙️ डेटा सिंक्रोनाइजेशन")
        if st.button("📤 सिंक करें (Google -> Supabase)", type="primary"):
            sync_data_to_supabase()

    # ⚠️ यहाँ से 'try...except' हटा दिया गया है ताकि असली एरर दिखे
    elif choice == "बुकिंग":
        from booking import show_booking_page
        show_booking_page()
        
    elif choice == "एडवांस":
        from advance import show_advance_page
        show_advance_page()
        
    elif choice == "POD":
        from pod import show_pod_page
        show_pod_page()
        
    elif choice == "रिसीवेबल":
        from receivable import show_receivable_page
        show_receivable_page()
        
    elif choice == "लेजर":
        from ledger import show_ledger_page
        show_ledger_page()
        
    elif choice == "📊 डैशबोर्ड":
        from dashboard import show_dashboard_page
        show_dashboard_page()
        
    elif choice == "रिपोर्ट्स":
        from reports import show_reports_page
        show_reports_page()
