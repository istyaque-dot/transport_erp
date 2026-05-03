# ==========================================
# 🖥️ MAIN APP LOGIC (Direct Routing - No Hidden Errors)
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

    # ⚠️ अब यहाँ कोई 'try...except' नहीं है, असली एरर दिखेगा
    elif choice == "बुकिंग":
        import booking
        booking.show_booking_page()
        
    elif choice == "एडवांस":
        import advance
        advance.show_advance_page()
        
    elif choice == "POD":
        import pod
        pod.show_pod_page()
        
    elif choice == "रिसीवेबल":
        import receivable
        receivable.show_receivable_page()
        
    elif choice == "लेजर":
        import ledger
        ledger.show_ledger_page()
        
    elif choice == "📊 डैशबोर्ड":
        import dashboard
        dashboard.show_dashboard_page()
        
    elif choice == "रिपोर्ट्स":
        import reports
        reports.show_reports_page()
