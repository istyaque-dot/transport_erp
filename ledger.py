import streamlit as st


def show_ledger_page():
    st.header("📒 लेजर / हिसाब-किताब")
    st.info("Quota-safe mode: Ledger Hub में अब सभी pages एक साथ load नहीं होंगे। नीचे सिर्फ एक section खोलें।")

    section = st.radio(
        "Section चुनें",
        ["🔀 Transfer", "📓 Day Book", "💸 Outstanding", "🏢 Company Hisaab"],
        horizontal=True,
    )

    try:
        if section == "🔀 Transfer":
            from transfer import show_transfer_page
            show_transfer_page()
        elif section == "📓 Day Book":
            from daybook import show_daybook_page
            show_daybook_page()
        elif section == "💸 Outstanding":
            from outstanding import show_outstanding_page
            show_outstanding_page()
        elif section == "🏢 Company Hisaab":
            from company_hisaab import show_company_page
            show_company_page()
    except Exception as e:
        st.error(f"Ledger section error: {e}")
