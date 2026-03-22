import streamlit as st
import datetime

st.set_page_config(page_title="Khan Transport ERP", page_icon="🚛", layout="wide")

# ==========================================
# 🖥️ MAIN ERP APP (Direct Entry - No Password Needed)
# ==========================================

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