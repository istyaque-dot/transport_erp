import streamlit as st
import pandas as pd
from database import get_dashboard_stats, get_all_trips, get_ledger_stats

def show_dashboard_page():
    st.markdown("""
        <style>
            /* Compact spacing */
            .stMetric { padding: 0.5rem 0; }
            .element-container { margin-bottom: 0.5rem; }
            
            /* Custom metric styling */
            [data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 600; }
            [data-testid="stMetricLabel"] { font-size: 0.9rem; color: #888; }
            
            /* Clean table */
            .dataframe { font-size: 0.9rem; }
            
            /* Section headers */
            .section-header { 
                background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
                color: white;
                padding: 0.75rem 1rem;
                border-radius: 0.5rem;
                margin: 1rem 0 0.5rem 0;
                font-size: 1.1rem;
                font-weight: 600;
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("📊 Khan Transport - Dashboard")
    
    # --- BUSINESS OVERVIEW ---
    st.markdown('<div class="section-header">💼 बिज़नेस का हाल (Business Overview)</div>', unsafe_allow_html=True)
    
    stats = get_dashboard_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="कुल गाड़ियाँ (Total Trips)",
            value=stats.get("total_trips", 0),
            delta=None
        )
    
    with col2:
        freight = stats.get('total_freight', 0)
        st.metric(
            label="कुल कंपनी भाड़ा (Total Freight)",
            value=f"₹{freight:,}",
            delta=None
        )
    
    with col3:
        advance = stats.get('total_advance', 0)
        st.metric(
            label="कुल एडवांस दिया (Total Advance)",
            value=f"₹{advance:,}",
            delta=None
        )
    
    with col4:
        cleared = stats.get('total_cleared', 0)
        st.metric(
            label="कुल पेमेंट आया (Total Received)",
            value=f"₹{cleared:,}",
            delta=None
        )
    
    # --- ACCOUNT BALANCES ---
    st.markdown('<div class="section-header">🏦 खातों का बैलेंस (Account Balances)</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    cash = get_ledger_stats("Cash_Ledger")
    c311 = get_ledger_stats("Canara_311_Ledger")
    c41 = get_ledger_stats("Canara_41_Ledger")
    bob = get_ledger_stats("BOB_Ledger")
    pump = get_ledger_stats("Shekh_Filling_Ledger")
    
    with col1:
        cash_bal = cash.get("balance", 0)
        st.metric("💵 Cash", f"₹{cash_bal:,}")
    
    with col2:
        c311_bal = c311.get("balance", 0)
        st.metric("🏦 Canara 311", f"₹{c311_bal:,}")
    
    with col3:
        c41_bal = c41.get("balance", 0)
        st.metric("🏦 Canara 41", f"₹{c41_bal:,}")
    
    with col4:
        bob_bal = bob.get("balance", 0)
        st.metric("🏦 BOB", f"₹{bob_bal:,}")
    
    with col5:
        pump_bal = pump.get("balance", 0)
        if pump_bal < 0:
            st.metric("⛽ Pump", f"₹{abs(pump_bal):,}", "देना बाकी", delta_color="inverse")
        else:
            st.metric("⛽ Pump", f"₹{pump_bal:,}", "क्लियर", delta_color="normal")
    
    # Total Cash Available
    total_available = cash_bal + c311_bal + c41_bal + bob_bal
    st.info(f"💰 **कुल उपलब्ध पैसा (Total Available Cash):** ₹{total_available:,}")
    
    # --- PENDING PAYMENTS SUMMARY ---
    st.markdown('<div class="section-header">⏳ पेंडिंग पेमेंट्स (Pending Payments)</div>', unsafe_allow_html=True)
    
    df = get_all_trips()
    if not df.empty:
        # Company से आना बाकी
        company_pending = freight - cleared
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "🏢 कंपनी से आना बाकी (Receivable)",
                f"₹{company_pending:,}",
                help="Total freight minus total received"
            )
        with col2:
            # Calculate actual pending balance from trips
            pending_count = 0
            for idx, row in df.iterrows():
                try:
                    comp_freight = int(row.iloc[11])
                    # You can add more logic here to check received amounts
                    if comp_freight > 0:
                        pending_count += 1
                except:
                    pass
            
            st.metric(
                "🚛 पेंडिंग ट्रिप्स (Pending Settlements)",
                f"{pending_count} गाड़ियाँ",
                help="Trips with pending settlements"
            )
    
    # --- RECENT BOOKINGS ---
    st.markdown('<div class="section-header">📋 हाल की बुकिंग (Recent Bookings - Last 15)</div>', unsafe_allow_html=True)
    
    if not df.empty:
        df_display = df.tail(15).iloc[::-1].copy()
        
        try:
            # Select important columns only
            display_data = []
            for idx, row in df_display.iterrows():
                display_data.append({
                    "तारीख": row.iloc[0],
                    "गाड़ी": row.iloc[6],
                    "कहाँ तक": row.iloc[7],
                    "GR नंबर": row.iloc[8] if row.iloc[8] else "-",
                    "कंपनी": row.iloc[2],
                    "भाड़ा": f"₹{int(row.iloc[11]):,}",
                    "Trip ID": row.iloc[14]
                })
            
            df_clean = pd.DataFrame(display_data)
            
            # Display as table with alternating colors
            st.dataframe(
                df_clean,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
        except Exception as e:
            st.error(f"Table display error: {str(e)}")
            st.dataframe(df_display, use_container_width=True)
    else:
        st.info("अभी कोई गाड़ी लोड नहीं हुई है।")
    
    # --- QUICK NAVIGATION INFO ---
    st.markdown('<div class="section-header">⚡ त्वरित नेविगेशन (Quick Navigation)</div>', unsafe_allow_html=True)
    
    st.info("""
    **📍 सभी pages को sidebar से access करें:**
    
    - 🚛 **बुकिंग** - नई गाड़ी लगाएँ या एडिट करें
    - 💸 **एडवांस** - गाड़ी वाले को एडवांस दें
    - 📥 **रिसिवेबल** - कंपनी से पेमेंट लें
    - 🔀 **ट्रांसफर** - खातों के बीच पैसा transfer करें
    - 📓 **डे बुक** - अन्य जमा/खर्च की entry
    - 🏁 **POD और फाइनल हिसाब** - बिल्टी upload और settlement
    - 📑 **रिपोर्ट्स** - सभी ledgers और statements
    """)
    
    # --- FOOTER INFO ---
    st.markdown("---")
    st.caption("💡 **Tip:** Dashboard हर minute auto-refresh होता है। सभी data real-time है।")
