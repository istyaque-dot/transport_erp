import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 🗄️ DATABASE QUERIES (Google Sheets)
# ==========================================

from sheet_utils import connect_to_sheet, invalidate_sheet_cache

@st.cache_data(ttl=600)
def get_dashboard_data():
    """Google Sheets से dashboard numbers index-safe तरीके से निकालना."""
    from sheet_utils import worksheet_values, clean_amount

    banks_map = {
        "Cash": "Cash_Ledger",
        "Canara 311": "Canara_311_Ledger",
        "Canara 41": "Canara_41_Ledger",
        "BOB": "BOB_Ledger",
        "Canara 1747": "canara_1747",
        "Pump": "Shekh_Filling_Ledger",
    }

    results = {}
    for key, sheet_name in banks_map.items():
        rows = worksheet_values(sheet_name)
        total = 0
        for row in rows[1:]:
            if row:
                total += clean_amount(row[-1])
        results[key] = int(total)

    def ledger_balance(sheet_name):
        rows = worksheet_values(sheet_name)
        return int(sum(clean_amount(row[-1]) for row in rows[1:] if row))

    ish_bal = ledger_balance("Ishtyaque_Ledger")
    uni_bal = ledger_balance("Universal_Ledger")

    # गाड़ी वालों को देय = Owner Freight total - Advances total - final/shortage adjustments
    booking_rows = worksheet_values("Bookings")
    total_owner_freight = 0
    for row in booking_rows[1:]:
        # current Booking schema में Owner Freight index 12 है
        if len(row) > 12:
            total_owner_freight += clean_amount(row[12])

    adv_rows = worksheet_values("Advances")
    total_adv = 0
    for row in adv_rows[1:]:
        # New schema index 8, old fallback index 5
        total_adv += clean_amount(row[8] if len(row) > 8 else (row[5] if len(row) > 5 else 0))

    owner_rows = worksheet_values("Owner_Ledger")
    owner_adjustments = 0
    for row in owner_rows[1:]:
        if len(row) > 5 and any(k in str(row[4]) for k in ["Final Balance", "Shortage", "Extra", "Detention"]):
            owner_adjustments += clean_amount(row[5])

    payable = total_owner_freight - total_adv + owner_adjustments
    return results, ish_bal, uni_bal, int(payable)

# ==========================================
# 🎨 CSS
# ==========================================
DASH_CSS = """
<style>
.block-container { padding-top: 0.7rem !important; max-width: 98% !important; }
[data-testid="metric-container"] { border-radius: 9px !important; padding: 8px 12px !important; background: #f8faff !important; border: 1px solid #dde3f0 !important; }
[data-testid="stMetricValue"] { font-size: 1.05rem !important; font-weight: 800 !important; color: #003399 !important; }
.sum-card { border-radius: 10px; padding: 10px 16px; margin: 3px 0; font-size: 0.82rem; font-weight: 600; }
.sum-green { background:#d1e7dd; border-left:4px solid #198754; color:#0f5132; }
.sum-red { background:#fee2e2; border-left:4px solid #dc3545; color:#991b1b; }
.sum-blue { background:#dbeafe; border-left:4px solid #003399; color:#1e3a8a; }
.pill { background: #003399; color: white; border-radius: 20px; padding: 2px 14px; font-size: 0.74rem; font-weight: 700; display:inline-block; margin-bottom:5px; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_dashboard_page():
    st.markdown(DASH_CSS, unsafe_allow_html=True)

    # Header
    h1, h2 = st.columns([5, 1])
    with h1: st.header("📊 डैशबोर्ड — बिज़नेस समरी (Sheets)")
    with h2:
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            invalidate_sheet_cache()
            st.rerun()

    # Get Data
    bank_bals, ish_bal, uni_bal, payable = get_dashboard_data()

    # Define Bank Balances
    cash = bank_bals.get("Cash", 0)
    c311 = bank_bals.get("Canara 311", 0)
    c41 = bank_bals.get("Canara 41", 0)
    bob = bank_bals.get("BOB", 0)
    c1747 = bank_bals.get("Canara 1747", 0)
    pump = bank_bals.get("Pump", 0)

    total_liquidity = cash + c311 + c41 + bob + c1747

    # ── Top Summary Bar ──
    sb1, sb2, sb3 = st.columns(3)
    sb1.markdown(f"<div class='sum-card sum-blue'>💰 कुल बैंक + नकद<br><span style='font-size:1.1rem'>₹{total_liquidity:,}</span></div>", unsafe_allow_html=True)
    sb2.markdown(f"<div class='sum-card sum-red'>🚛 गाड़ी वालों को देना<br><span style='font-size:1.1rem'>₹{int(payable):,}</span></div>", unsafe_allow_html=True)
    
    net_pos = total_liquidity - int(payable)
    net_color = "sum-green" if net_pos >= 0 else "sum-red"
    sb3.markdown(f"<div class='sum-card {net_color}'>📊 नेट पोज़िशन<br><span style='font-size:1.1rem'>₹{net_pos:,}</span></div>", unsafe_allow_html=True)

    st.divider()

    # ── Bank & Cash ──
    st.markdown("<div class='pill'>🏦 बैंक और नकद</div>", unsafe_allow_html=True)
    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
    bc1.metric("💵 Cash", f"₹{cash:,}")
    bc2.metric("🏦 Canara 311", f"₹{c311:,}")
    bc3.metric("🏦 Canara 41", f"₹{c41:,}")
    bc4.metric("🏦 BOB", f"₹{bob:,}")
    bc5.metric("🏦 Canara 1747", f"₹{c1747:,}")

    st.divider()

    # ── Special Ledgers ──
    st.markdown("<div class='pill'>👤 खास खाते</div>", unsafe_allow_html=True)
    sp1, sp2, sp3 = st.columns(3)
    sp1.metric("👤 इश्तियाक भाई", f"₹{ish_bal:,}")
    sp2.metric("🏢 यूनिवर्सल", f"₹{uni_bal:,}")
    
    # Pump Status
    p_status = "देना बाकी ⏳" if pump < 0 else "एडवांस जमा ✅"
    sp3.metric("⛽ शेख फिलिंग", f"₹{abs(pump):,}", p_status, delta_color="inverse" if pump < 0 else "normal")

    st.markdown("<div style='text-align:center; color:#bbb; font-size:0.7rem; margin-top:5vh;'>डेटा सीधे Google Sheets से आ रहा है · Khan Transport ERP v1.0</div>", unsafe_allow_html=True)
