import streamlit as st
import datetime

# --- पेज कॉन्फ़िगरेशन ---
st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🔒 LOGIN SYSTEM LOGIC
# ==========================================

def check_password():
    """लॉगिन फॉर्म दिखाता है और पासवर्ड चेक करता है।"""
    def password_entered():
        # Check if keys exist before accessing
        username = st.session_state.get("username", "")
        password = st.session_state.get("password", "")
        
        if username == "admin" and password == "khan786":
            st.session_state["password_correct"] = True
            # सुरक्षा के लिए पासवर्ड डिलीट करें
            if "password" in st.session_state:
                del st.session_state["password"]
            if "username" in st.session_state:
                del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    # Check if already logged in
    if st.session_state.get("password_correct", False):
        return True
    
    # Show login form
    st.markdown("<h2 style='text-align: center;'>🔐  Transport ERP Login</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                password_entered()
    
    # Show error if login failed
    if st.session_state.get("password_correct") == False:
        st.error("❌ गलत यूजरनेम या पासवर्ड!")
    
    return False

# ==========================================
# 🖥️ MAIN ERP APP (Only shown if logged in)
# ==========================================

if check_password():
    # 🟢 नई फाइल का लिंक यहाँ जोड़ दिया गया है
    from booking import show_booking_page
    from advance import show_advance_page
    from receivable import show_receivable_page
    from daybook import show_daybook_page
    from dashboard import show_dashboard_page
    from transfer import show_transfer_page
    from reports import show_reports_page
    from pod import show_pod_page  
    from company_hissab import show_company_page  # 🟢 नया पेज

    # --- SIDEBAR ---
    st.sidebar.markdown("<h2 style='text-align: center;'>🚛 Khan ERP</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='text-align: center; color: gray;'>Today: {datetime.date.today()}</p>", unsafe_allow_html=True)
    
    # लॉगआउट बटन
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.sidebar.markdown("---")

    choice = st.sidebar.radio("कहाँ जाना है?", [
        "डैशबोर्ड", 
        "बुकिंग", 
        "एडवांस", 
        "रिसिवेबल (पार्टी पेमेंट)", 
        "डे बुक (Credit/Debit)", 
        "ट्रांसफर / पेमेंट (Contra)", 
        "रिपोर्ट्स (Reports)",
        "POD और फाइनल हिसाब",
        "🏢 कंपनी खाता"  # 🟢 नया टैब लिस्ट में आ गया
    ])

    # --- PAGE NAVIGATION ---
    if choice == "डैशबोर्ड":
        show_dashboard_page()
    elif choice == "बुकिंग":
        show_booking_page()
    elif choice == "एडवांस":
        show_advance_page()
    elif choice == "रिसिवेबल (पार्टी पेमेंट)":
        show_receivable_page()
    elif choice == "डे बुक (Credit/Debit)":
        show_daybook_page()
    elif choice == "ट्रांसफर / पेमेंट (Contra)":
        show_transfer_page()
    elif choice == "रिपोर्ट्स (Reports)":
        show_reports_page()
    elif choice == "POD और फाइनल हिसाब":
        show_pod_page()
    elif choice == "🏢 कंपनी खाता":
        show_company_page()  # 🟢 यहाँ से नया पेज खुलेगा
