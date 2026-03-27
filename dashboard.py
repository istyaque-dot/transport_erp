import streamlit as st
import pandas as pd
from database import get_dashboard_stats, get_all_trips

def show_dashboard_page():
    st.header("📊 डैशबोर्ड (Dashboard)")
    
    stats = get_dashboard_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("कुल गाड़ियाँ", stats.get("total_trips", 0))
    col2.metric("कुल कंपनी भाड़ा", f"₹{stats.get('total_freight', 0):,}")
    col3.metric("कुल एडवांस दिया", f"₹{stats.get('total_advance', 0):,}")
    col4.metric("कुल रिसीव (क्लियर)", f"₹{stats.get('total_cleared', 0):,}")
    
    st.write("---")
    st.subheader("📋 हाल ही की बुकिंग (Recent Bookings)")
    
    df = get_all_trips()
    if not df.empty:
        df_display = df.tail(10).iloc[::-1]
        try:
            # 5 ज़रूरी चीज़ें दिखाना: Date, Truck, To, Company, Comp_Freight
            display_cols = df_display.iloc[:, [0, 6, 7, 2, 11]]
            display_cols.columns = ["तारीख", "गाड़ी नंबर", "कहाँ तक", "कंपनी", "भाड़ा"]
            st.dataframe(display_cols, use_container_width=True)
        except:
            st.dataframe(df_display, use_container_width=True)
    else:
        st.info("अभी कोई गाड़ी लोड नहीं हुई है।")
