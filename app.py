import streamlit as st
import datetime
import pandas as pd
from supabase import create_client

# ऐप कॉन्फ़िगरेशन
st.set_page_config(page_title="Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🔐 SUPABASE SETUP
# ==========================================
# पक्का करें कि आपने Secrets में [supabase] सेक्शन जोड़ दिया है
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# ==========================================
# 🎨 GLOBAL CSS (पहले जैसा ही)
# ==========================================
st.markdown("""
<style>
/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #001f5b 0%, #003399 60%, #0055cc 100%) !important;
}
/* ... (बाकी CSS पहले जैसा ही रखें) ... */
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔒 LOGIN SYSTEM (पहले जैसा ही)
# ==========================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    
    st.markdown("<div style='text-align:center; padding-top:4vh;'><div style='font-size:3.2rem;'>🚛</div><div style='font-size:1.6rem; font-weight:900; color:#003399;'>BAZPUR UP TRANSPORT</div></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login_form"):
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
# 🔄 SYNC FUNCTION (Google Sheets to Supabase)
# ==========================================
def sync_data_to_supabase():
    from reports import get_sheet_data_for_reports # डेटा लाने के लिए पुराना फंक्शन
    st.info("🚀 माइग्रेशन शुरू हो रहा है...")
    
    try:
        # 1. Bookings Sync (17 Column)
        raw_bk = get_sheet_data_for_reports("Bookings")
        if len(raw_bk) > 1:
            df_bk = pd.DataFrame(raw_bk[1:], columns=[
                "date", "from_loc", "company", "freight_truck", "freight_company", 
                "weight", "truck_no", "destination", "gr_number", "universal_amount", 
                "connect_person", "totalfright", "truck_freight", "universal_payment", 
                "trip_id", "ishtyaque", "google_url"
            ])
            # NaN वैल्यू हटाना ताकि SQL एरर न दे
            data_dict = df_bk.where(pd.notnull(df_bk), None).to_dict(orient='records')
            supabase.table("bookings").upsert(data_dict).execute()
            st.success(f"✅ {len(data_dict)} बुकिंग्स सिंक हो गईं!")
        
        # आप यहाँ दूसरी टेबल्स (Advances, Receivables) के लिए भी कोड जोड़ सकते हैं
        
    except Exception as e:
        st.error(f"❌ सिंक एरर: {e}")

# ==========================================
# 🖥️ MAIN APP
# ==========================================
if check_password():
    # फाइल इम्पोर्ट (सारे पुराने पेज)
    try:
        from booking import show_booking_page
        from advance import show_advance_page
        from receivable import show_receivable_page
        from daybook import show_daybook_page
        from dashboard import show_dashboard_page
        from transfer import show_transfer_page
        from reports import show_reports_page
        from pod import show_pod_page
        from company_hisaab import show_company_page
        from outstanding import show_outstanding_page
    except ImportError as e:
        st.error(f"❌ फाइल इम्पोर्ट में गलती: {e}"); st.stop()

    # ── Sidebar ──
    st.sidebar.markdown("<div style='text-align:center; padding: 12px 0;'><div style='font-size:1.8rem;'>🚛</div><div style='font-size:1rem; font-weight:900; color:white;'>Transport ERP</div></div>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state["password_correct"] = False; st.rerun()

    PAGES = [
        "🏠 होम (Home)", "बुकिंग", "एडवांस", "रिसिवेबल (पार्टी पेमेंट)", 
        "डे बुक (Credit/Debit)", "ट्रांसफर / पेमेंट (Contra)", 
        "रिपोर्ट्स (Reports)", "POD और फाइनल हिसाब", "🏢 कंपनी खाता", 
        "💸 लेना - देना (Outstanding)", "📊 डैशबोर्ड"
    ]
    choice = st.sidebar.radio("मेन्यू", PAGES, label_visibility="collapsed")

    # Routing
    if choice == "🏠 होम (Home)":
        st.markdown("<div style='text-align:center; padding-top:4vh;'><h1 style='color:#003399;'>BAZPUR UP TRANSPORT</h1></div>", unsafe_allow_html=True)
        
        # स्टेटस कार्ड्स
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", "Online", "Live Mode")
        c2.metric("Database", "G-Sheets + Supabase", "Synced")
        c3.metric("System", "Fast Engine", "Active")

        st.markdown("---")
        # 🔄 ADMIN SYNC BUTTON
        st.subheader("⚙️ डेटा सिंक्रोनाइजेशन (Admin Only)")
        st.write("गूगल शीट का नया डेटा Supabase में भेजने के लिए नीचे बटन दबाएँ:")
        if st.button("📤 सिंक करें (Google -> Supabase)", type="primary"):
            sync_data_to_supabase()

    elif choice == "बुकिंग": show_booking_page()
    elif choice == "एडवांस": show_advance_page()
    elif choice == "रिसिवेबल (पार्टी पेमेंट)": show_receivable_page()
    elif choice == "डे बुक (Credit/Debit)": show_daybook_page()
    elif choice == "ट्रांसफर / पेमेंट (Contra)": show_transfer_page()
    elif choice == "रिपोर्ट्स (Reports)": show_reports_page()
    elif choice == "POD और फाइनल हिसाब": show_pod_page()
    elif choice == "🏢 कंपनी खाता)": show_company_page()
    elif choice == "💸 लेना - देना (Outstanding)": show_outstanding_page()
    elif choice == "📊 डैशबोर्ड": show_dashboard_page()
