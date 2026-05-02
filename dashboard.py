import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ==========================================
# 🚀 SUPABASE CONFIG
# ==========================================
SUPABASE_URL = "https://tsyghmvqrlxwicipkvqw.supabase.co"
SUPABASE_KEY = "sb_publishable_p0_eR7aMIL5KDvUkiwm18g_t1OtXBDv"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# ==========================================
# 🗄️ DATABASE QUERIES (Supabase)
# ==========================================

@st.cache_data(ttl=30)
def get_all_balances():
    """एक ही क्वेरी में सारे बैंकों और खास खातों का बैलेंस निकालना"""
    try:
        # Bank Ledgers से बैलेंस (Group by bank_name)
        res = supabase.table("bank_ledgers").select("bank_name, amount").execute()
        df = pd.DataFrame(res.data)
        balances = df.groupby("bank_name")["amount"].sum().to_dict() if not df.empty else {}
        
        # Ishtyaque और Universal Ledger से बैलेंस
        ish_res = supabase.table("ishtyaque_ledger").select("amount").execute()
        ish_bal = sum(item['amount'] for item in ish_res.data) if ish_res.data else 0
        
        uni_res = supabase.table("universal_ledger").select("amount").execute()
        uni_bal = sum(item['amount'] for item in uni_res.data) if uni_res.data else 0
        
        return balances, ish_bal, uni_bal
    except:
        return {}, 0, 0

@st.cache_data(ttl=60)
def get_truck_payable_v2():
    """गाड़ी वालों को कुल कितना देना बाकी है (Bookings - Advances)"""
    try:
        # 1. कुल गाड़ी भाड़ा (Bookings)
        bk_res = supabase.table("bookings").select("owner_freight, uni_amt").execute()
        total_fr = sum(float(row['owner_freight']) - float(row['uni_amt']) for row in bk_res.data)
        
        # 2. अब तक दिया गया एडवांस
        adv_res = supabase.table("advances").select("amount").execute()
        total_adv = sum(float(row['amount']) for row in adv_res.data)
        
        return total_fr - total_adv
    except: return 0

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
.pill { background: #003399; color: white; border-radius: 20px; padding: 2px 14px; font-size: 0.74rem; font-weight: 700; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_dashboard_page():
    st.markdown(DASH_CSS, unsafe_allow_html=True)

    # Header
    h1, h2 = st.columns([5, 1])
    with h1: st.header("📊 डैशबोर्ड — बिज़नेस समरी (V2)")
    with h2:
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Get Data
    bank_bals, ish_bal, uni_bal = get_all_balances()
    payable = get_truck_payable_v2()

    # Define Bank Balances (Safe fetch)
    cash = bank_bals.get("Cash", 0)
    c311 = bank_bals.get("Canara 311", 0)
    c41 = bank_bals.get("Canara 41", 0)
    bob = bank_bals.get("BOB", 0)
    c1747 = bank_bals.get("Canara 1747", 0)
    pump = bank_bals.get("Pump (Shekh Filling)", 0)

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

    st.markdown("<div style='text-align:center; color:#bbb; font-size:0.7rem; margin-top:5vh;'>डेटा सीधे Supabase से आ रहा है · Khan Transport ERP v2.0</div>", unsafe_allow_html=True)
