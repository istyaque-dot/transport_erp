import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🗄️ DATABASE — Unchanged
# ==========================================

@st.cache_resource
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["gcp_service_account"]), scope)
    return gspread.authorize(creds).open("Khan_Transport_ERP")

def clean_amt(val):
    try:
        return float(str(val).replace(',','').replace('₹','').strip()) if str(val).strip() else 0
    except: return 0

@st.cache_data(ttl=30)
def get_ledger_balance(sheet_name):
    try:
        data = connect_to_sheet().worksheet(sheet_name).get_all_values()
        if len(data) > 1:
            df   = pd.DataFrame(data[1:], columns=data[0])
            vals = df.iloc[:,-1].astype(str).str.replace(',','').str.replace('₹','').str.strip()
            return int(pd.to_numeric(vals, errors='coerce').fillna(0).sum())
    except: pass
    return 0

@st.cache_data(ttl=60)
def get_truck_payable():
    try:
        db      = connect_to_sheet()
        bk_raw  = db.worksheet("Bookings").get_all_values()
        adv_raw = db.worksheet("Advances").get_all_values()
        own_raw = db.worksheet("Owner_Ledger").get_all_values()

        df_bk   = pd.DataFrame(bk_raw[1:], columns=bk_raw[0])

        adv_map = {}
        for r in adv_raw[1:]:
            if len(r) > 8:
                tid = str(r[1]).strip()
                adv_map[tid] = adv_map.get(tid, 0) + clean_amt(r[8])

        own_map = {}
        for r in own_raw[1:]:
            if len(r) > 5:
                tid  = str(r[1]).strip()
                desc = str(r[4])
                if any(x in desc for x in ["Final Balance","Shortage","Extra","Detention"]):
                    own_map[tid] = own_map.get(tid, 0) + clean_amt(r[5])

        total = 0
        for _, row in df_bk.iterrows():
            if len(row) < 15: continue
            tid    = str(row.iloc[14]).strip()
            own_fr = clean_amt(row.iloc[12])
            if own_fr > 0:
                mun   = clean_amt(row.iloc[5])
                bal   = (own_fr - mun) - adv_map.get(tid,0) + own_map.get(tid,0)
                if bal > 10: total += bal
        return total
    except: return 0

# ==========================================
# 🎨 CSS
# ==========================================

DASH_CSS = """
<style>
.block-container {
    padding-top: 0.7rem !important;
    padding-bottom: 0.3rem !important;
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
    max-width: 98% !important;
}
h2 { font-size: 1.15rem !important; margin: 0 0 3px 0 !important; }
.element-container { margin-bottom: 0.1rem !important; }
[data-testid="stVerticalBlock"]   { gap: 0.12rem !important; }
[data-testid="stHorizontalBlock"] { gap: 0.45rem !important; }

/* ── Metric cards ── */
[data-testid="metric-container"] {
    border-radius: 9px !important;
    padding: 8px 12px !important;
    border: 1px solid #dde3f0 !important;
    background: #f8faff !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(0,51,153,0.10) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    color: #003399 !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    color: #555 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.66rem !important; }

/* ── Buttons ── */
[data-testid="stButton"] button {
    border-radius: 6px !important;
    min-height: 1.7rem !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    padding: 0 14px !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg,#003399,#0055cc) !important;
    color:#fff !important; border:none !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    padding: 5px 10px !important;
    margin: 2px 0 !important;
}
[data-testid="stAlert"] p { font-size: 0.78rem !important; margin:0 !important; }

hr { margin: 0.25em 0 !important; border-color: #e8edf5 !important; }

/* ── Section pill ── */
.pill {
    display: inline-block;
    background: #003399; color: white;
    border-radius: 20px; padding: 2px 14px;
    font-size: 0.74rem; font-weight: 700;
    margin: 5px 0 4px 0;
}

/* ── Summary card ── */
.sum-card {
    border-radius: 10px;
    padding: 10px 16px;
    margin: 3px 0;
    font-size: 0.82rem;
    font-weight: 600;
}
.sum-green  { background:#d1e7dd; border:1px solid #0f5132; border-left:4px solid #198754; color:#0f5132; }
.sum-red    { background:#fee2e2; border:1px solid #f87171; border-left:4px solid #dc3545; color:#991b1b; }
.sum-blue   { background:#dbeafe; border:1px solid #93c5fd; border-left:4px solid #003399; color:#1e3a8a; }
.sum-yellow { background:#fff3cd; border:1px solid #ffc107; border-left:4px solid #f59e0b; color:#856404; }

/* ── Bank card with color bar ── */
.bank-wrap [data-testid="metric-container"]:nth-child(1) { border-top: 3px solid #22c55e !important; }
.bank-wrap [data-testid="metric-container"]:nth-child(2) { border-top: 3px solid #003399 !important; }
.bank-wrap [data-testid="metric-container"]:nth-child(3) { border-top: 3px solid #0ea5e9 !important; }
.bank-wrap [data-testid="metric-container"]:nth-child(4) { border-top: 3px solid #f59e0b !important; }
.bank-wrap [data-testid="metric-container"]:nth-child(5) { border-top: 3px solid #8b5cf6 !important; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_dashboard_page():
    st.markdown(DASH_CSS, unsafe_allow_html=True)

    # ── Header row ──
    h1, h2 = st.columns([5, 1])
    with h1: st.header("📊 डैशबोर्ड — बिज़नेस समरी")
    with h2:
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Fetch all balances ──
    cash      = get_ledger_balance("Cash_Ledger")
    c311      = get_ledger_balance("Canara_311_Ledger")
    c41       = get_ledger_balance("Canara_41_Ledger")
    bob       = get_ledger_balance("BOB_Ledger")
    c1747     = get_ledger_balance("canara_1747")
    ishtyaque = get_ledger_balance("Ishtyaque_Ledger")
    universal = get_ledger_balance("Universal_Ledger")
    pump      = get_ledger_balance("Shekh_Filling_Ledger")
    payable   = get_truck_payable()

    total_bank = cash + c311 + c41 + bob + c1747

    # ── Summary bar ──
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    sb1, sb2, sb3 = st.columns(3)
    sb1.markdown(
        f"<div class='sum-card sum-blue'>💰 कुल बैंक + नकद<br>"
        f"<span style='font-size:1.1rem'>₹{total_bank:,}</span></div>",
        unsafe_allow_html=True)
    sb2.markdown(
        f"<div class='sum-card sum-red'>🚛 गाड़ी वालों को देना<br>"
        f"<span style='font-size:1.1rem'>₹{int(payable):,}</span></div>",
        unsafe_allow_html=True)
    net = total_bank - int(payable)
    color = "sum-green" if net >= 0 else "sum-red"
    sb3.markdown(
        f"<div class='sum-card {color}'>📊 नेट पोज़िशन (अनुमानित)<br>"
        f"<span style='font-size:1.1rem'>₹{net:,}</span></div>",
        unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Section 1: Bank & Cash ──
    st.markdown("<div class='pill'>🏦 बैंक और नकद</div>", unsafe_allow_html=True)
    st.markdown("<div class='bank-wrap'>", unsafe_allow_html=True)
    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
    bc1.metric("💵 गल्ला (Cash)",     f"₹{cash:,}")
    bc2.metric("🏦 Canara 311",        f"₹{c311:,}")
    bc3.metric("🏦 Canara 41",         f"₹{c41:,}")
    bc4.metric("🏦 BOB",               f"₹{bob:,}")
    bc5.metric("🏦 Canara 1747",       f"₹{c1747:,}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Section 2: Special Ledgers ──
    st.markdown("<div class='pill'>👤 खास खाते</div>", unsafe_allow_html=True)
    sp1, sp2, sp3 = st.columns(3)
    sp1.metric("👤 इश्तियाक भाई",    f"₹{ishtyaque:,}")
    sp2.metric("🏢 यूनिवर्सल",        f"₹{universal:,}")

    # Pump — smart display
    if pump < 0:
        sp3.metric("⛽ शेख फिलिंग",   f"₹{abs(pump):,}", "देना बाकी ⏳", delta_color="inverse")
    elif pump > 0:
        sp3.metric("⛽ शेख फिलिंग",   f"₹{pump:,}",      "एडवांस जमा ✅", delta_color="normal")
    else:
        sp3.metric("⛽ शेख फिलिंग",   "₹0",               "क्लियर ✅",     delta_color="off")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Section 3: Payables ──
    st.markdown("<div class='pill'>🚛 गाड़ी वालों की देनदारी</div>", unsafe_allow_html=True)
    pd1, pd2 = st.columns([1, 2])

    with pd1:
        if payable > 0:
            st.markdown(
                f"<div class='sum-card sum-red' style='font-size:0.9rem'>"
                f"🔴 कुल देना है<br>"
                f"<span style='font-size:1.3rem; font-weight:900'>₹{int(payable):,}</span>"
                f"</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='sum-card sum-green' style='font-size:0.9rem'>"
                "✅ कोई देनदारी नहीं</div>",
                unsafe_allow_html=True)

    with pd2:
        st.markdown(
            "<div class='sum-card sum-yellow'>"
            "💡 डिटेल हिसाब देखने के लिए साइड मेनू से "
            "<b>💸 लेना - देना (Outstanding)</b> पेज पर जाएँ।"
            "</div>",
            unsafe_allow_html=True)

    # ── Footer ──
    st.markdown(
        "<div style='text-align:center; color:#bbb; font-size:0.7rem; margin-top:3vh;'>"
        "डेटा हर 30 सेकंड में ऑटो-अपडेट होता है · Khan Transport ERP v2.0"
        "</div>",
        unsafe_allow_html=True)
