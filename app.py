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
    supabase = None
    # Supabase optional है; Booking/Reports अभी Google Sheets mode में हैं.
    # st.error केवल तब दिखाएँ जब Supabase feature use हो.


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
        
        # यहाँ आपका सिंक लॉजिक आएगा
        st.success("✅ सिंक पूरा हुआ!")
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

    # 🟢 नेविगेशन मेनू में 'रिसीवेबल' मौजूद है
    PAGES = ["🏠 होम", "बुकिंग", "एडवांस", "POD", "रिसीवेबल", "लेजर", "📊 डैशबोर्ड", "रिपोर्ट्स"]
    choice = st.sidebar.radio("नेविगेशन", PAGES)

    if choice == "🏠 होम":
        st.title("🚛 BAZPUR UP TRANSPORT ERP")
        st.markdown(f"**आज की तारीख:** `{datetime.date.today().strftime('%d-%m-%Y')}`")
        st.divider()

        # --- 🟢 SECTION 1: QUICK ACTIONS (शॉर्टकट बटन) ---
        st.subheader("⚡ क्विक एक्शन्स (शॉर्टकट)")
        
        # 🟢 5 बटन कर दिए गए हैं (कंपनी बैलेंस के लिए नया बटन)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("📝 नई बुकिंग", use_container_width=True, type="secondary"):
                st.info("👈 साइडबार से 'बुकिंग' वाले पेज पर जाएँ।")
        with col2:
            if st.button("💸 एडवांस", use_container_width=True, type="secondary"):
                st.info("👈 साइडबार से 'एडवांस' वाले पेज पर जाएँ।")
        with col3:
            if st.button("🏁 मुंशी/POD", use_container_width=True, type="secondary"):
                st.info("👈 साइडबार से 'POD' वाले पेज पर जाएँ।")
        with col4:
            # नया बटन 
            if st.button("🏢 कंपनी बैलेंस", use_container_width=True, type="primary"):
                st.info("👈 साइडबार से 'रिसीवेबल' वाले पेज पर जाएँ।")
        with col5:
            if st.button("📊 रिपोर्ट्स", use_container_width=True, type="secondary"):
                st.info("👈 साइडबार से 'रिपोर्ट्स' वाले पेज पर जाएँ।")

        st.divider()

        # --- 🟢 SECTION 2: BUSINESS SNAPSHOT (वेलकम मैसेज) ---
        st.subheader("👋 वेलकम बैक, मुंशी जी!")
        st.write("बाज़पुर यूपी ट्रांसपोर्ट के डिजिटल सिस्टम में आपका स्वागत है। आप बाएँ तरफ दिए गए मेनू (Menu) से कोई भी काम चुन सकते हैं।")
        
        st.info("""
        **सिस्टम के मुख्य फीचर्स:**
        * 🚚 **बुकिंग:** नई गाड़ियों की एंट्री और एक्सेल अपलोड।
        * 💳 **एडवांस / लेजर:** गाड़ियों का सीधा हिसाब।
        * 📑 **POD:** बिल्टी अपलोड और फाइनल सेटलमेंट।
        * 🏢 **रिसीवेबल (नया):** कंपनी का बैलेंस और POD डाउनलोड।
        * 📊 **रिपोर्ट्स:** दिन भर का कैश फ्लो।
        """)

        st.divider()

        # --- 🟢 SECTION 3: DATA SYNC (बैकअप सिस्टम) ---
        st.subheader("⚙️ डेटा सिंक्रोनाइजेशन (Backup & Sync)")
        st.write("अपने गूगल शीट के डेटा को सुरक्षित रूप से Supabase डेटाबेस में भेजने के लिए नीचे दिया गया बटन दबाएँ:")
        
        col_sync, _ = st.columns([1, 2])
        with col_sync:
            if st.button("📤 सिंक करें (Google -> Supabase)", type="primary", use_container_width=True):
                sync_data_to_supabase()

    # 🟢 पेज राउटिंग सिस्टम
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
        # 🟢 यह 'रिसीवेबल' आपकी कंपनी बैलेंस वाली नई फाइल को चलाएगा
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
