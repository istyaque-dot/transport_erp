import streamlit as st
import datetime
from supabase import create_client, Client

# ==========================================
# 🚀 SUPABASE CONFIG (V2)
# ==========================================
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🎨 GLOBAL CSS
# ==========================================
st.markdown("""
<style>
/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #001f5b 0%, #003399 60%, #0055cc 100%) !important;
    padding-top: 0.5rem !important;
}
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2) !important; }

/* Sidebar radio buttons */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 3px 0 !important;
    color: rgba(255,255,255,0.9) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-baseweb="radio"] > label {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 6px !important;
    padding: 4px 10px !important;
    margin: 1px 0 !important;
    transition: background 0.15s !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-baseweb="radio"]:has(input:checked) > label {
    background: rgba(255,255,255,0.2) !important;
    border-left: 3px solid #fff !important;
}

/* Sidebar logout button */
[data-testid="stSidebar"] [data-testid="stButton"] button {
    background: rgba(255,255,255,0.15) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    border-radius: 6px !important;
    font-size: 0.8rem !important;
    width: 100% !important;
    min-height: 1.7rem !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
    background: rgba(255,80,80,0.5) !important;
}

.block-container { padding-top: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 LOGIN
# ==========================================
def check_password():
    def password_entered():
        u = st.session_state.get("username", "")
        p = st.session_state.get("password", "")
        if u == "admin" and p == "khan786":
            st.session_state["password_correct"] = True
            st.session_state.pop("password", None)
            st.session_state.pop("username", None)
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Branding & Form
    st.markdown("<div style='text-align:center; padding-top:4vh;'><div style='font-size:3.2rem;'>🚛</div><div style='font-size:1.6rem; font-weight:900; color:#003399;'>BAZPUR UP TRANSPORT</div></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form"):
            st.text_input("👤 Username", key="username")
            st.text_input("🔑 Password", type="password", key="password")
            if st.form_submit_button("🚀 Login करें"):
                password_entered()
                st.rerun()
    return False

# ==========================================
# 🖥️ MAIN APP
# ==========================================
if check_password():
    # Import Pages
    from booking        import show_booking_page
    from advance        import show_advance_page
    from receivable     import show_receivable_page
    from daybook        import show_daybook_page
    from dashboard      import show_dashboard_page
    from transfer       import show_transfer_page
    from reports        import show_reports_page
    from pod            import show_pod_page
    from company_hisaab import show_company_page
    from outstanding    import show_outstanding_page

    # ── Sidebar ──
    st.sidebar.markdown("<div style='text-align:center; padding: 12px 0;'><div style='font-size:1.8rem;'>🚛</div><div style='font-size:1rem; font-weight:900; color:white;'>Transport ERP</div></div>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div style='text-align:center; font-size:0.72rem; color:white;'>📅 {datetime.date.today().strftime('%d %b %Y')}</div>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.sidebar.markdown("<hr>", unsafe_allow_html=True)

    PAGES = [
        "🏠 होम (Home)", "बुकिंग", "एडवांस", "रिसिवेबल (पार्टी पेमेंट)", 
        "डे बुक (Credit/Debit)", "ट्रांसफर / पेमेंट (Contra)", 
        "रिपोर्ट्स (Reports)", "POD और फाइनल हिसाब", "🏢 कंपनी खाता", 
        "💸 लेना - देना (Outstanding)", "📊 डैशबोर्ड", "🛠️ Admin: Data Migration"
    ]
    choice = st.sidebar.radio("मेन्यू", PAGES, label_visibility="collapsed")

    # Routing
    if choice == "🏠 होम (Home)":
        st.markdown("<div style='text-align:center; padding-top:8vh;'><div style='font-size:4rem;'>🚛</div><h1 style='color:#003399;'>BAZPUR UP TRANSPORT</h1><p>सुरक्षित · तेज़ · भरोसेमंद</p></div>", unsafe_allow_html=True)
        # Dashboard like cards
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", "Online", "Supabase V2")
        c2.metric("Database", "PostgreSQL", "Connected")
        c3.metric("System", "Fast Engine", "Active")

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
        show_company_page()
    elif choice == "💸 लेना - देना (Outstanding)":
        show_outstanding_page()
    elif choice == "📊 डैशबोर्ड":
        show_dashboard_page()
    
    # 🚨 Data Migration Tool (For future or missing sheets)
    elif choice == "🛠️ Admin: Data Migration":
        st.header("🚀 Google Sheets ➡️ Supabase Migration")
        st.info("यह टूल पुराने डेटा को नए डेटाबेस में डालने के लिए है।")
        if st.button("🔥 माइग्रेशन शुरू करें"):
            # Yahan migration logic trigger kar sakte hain agar koi sheet bachi ho
            st.write("माइग्रेशन प्रोसेस शुरू...")
