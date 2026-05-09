import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 🗄️ DATABASE
# ==========================================

from sheet_utils import connect_to_sheet, invalidate_sheet_cache

@st.cache_data(ttl=600)
def get_all_trips():
    try:
        data = connect_to_sheet().worksheet("Bookings").get_all_values()
        return pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_company_balance_details(trip_id):
    try:
        data  = connect_to_sheet().worksheet("Company_Ledger").get_all_values()
        total = 0
        for row in data[1:]:
            if len(row) > 5 and str(row[1]).strip() == str(trip_id).strip():
                try: total += int(float(str(row[5]).replace(',', '')))
                except: pass
        return total
    except: return 0

@st.cache_data(ttl=600)
def get_pod_link(trip_id):
    try:
        data = connect_to_sheet().worksheet("Owner_Ledger").get_all_values()
        for row in data[1:]:
            if len(row) > 4 and str(row[1]).strip() == str(trip_id).strip():
                if "POD Link:" in str(row[4]):
                    return str(row[4]).replace("POD Link:", "").strip()
        return None
    except: return None

def save_company_payment(date_val, trip_id, gr_no, truck_no,
                         pay_received, bank_name, shortage, tds, extra_km, remarks):
    try:
        db   = connect_to_sheet()
        rows = []
        if extra_km    > 0: rows.append([str(date_val), trip_id, gr_no, truck_no, f"Detention/Extra: {remarks}",  int(extra_km)])
        if shortage    > 0: rows.append([str(date_val), trip_id, gr_no, truck_no, f"Shortage: {remarks}",        -int(shortage)])
        if tds         > 0: rows.append([str(date_val), trip_id, gr_no, truck_no, f"TDS Deduction: {remarks}",   -int(tds)])
        if pay_received > 0: rows.append([str(date_val), trip_id, gr_no, truck_no, f"Payment Recvd: {remarks}",   -int(pay_received)])

        if rows:
            db.worksheet("Company_Ledger").append_rows(rows, table_range="A1")

        if pay_received > 0:
            s_map = {
                "Cash":            "Cash_Ledger",
                "canara bank 311": "Canara_311_Ledger",
                "canara bank 41":  "Canara_41_Ledger",
                "bob":             "BOB_Ledger",
                "Canara 1747":     "canara_1747"
            }
            s_name = s_map.get(bank_name)
            if s_name:
                if s_name == "canara_1747":
                    db.worksheet(s_name).append_row(
                        [str(date_val), f"Company Pay ({gr_no}) - {truck_no}",
                         "From: Company", int(pay_received)], table_range="A1")
                else:
                    db.worksheet(s_name).append_row(
                        [str(date_val), trip_id, gr_no,
                         f"Comp Pay: {truck_no} | {remarks}", int(pay_received)],
                        table_range="A1")
        invalidate_sheet_cache()
        return True
    except: return False

# ==========================================
# 🎨 CSS
# ==========================================

CSS = """
<style>
.block-container {
    padding-top: 0.7rem !important; padding-bottom: 0.3rem !important;
    padding-left: 1.2rem !important; padding-right: 1.2rem !important;
    max-width: 98% !important;
}
h2 { font-size: 1.15rem !important; margin: 0 0 3px 0 !important; }
.element-container { margin-bottom: 0.1rem !important; margin-top: 0 !important; }
[data-testid="stVerticalBlock"]   { gap: 0.12rem !important; }
[data-testid="stHorizontalBlock"] { gap: 0.45rem !important; }
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 0.18rem !important; }

[data-testid="stForm"] {
    background:#fff !important; border:1px solid #dde3f0 !important;
    border-radius:10px !important; padding:10px 14px 10px 14px !important;
    box-shadow:0 1px 4px rgba(0,0,0,0.05) !important;
}
[data-baseweb="input"] { border-radius:6px !important; min-height:1.7rem !important; }
[data-baseweb="input"] input {
    font-size:0.81rem !important; padding:2px 8px !important;
    min-height:1.7rem !important; background:#fafafa !important;
}
[data-baseweb="input"]:focus-within {
    border-color:#003399 !important;
    box-shadow:0 0 0 2px rgba(0,51,153,0.08) !important;
}
[data-baseweb="select"] > div:first-child {
    border-radius:6px !important; min-height:1.7rem !important;
    font-size:0.81rem !important; background:#fafafa !important;
}
[data-testid="stNumberInput"] [data-baseweb="input"] input {
    font-size:0.81rem !important; min-height:1.7rem !important;
}
label, [data-testid="stWidgetLabel"] p {
    font-size:0.73rem !important; font-weight:700 !important;
    color:#374151 !important; margin-bottom:0 !important; line-height:1.1 !important;
}
[data-testid="stButton"] button {
    border-radius:6px !important; min-height:1.7rem !important;
    font-size:0.81rem !important; font-weight:600 !important; padding:0 12px !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background:linear-gradient(135deg,#003399,#0055cc) !important;
    color:#fff !important; border:none !important;
}
[data-testid="stFormSubmitButton"] button {
    background:linear-gradient(135deg,#003399,#0055cc) !important;
    color:#fff !important; border-radius:6px !important;
    font-size:0.82rem !important; font-weight:700 !important;
    min-height:1.8rem !important; width:100% !important;
}
[data-testid="stAlert"] {
    border-radius:6px !important; padding:4px 10px !important; margin:2px 0 !important;
}
[data-testid="stAlert"] p { font-size:0.8rem !important; margin:0 !important; }

/* Metrics */
[data-testid="metric-container"] {
    background:#f8faff !important; border:1px solid #dde3f0 !important;
    border-radius:7px !important; padding:6px 10px !important;
}
[data-testid="stMetricValue"] {
    font-size:0.92rem !important; font-weight:800 !important;
    color:#003399 !important; line-height:1.2 !important;
}
[data-testid="stMetricLabel"] { font-size:0.64rem !important; font-weight:600 !important; color:#666 !important; }
[data-testid="stMetricDelta"] { font-size:0.64rem !important; }

hr { margin:0.25em 0 !important; border-color:#e8edf5 !important; }

/* Trip bar */
.trip-bar {
    display:flex; align-items:center; flex-wrap:wrap; gap:5px;
    background:#f0f4ff; border-left:4px solid #003399;
    border-radius:0 8px 8px 0; padding:7px 14px; margin:3px 0 4px 0;
}
.trip-chip {
    background:#fff; border:1px solid #c7d4f5; border-radius:20px;
    padding:1px 10px; font-size:0.74rem; font-weight:700; color:#003399;
}

/* Pill header */
.pill {
    display:inline-block; background:#003399; color:white;
    border-radius:20px; padding:2px 14px;
    font-size:0.73rem; font-weight:700; margin:5px 0 3px 0;
}

/* Doc cards */
.doc-ok   { background:#d1e7dd; border:1px solid #0f5132; border-radius:7px;
            padding:5px 12px; font-size:0.76rem; font-weight:700;
            color:#0f5132; text-align:center; margin-bottom:3px; }
.doc-miss { background:#fff3cd; border:1px solid #ffc107; border-radius:7px;
            padding:5px 12px; font-size:0.76rem; font-weight:700;
            color:#856404; text-align:center; margin-bottom:3px; }

/* Balance cards */
.bal-clear {
    background:#d1e7dd; border:1px solid #0f5132;
    border-left:4px solid #198754; border-radius:8px;
    padding:8px 16px; color:#0f5132; font-weight:700;
    font-size:0.85rem; margin:4px 0;
}
.bal-due {
    background:#fff3cd; border:1px solid #ffc107;
    border-left:4px solid #f59e0b; border-radius:8px;
    padding:8px 16px; color:#856404; font-weight:700;
    font-size:0.88rem; margin:4px 0;
    display:flex; justify-content:space-between; align-items:center;
}

/* Sub-group label inside form */
.grp {
    font-size:0.72rem; font-weight:700; color:#003399;
    background:#f0f4ff; border-radius:5px;
    padding:2px 10px; margin:4px 0 2px 0; display:inline-block;
}

/* Live summary row */
.live-row {
    background:#f0f4ff; border:1px solid #c7d4f5;
    border-radius:8px; padding:6px 12px;
    display:flex; gap:20px; flex-wrap:wrap;
    font-size:0.8rem; font-weight:600; margin-top:4px;
}
.live-item { display:flex; flex-direction:column; align-items:center; }
.live-val  { font-size:1rem; font-weight:800; color:#003399; }
.live-lbl  { font-size:0.65rem; color:#666; }
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_company_page():
    st.markdown(CSS, unsafe_allow_html=True)

    # Header + Refresh
    h1, h2 = st.columns([5, 1])
    with h1: st.header("🏢 कंपनी खाता और सेटलमेंट")
    with h2:
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            invalidate_sheet_cache(); st.rerun()

    df_trips = get_all_trips()
    if df_trips.empty:
        st.info("कोई डेटा नहीं मिला।"); return

    # ── Trip Selector ──
    df_last = df_trips.tail(150).iloc[::-1]
    labels, trip_ids = [], []
    for _, row in df_last.iterrows():
        try:
            gr = str(row.iloc[8]) if str(row.iloc[8]).lower() not in ("nan","") else "—"
            labels.append(
                f"🚛 {row.iloc[6]}  |  📅 {str(row.iloc[0])[:10]}  |  "
                f"📍 {row.iloc[7]}  |  GR: {gr}")
            trip_ids.append(str(row.iloc[14]))
        except: pass

    selected = st.selectbox(
        "गाड़ी खोजें:", ["चुनें..."] + labels,
        label_visibility="collapsed")

    if selected == "चुनें...":
        st.caption("👆 GR नंबर, गाड़ी नंबर या कंपनी का नाम टाइप करके खोजें।")
        return

    idx      = labels.index(selected)
    trip_id  = trip_ids[idx]
    row_data = df_last[df_last.iloc[:, 14].astype(str) == trip_id].iloc[0]

    gr_no    = str(row_data.iloc[8])
    truck_no = str(row_data.iloc[6])
    comp     = str(row_data.iloc[2])
    dest     = str(row_data.iloc[7])
    t_date   = str(row_data.iloc[0])[:10]
    try:    freight = int(float(str(row_data.iloc[11]).replace(',', '')))
    except: freight = 0

    # ── Trip Bar ──
    st.markdown(f"""
        <div class='trip-bar'>
            <span class='trip-chip'>🚛 {truck_no}</span>
            <span class='trip-chip'>🏢 {comp}</span>
            <span class='trip-chip'>📄 GR: {gr_no}</span>
            <span class='trip-chip'>📍 {dest}</span>
            <span class='trip-chip'>📅 {t_date}</span>
            <span class='trip-chip'>💰 ₹{freight:,}</span>
        </div>
    """, unsafe_allow_html=True)

    # ── Documents ──
    gr_link = None
    if len(row_data) > 16 and pd.notna(row_data.iloc[16]) and "http" in str(row_data.iloc[16]):
        gr_link = str(row_data.iloc[16]).strip()
    pod_link = get_pod_link(trip_id)

    st.markdown("<div class='pill'>📄 डॉक्यूमेंट्स</div>", unsafe_allow_html=True)
    dc1, dc2 = st.columns(2)
    with dc1:
        if gr_link:
            st.markdown("<div class='doc-ok'>✅ GR (बिल्टी) अपलोड है</div>", unsafe_allow_html=True)
            st.link_button("📄 GR देखें", gr_link, use_container_width=True)
        else:
            st.markdown("<div class='doc-miss'>⚠️ GR अभी अपलोड नहीं</div>", unsafe_allow_html=True)
    with dc2:
        if pod_link:
            st.markdown("<div class='doc-ok'>✅ POD (रिसीविंग) अपलोड है</div>", unsafe_allow_html=True)
            st.link_button("🏁 POD देखें", pod_link, use_container_width=True)
        else:
            st.markdown("<div class='doc-miss'>⚠️ POD अभी अपलोड नहीं</div>", unsafe_allow_html=True)

    # ── Balance Status ──
    st.markdown("<hr>", unsafe_allow_html=True)
    balance = get_company_balance_details(trip_id)

    tds_exp  = int(freight * 0.01)
    hold_exp = int(freight * 0.10)

    if balance <= 0:
        st.markdown(
            f"<div class='bal-clear'>✅ हिसाब पूरा — कोई बकाया नहीं &nbsp;|&nbsp; बैलेंस: ₹{balance:,}</div>",
            unsafe_allow_html=True)
        return

    # Balance due
    st.markdown(
        f"<div class='bal-due'>"
        f"<span>💰 बकाया राशि (Balance Due)</span>"
        f"<span style='font-size:1.15rem'>₹{balance:,}</span>"
        f"</div>", unsafe_allow_html=True)

    st.markdown("<div class='pill'>📊 अनुमानित हिसाब</div>", unsafe_allow_html=True)
    bm1, bm2, bm3, bm4 = st.columns(4)
    bm1.metric("💰 कुल भाड़ा",          f"₹{freight:,}")
    bm2.metric("📉 TDS 1%",             f"₹{tds_exp:,}")
    bm3.metric("🔒 10% रोक",            f"₹{hold_exp:,}")
    bm4.metric("✅ नेट मिलना चाहिए",    f"₹{freight - tds_exp - hold_exp:,}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Payment Form ──
    with st.form("payment_form"):
        st.markdown("<div class='pill'>💳 पेमेंट / कटौती एंट्री</div>",
                    unsafe_allow_html=True)
        st.markdown("<div style='height:3px'></div>", unsafe_allow_html=True)

        # बैंक में आया पेमेंट
        st.markdown("<div class='grp'>📥 बैंक में आया पेमेंट</div>", unsafe_allow_html=True)
        g1c1, g1c2 = st.columns(2)
        with g1c1: pay_rec = st.number_input("💵 अमाउंट (₹)", min_value=0, step=100, key="pay")
        with g1c2: bank    = st.selectbox("🏦 बैंक / खाता",
                                          ["N/A","Cash","canara bank 311",
                                           "canara bank 41","bob","Canara 1747"])

        # कटौतियाँ
        st.markdown("<div class='grp'>📉 कटौतियाँ और एक्स्ट्रा</div>", unsafe_allow_html=True)
        g2c1, g2c2, g2c3 = st.columns(3)
        with g2c1: tds      = st.number_input("✂️ TDS (₹)",             min_value=0, step=10,  value=tds_exp)
        with g2c2: shortage = st.number_input("📉 शॉर्टेज / कटी (₹)", min_value=0, step=50)
        with g2c3: extra    = st.number_input("📈 Detention/Extra (₹)", min_value=0, step=100)

        remark = st.text_input("📝 विवरण / UTR No.")

        # Live preview कैलकुलेशन
        total_cut  = tds + shortage - extra
        net_after  = balance - pay_rec - total_cut
        
        if pay_rec > 0 or tds > 0 or shortage > 0 or extra > 0:
            st.markdown(f"""
                <div class='live-row'>
                    <div class='live-item'>
                        <span class='live-val'>₹{pay_rec:,}</span>
                        <span class='live-lbl'>💵 पेमेंट आया</span>
                    </div>
                    <div class='live-item'>
                        <span class='live-val'>₹{tds:,}</span>
                        <span class='live-lbl'>✂️ TDS</span>
                    </div>
                    <div class='live-item'>
                        <span class='live-val'>₹{shortage:,}</span>
                        <span class='live-lbl'>📉 शॉर्टेज</span>
                    </div>
                    <div class='live-item'>
                        <span class='live-val'>₹{extra:,}</span>
                        <span class='live-lbl'>📈 Extra</span>
                    </div>
                    <div class='live-item' style='border-left:2px solid #c7d4f5; padding-left:16px'>
                        <span class='live-val' style='color:{"#198754" if net_after<=0 else "#dc3545"}'>
                            ₹{max(0,int(net_after)):,}
                        </span>
                        <span class='live-lbl'>📊 सेव के बाद बकाया</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        submitted = st.form_submit_button(
            "✅ हिसाब अपडेट करें",
            use_container_width=True, type="primary")

        if submitted:
            if pay_rec > 0 and bank == "N/A":
                st.error("⚠️ कृपया बैंक खाता चुनें!")
            elif pay_rec == 0 and shortage == 0 and extra == 0 and tds == 0:
                st.error("⚠️ कोई अमाउंट भरें!")
            else:
                with st.spinner("अपडेट हो रहा है..."):
                    if save_company_payment(
                        str(datetime.date.today()), trip_id,
                        gr_no, truck_no, pay_rec, bank,
                        shortage, tds, extra, remark):
                        invalidate_sheet_cache()
                        st.success("✅ कंपनी खाता अपडेट हो गया!")
                        time.sleep(1.5); st.rerun()
                    else:
                        st.error("❌ एरर! गूगल शीट चेक करें।")
