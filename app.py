import streamlit as st
import datetime

# --- पेज कॉन्फ़िगरेशन ---
st.set_page_config(page_title="Khan Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🔒 LOGIN SYSTEM LOGIC
# ==========================================

def check_password():
    """लॉगिन फॉर्म दिखाता है और पासवर्ड चेक करता है।"""
    def password_entered():
        # 🟢 अपना यूजरनेम और पासवर्ड यहाँ चेक करें
        if st.session_state["username"] == "admin" and st.session_state["password"] == "khan786":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>🔐 Khan Transport ERP Login</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                st.text_input("Username", key="username")
                st.text_input("Password", type="password", key="password")
                st.form_submit_button("Login", on_click=password_entered)
        return False
    
    elif not st.session_state["password_correct"]:
        st.error("❌ गलत यूजरनेम या पासवर्ड!")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                st.text_input("Username", key="username")
                st.text_input("Password", type="password", key="password")
                st.form_submit_button("Login", on_click=password_entered)
        return False
    
    return True

# ==========================================
# 🖥️ MAIN ERP APP (ये सब IF के अंदर होना चाहिए)
# ==========================================

if check_password():
    # 🟢 ध्यान दें: नीचे की सारी लाइनें अब IF के अंदर हैं (Space देकर आगे खिसकाई गई हैं)
    from booking import show_booking_page
    from advance import show_advance_page
    from receivable import show_receivable_page
    from daybook import show_daybook_page
    from dashboard import show_dashboard_page
    from transfer import show_transfer_page
    from reports import show_reports_page
    from pod import show_pod_page  

    st.sidebar.markdown("<h2 style='text-align: center;'>🚛 Khan ERP</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='text-align: center; color: gray;'>Today: {datetime.date.today()}</p>", unsafe_allow_html=True)
    
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
        "POD और फाइनल हिसाब"
    ])

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
