import streamlit as st


def show_ledger_page():
    st.header("📒 लेजर / हिसाब-किताब")
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔀 Transfer",
        "📓 Day Book",
        "💸 Outstanding",
        "🏢 Company Hisaab",
    ])

    with tab1:
        try:
            from transfer import show_transfer_page
            show_transfer_page()
        except Exception as e:
            st.error(f"Transfer page error: {e}")

    with tab2:
        try:
            from daybook import show_daybook_page
            show_daybook_page()
        except Exception as e:
            st.error(f"Day Book page error: {e}")

    with tab3:
        try:
            from outstanding import show_outstanding_page
            show_outstanding_page()
        except Exception as e:
            st.error(f"Outstanding page error: {e}")

    with tab4:
        try:
            from company_hisaab import show_company_page
            show_company_page()
        except Exception as e:
            st.error(f"Company Hisaab page error: {e}")
