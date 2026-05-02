import streamlit as st
import datetime
import time
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🗄️ DATABASE — Unchanged
# ==========================================

@st.cache_resource(ttl=3000)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Khan_Transport_ERP")

def get_all_trips():
    try:
        db   = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_values()
        return pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_company_balance_details(trip_id):
    try:
        db    = connect_to_sheet()
        data  = db.worksheet("Company_Ledger").get_all_values()
        total = 0
        for row in data[1:]:
            if len(row) > 5 and str(row[1]).strip() == str(trip_id).strip():
                try: total += int(float(str(row[5]).replace(',', '')))
                except: pass
        return total
    except:
        return 0

def get_pod_link(trip_id):
    try:
        db   = connect_to_sheet()
        data = db.worksheet("Owner_Ledger").get_all_values()
        for row in data[1:]:
            if len(row) > 4 and str(row[1]).strip() == str(trip_id).strip():
                if "POD Link:" in str(row[4]):
                    return str(row[4]).replace("POD Link:", "").strip()
        return None
    except:
        return None

def save_company_payment(date_val, trip_id, gr_no, truck_no,
                          pay_received, bank_name, shortage, tds, extra_km, remarks):
    try:
        db = connect_to_sheet()
        if extra_km > 0:
            db.worksheet("Company_Ledger").append_row(
                [str(date_val), trip_id, gr_no, truck_no,
                 f"Detention/Extra: {remarks}", int(extra_km)])
        if shortage > 0:
            db.worksheet("Company_Ledger").append_row(
                [str(date_val), trip_id, gr_no, truck_no,
                 f"Shortage: {remarks}", -int(shortage)])
        if tds > 0:
            db.worksheet("Company_Ledger").append_row(
                [str(date_val), trip_id, gr_no, truck_no,
                 f"TDS Deduction: {remarks}", -int(tds)])
        if pay_received > 0:
            db.worksheet("Company_Ledger").append_row(
                [str(date_val), trip_id, gr_no, truck_no,
                 f"Payment Recvd: {remarks}", -int(pay_received)])
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
                        [str(date_val),
                         f"Company Pay ({gr_no}) - {truck_no}",
                         "From: Company", int(pay_received)],
                        table_range="A1")
                else:
                    db.worksheet(s_name).append_row(
                        [str(date_val), trip_id, gr_no,
                         f"Comp Pay: {truck_no} | {remarks}",
                         int(pay_received)],
                        table_range="A1")
        return True
    except:
        return False

# ==========================================
# 🎨 CSS
# ==========================================

COMPANY_CSS = """
<style>
.block-container {
    padding-top: 0.7rem !important;
    padding-bottom: 0.3rem !important;
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
    max-width: 98% !important;
}
h2 { font-size: 1.15rem !important; margin: 0 0 3px 0 !important; }
.element-container { margin-bottom: 0.1rem !important; margin-top: 0 !important; }
[data-testid="stVerticalBlock"]   { gap: 0.12rem !important; }
[data-testid="stHorizontalBlock"] { gap: 0.45rem !important; }
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 0.18rem !important; }

[data-testid="stForm"] {
    background: #fff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 10px !important;
    padding: 10px 14px 8px 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}

[data-baseweb="input"] { border-radius: 6px !important; min-height: 1.7rem !important; }
[data-baseweb="input"] input {
    font-size: 0.81rem !important; padding: 2px 8px !important;
    min-height: 1.7rem !important; background: #fafafa !important;
}
[data-baseweb="input"]:focus-within {
    border-color: #003399 !important;
    box-shadow: 0 0 0 2px rgba(0,51,153,0.08) !important;
}
[data-baseweb="select"] > div:first-child {
    border-radius: 6px !important; min-height: 1.7rem !important;
    font-size: 0.81rem !important; background: #fafafa !important;
}
[data-testid="stDateInput"] input {
    font-size: 0.81rem !important; min-height: 1.7rem !important;
    padding: 2px 8px !important; border-radius: 6px !important;
}
[data-testid="stNumberInput"] [data-baseweb="input"] input {
    font-size: 0.81rem !important; min-height: 1.7rem !important;
}
label, [data-testid="stWidgetLabel"] p {
    font-size: 0.73rem !important; font-weight: 700 !important;
    color: #374151 !important; margin-bottom: 0 !important; line-height: 1.1 !important;
}
[data-testid="stButton"] button {
    border-radius: 6px !important; min-height: 1.7rem !important;
    font-size: 0.81rem !important; font-weight: 600 !important;
    padding: 0 12px !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #003399, #0055cc) !important;
    color: #fff !important; border: none !important;
}
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #003399, #0055cc) !important;
    color: #fff !important; border-radius: 6px !important;
    font-size: 0.81rem !important; font-weight: 700 !important;
    min-height: 1.7rem !important; width: 100% !important;
}
[data-testid="stAlert"] {
    border-radius: 6px !important; padding: 4px 10px !important; margin: 2px 0 !important;
}
[data-testid="stAlert"] p { font-size: 0.8rem !important; margin: 0 !important; }

[data-testid="metric-container"] {
    background: #f8faff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 7px !important; padding: 5px 10px !important;
}
[data-testid="stMetricValue"] { font-size: 0.9rem !important; font-weight: 700 !important; color: #003399 !important; line-height: 1.2 !important; }
[data-testid="stMetricLabel"] { font-size: 0.64rem !important; font-weight: 600 !important; color: #666 !important; }
[data-testid="stMetricDelta"] { display: none !important; }
hr { margin: 0.25em 0 !important; border-color: #e8edf5 !important; }

/* Trip info bar */
.trip-bar {
    display: flex; align-items: center; flex-wrap: wrap; gap: 5px;
    background: #f0f4ff; border-left: 4px solid #003399;
    border-radius: 0 8px 8px 0; padding: 7px 14px;
    margin: 3px 0 5px 0; font-size: 0.8rem;
}
.trip-chip {
    background: #fff; border: 1px solid #c7d4f5;
    border-radius: 20px; padding: 1px 10px;
    font-size: 0.75rem; font-weight: 700; color: #003399;
}

/* Pill header */
.pill-header {
    display: inline-block; background: #003399; color: white;
    border-radius: 20px; padding: 2px 14px;
    font-size: 0.74rem; font-weight: 700; margin: 5px 0 3px 0;
}

/* Document cards */
.doc-card-ok {
    background: #d1e7dd; border: 1px solid #0f5132;
    border-radius: 7px; padding: 6px 12px;
    font-size: 0.78rem; font-weight: 700; color: #0f5132;
    text-align: center; margin-bottom: 4px;
}
.doc-card-miss {
    background: #fff3cd; border: 1px solid #ffc107;
    border-radius: 7px; padding: 6px 12px;
    font-size: 0.78rem; font-weight: 700; color: #856404;
    text-align: center; margin-bottom: 4px;
}

/* Balance cards */
.bal-clear {
    background: #d1e7dd; border: 1px solid #0f5132;
    border-left: 4px solid #0f5132; border-radius: 8px;
    padding: 8px 16px; color: #0f5132; font-weight: 700;
    font-size: 0.85rem; margin: 5px 0;
}
.bal-due {
    background: #fff3cd; border: 1px solid #ffc107;
    border-left: 4px solid #f59e0b; border-radius: 8px;
    padding: 8px 16px; color: #856404; font-weight: 700;
    font-size: 0.88rem; margin: 5px 0;
}

/* Input group divider */
.grp-label {
    font-size: 0.73rem; font-weight: 700; color: #003399;
    background: #f0f4ff; border-radius: 5px;
    padding: 2px 8px; margin: 3px 0 2px 0;
    display: inline-block;
}
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_company_page():
    st.markdown(COMPANY_CSS, unsafe_allow_html=True)
    st.header("🏢 कंपनी खाता और सेटलमेंट")

    df_trips = get_all_trips()
    if df_trips.empty:
        st.info("कोई डेटा नहीं मिला।")
        return

    # ── Trip Selector ──
    df_last = df_trips.tail(150).iloc[::-1]
    labels, trip_ids = [], []
    for _, row in df_last.iterrows():
        try:
            gr = str(row.iloc[8]) if str(row.iloc[8]).lower() not in ("nan","") else "No GR"
            labels.append(
                f"🚛 {row.iloc[6]}  |  📅 {str(row.iloc[0])[:10]}  |  "
                f"📍 {row.iloc[7]}  |  GR: {gr}")
            trip_ids.append(str(row.iloc[14]))
        except:
            pass

    selected_label = st.selectbox(
        "गाड़ी या GR सर्च करें:", ["चुनें..."] + labels,
        label_visibility="collapsed"
    )

    if selected_label == "चुनें...":
        st.caption("👆 GR नंबर, गाड़ी नंबर या कंपनी टाइप करके खोजें।")
        return

    idx              = labels.index(selected_label)
    selected_trip_id = trip_ids[idx]
    row_data         = df_last[df_last.iloc[:, 14].astype(str) == selected_trip_id].iloc[0]

    gr_no        = str(row_data.iloc[8])
    truck_no     = str(row_data.iloc[6])
    company_name = str(row_data.iloc[2])
    dest         = str(row_data.iloc[7])
    trip_date    = str(row_data.iloc[0])[:10]
    try:    comp_freight = int(float(str(row_data.iloc[11]).replace(',', '')))
    except: comp_freight = 0

    # ── Trip Info Bar ──
    st.markdown(f"""
        <div class='trip-bar'>
            <span class='trip-chip'>🚛 {truck_no}</span>
            <span class='trip-chip'>🏢 {company_name}</span>
            <span class='trip-chip'>📄 GR: {gr_no}</span>
            <span class='trip-chip'>📍 {dest}</span>
            <span class='trip-chip'>📅 {trip_date}</span>
            <span class='trip-chip'>💰 भाड़ा: ₹{comp_freight:,}</span>
        </div>
    """, unsafe_allow_html=True)

    # ── Documents ──
    gr_link = None
    if len(row_data) > 16 and pd.notna(row_data.iloc[16]) and "http" in str(row_data.iloc[16]):
        gr_link = str(row_data.iloc[16]).strip()
    pod_link = get_pod_link(selected_trip_id)

    st.markdown("<div class='pill-header'>📄 डॉक्यूमेंट्स</div>", unsafe_allow_html=True)
    doc1, doc2 = st.columns(2)

    with doc1:
        if gr_link:
            st.markdown("<div class='doc-card-ok'>✅ GR (बिल्टी) अपलोड है</div>",
                        unsafe_allow_html=True)
            st.link_button("📄 GR देखें", gr_link, use_container_width=True)
        else:
            st.markdown("<div class='doc-card-miss'>⚠️ GR अभी अपलोड नहीं</div>",
                        unsafe_allow_html=True)

    with doc2:
        if pod_link:
            st.markdown("<div class='doc-card-ok'>✅ POD (रिसीविंग) अपलोड है</div>",
                        unsafe_allow_html=True)
            st.link_button("🏁 POD देखें", pod_link, use_container_width=True)
        else:
            st.markdown("<div class='doc-card-miss'>⚠️ POD अभी अपलोड नहीं</div>",
                        unsafe_allow_html=True)

    # ── Balance ──
    st.markdown("<hr>", unsafe_allow_html=True)
    comp_balance = get_company_balance_details(selected_trip_id)

    if comp_balance <= 0:
        st.markdown(
            f"<div class='bal-clear'>✅ हिसाब क्लियर — कोई बकाया नहीं (बैलेंस: ₹{comp_balance:,})</div>",
            unsafe_allow_html=True)
        return

    st.markdown(
        f"<div class='bal-due'>💰 बकाया (Balance Due): ₹{comp_balance:,}</div>",
        unsafe_allow_html=True)

    # ── Balance Metrics ──
    tds_exp    = int(comp_freight * 0.01)
    hold_exp   = int(comp_freight * 0.10)
    net_exp    = comp_freight - tds_exp - hold_exp

    bm1, bm2, bm3 = st.columns(3)
    bm1.metric("💰 कुल भाड़ा",    f"₹{comp_freight:,}")
    bm2.metric("📉 TDS (अनुमान)", f"₹{tds_exp:,}")
    bm3.metric("🔒 10% रोक",      f"₹{hold_exp:,}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Payment Form ──
    with st.form("payment_form"):
        st.markdown("<div class='pill-header'>💳 पेमेंट / कटौती एंट्री</div>",
                    unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Row 1 — Payment in
        st.markdown("<div class='grp-label'>📥 आया हुआ पेमेंट</div>", unsafe_allow_html=True)
        r1c1, r1c2 = st.columns(2)
        with r1c1: pay_rec = st.number_input("💵 बैंक में आया (₹)", min_value=0, step=100)
        with r1c2: bank    = st.selectbox("🏦 बैंक / खाता",
                                          ["N/A", "Cash", "canara bank 311",
                                           "canara bank 41", "bob", "Canara 1747"])

        # Row 2 — Deductions
        st.markdown("<div class='grp-label'>📉 कटौतियाँ</div>", unsafe_allow_html=True)
        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1: tds      = st.number_input("✂️ TDS कटा (₹)",        min_value=0, step=10,  value=tds_exp)
        with r2c2: shortage = st.number_input("📉 शॉर्टेज / कटी (₹)", min_value=0, step=50)
        with r2c3: extra    = st.number_input("📈 Detention/Extra (₹)", min_value=0, step=100)

        # Remarks
        remark = st.text_input("📝 विवरण / UTR No.")

        # Live summary inside form
        if pay_rec > 0 or tds > 0 or shortage > 0 or extra > 0:
            st.markdown("<hr>", unsafe_allow_html=True)
            net_after = comp_balance + extra - shortage - tds - pay_rec
            fm1, fm2, fm3, fm4 = st.columns(4)
            fm1.metric("💵 पेमेंट आया",   f"₹{pay_rec:,}")
            fm2.metric("✂️ TDS",           f"₹{tds:,}")
            fm3.metric("📉 शॉर्टेज",      f"₹{shortage:,}")
            fm4.metric("📊 बाद में बकाया", f"₹{max(0,int(net_after)):,}")

        submitted = st.form_submit_button(
            "✅ हिसाब अपडेट करें",
            use_container_width=True, type="primary"
        )

        if submitted:
            if pay_rec > 0 and bank == "N/A":
                st.error("⚠️ कृपया बैंक खाता चुनें!")
            elif pay_rec == 0 and shortage == 0 and extra == 0 and tds == 0:
                st.error("⚠️ कोई अमाउंट भरें!")
            else:
                with st.spinner("अपडेट हो रहा है..."):
                    if save_company_payment(
                        str(datetime.date.today()), selected_trip_id,
                        gr_no, truck_no, pay_rec, bank,
                        shortage, tds, extra, remark
                    ):
                        st.cache_data.clear()
                        st.success("✅ कंपनी खाता अपडेट हो गया!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ एरर! गूगल शीट चेक करें।")
