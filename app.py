import streamlit as st
import datetime

st.set_page_config(page_title="Transport ERP", page_icon="", layout="wide")

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

/* Hide streamlit default top padding */
.block-container {
    padding-top: 0.5rem !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 LOGIN
# ==========================================

LOGIN_CSS = """
<style>
[data-testid="stForm"] {
    background: #fff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 14px !important;
    padding: 28px 32px 20px 32px !important;
    box-shadow: 0 4px 24px rgba(0,51,153,0.10) !important;
}
[data-baseweb="input"] { border-radius: 7px !important; min-height: 2rem !important; }
[data-baseweb="input"] input {
    font-size: 0.9rem !important; padding: 4px 12px !important; min-height: 2rem !important;
}
[data-baseweb="input"]:focus-within {
    border-color: #003399 !important;
    box-shadow: 0 0 0 2px rgba(0,51,153,0.1) !important;
}
label, [data-testid="stWidgetLabel"] p {
    font-size: 0.82rem !important; font-weight: 700 !important; color: #374151 !important;
}
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #003399, #0055cc) !important;
    color: #fff !important; border-radius: 8px !important;
    font-size: 0.9rem !important; font-weight: 700 !important;
    min-height: 2.2rem !important; width: 100% !important;
    border: none !important; margin-top: 6px !important;
    box-shadow: 0 3px 10px rgba(0,51,153,0.25) !important;
}
[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, #002277, #0044aa) !important;
}
</style>
"""

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

    # ── Login Page ──
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    # Top branding
    st.markdown("""
        <div style='text-align:center; padding: 4vh 0 2vh 0;'>
            <div style='font-size:3.2rem; line-height:1;'>🚛</div>
            <div style='font-size:1.6rem; font-weight:900;
                        background: linear-gradient(90deg,#001f5b,#003399,#0055cc);
                        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                        letter-spacing:2px; margin:6px 0 2px 0;'>
                BAZPUR UP TRANSPORT
            </div>
            <div style='font-size:0.85rem; color:#888; font-weight:500; letter-spacing:1px;'>
                ERP Management System
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Login form in center column
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form"):
            st.markdown("""
                <div style='text-align:center; font-size:1rem; font-weight:700;
                            color:#003399; margin-bottom:14px;'>
                    🔐 लॉगिन करें
                </div>
            """, unsafe_allow_html=True)
            st.text_input("👤 Username", key="username", placeholder="admin")
            st.text_input("🔑 Password", type="password", key="password", placeholder="••••••••")
            submitted = st.form_submit_button("🚀 Login करें")
            if submitted:
                password_entered()

        if st.session_state.get("password_correct") == False:
            st.markdown("""
                <div style='background:#fee2e2; border:1px solid #f87171;
                    border-radius:7px; padding:6px 14px;
                    font-size:0.82rem; color:#991b1b; font-weight:600;
                    text-align:center; margin-top:4px;'>
                    ❌ गलत यूजरनेम या पासवर्ड!
                </div>
            """, unsafe_allow_html=True)

    # Footer
    st.markdown("""
        <div style='text-align:center; color:#bbb; font-size:0.72rem; margin-top:6vh;'>
            © 2026 Bazpur UP Transport Company · Powered by Khan ERP
        </div>
    """, unsafe_allow_html=True)

    return False

# ==========================================
# 🖥️ MAIN APP
# ==========================================

if check_password():
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
    st.sidebar.markdown("""
        <div style='text-align:center; padding: 12px 0 4px 0;'>
            <div style='font-size:1.8rem;'>🚛</div>
            <div style='font-size:1rem; font-weight:900; letter-spacing:1px;
                        color:white; margin:2px 0;'>Transport ERP</div>
            <div style='font-size:0.7rem; color:rgba(255,255,255,0.6);'>
                Khan Transport Co.
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style='text-align:center; font-size:0.72rem;
                    color:rgba(255,255,255,0.55); margin-bottom:4px;'>
            📅 {datetime.date.today().strftime('%d %b %Y')}
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("<hr style='margin:6px 0;'>", unsafe_allow_html=True)

    if st.sidebar.button("🚪 Logout", key="logout_btn"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.sidebar.markdown("<hr style='margin:6px 0;'>", unsafe_allow_html=True)

    PAGES = [
        "🏠 होम (Home)",
        "बुकिंग",
        "एडवांस",
        "रिसिवेबल (पार्टी पेमेंट)",
        "डे बुक (Credit/Debit)",
        "ट्रांसफर / पेमेंट (Contra)",
        "रिपोर्ट्स (Reports)",
        "POD और फाइनल हिसाब",
        "🏢 कंपनी खाता",
        "💸 लेना - देना (Outstanding)",
        "📊 डैशबोर्ड",
    ]

    choice = st.sidebar.radio("कहाँ जाना है?", PAGES, label_visibility="collapsed")

    # ── Page Routing ──
    if choice == "🏠 होम (Home)":
        st.markdown("""
            <div style='text-align:center; padding: 8vh 0 2vh 0;'>
                <div style='font-size:4rem; margin-bottom:8px;'>🚛</div>
                <div style='font-size:3.2rem; font-weight:900; letter-spacing:3px;
                            background:linear-gradient(90deg,#001f5b,#003399,#0055cc);
                            -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                            line-height:1.1; margin-bottom:4px;'>
                    BAZPUR UP
                </div>
                <div style='font-size:1.6rem; font-weight:800; color:#E74C3C;
                            letter-spacing:4px; text-shadow:1px 1px 3px rgba(0,0,0,0.08);
                            margin-bottom:10px;'>
                    TRANSPORT COMPANY
                </div>
                <div style='font-size:1rem; color:#666; font-weight:500; margin-bottom:20px;'>
                    सुरक्षित &nbsp;·&nbsp; तेज़ &nbsp;·&nbsp; भरोसेमंद
                </div>
                <hr style='width:18%; border:2.5px solid #003399;
                           margin:auto; border-radius:5px; opacity:0.4;'>
            </div>
        """, unsafe_allow_html=True)

        # Quick access cards
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        cards = [
            ("📋", "बुकिंग",        "#003399", "नई गाड़ी लगाएँ"),
            ("💸", "एडवांस",        "#0055cc", "एडवांस पेमेंट दें"),
            ("📥", "रिसिवेबल",      "#0077ff", "पार्टी पेमेंट लें"),
            ("📊", "डैशबोर्ड",      "#E74C3C", "रिपोर्ट देखें"),
        ]
        for col, (icon, title, color, sub) in zip([c1, c2, c3, c4], cards):
            col.markdown(f"""
                <div style='background:linear-gradient(135deg,{color}22,{color}11);
                    border:1px solid {color}44; border-left:4px solid {color};
                    border-radius:10px; padding:14px 16px; text-align:center;
                    margin:4px 0;'>
                    <div style='font-size:1.6rem;'>{icon}</div>
                    <div style='font-size:0.88rem; font-weight:800;
                                color:{color}; margin:3px 0 1px 0;'>{title}</div>
                    <div style='font-size:0.72rem; color:#666;'>{sub}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style='text-align:center; color:#bbb; font-size:0.72rem; margin-top:5vh;'>
                © 2026 Bazpur UP Transport · Khan ERP v2.0
            </div>
        """, unsafe_allow_html=True)

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
