import streamlit as st
import datetime
import time
import io
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🗄️ DATABASE 
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

@st.cache_data(ttl=120)
def get_all_trips():
    try:
        db   = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_values()
        return pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame()
    except:
        return pd.DataFrame()

def save_advance_to_db(date_val, trip_id, truck_no, mode, remarks, amount):
    try:
        db = connect_to_sheet()
        # 6 कॉलम के हिसाब से सेट किया गया है: Date, Trip ID, Truck, Mode, Remarks, Amount
        row_data = [str(date_val), str(trip_id), str(truck_no), str(mode), str(remarks), int(amount)]
        db.worksheet("Advances").append_row(row_data, table_range="A1")

        s_map = {
            "Cash":                 "Cash_Ledger",
            "Canara 311":           "Canara_311_Ledger",
            "Canara 41":            "Canara_41_Ledger",
            "BOB":                  "BOB_Ledger",
            "Canara 1747":          "canara_1747",
            "Pump (Shekh Filling)": "Shekh_Filling_Ledger"
        }
        ledger_name = s_map.get(mode)
        if ledger_name:
            if mode == "Canara 1747":
                db.worksheet(ledger_name).append_row(
                    [str(date_val), "Advance", f"Truck: {truck_no}", -int(amount)],
                    table_range="A1")
            else:
                db.worksheet(ledger_name).append_row(
                    [str(date_val), "Advance", "Debit",
                     f"Truck: {truck_no} | {remarks}", -int(amount)],
                    table_range="A1")
        st.cache_data.clear()
        return True
    except:
        return False



# ==========================================
# 📥 BULK ADVANCE UPLOAD HELPERS
# ==========================================

def _clean_str(v, default=""):
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    s = str(v).strip()
    if s.lower() in ("nan", "none", "nat"):
        return default
    return s

def _norm_key(v):
    s = _clean_str(v, "").upper()
    # 45.0 -> 45
    try:
        if s.endswith('.0') and float(s).is_integer():
            s = str(int(float(s)))
    except Exception:
        pass
    return ''.join(ch for ch in s if ch.isalnum())

def _clean_amount(v):
    s = _clean_str(v, "0").replace(',', '').replace('₹', '').strip()
    try:
        return int(round(float(s)))
    except Exception:
        return 0

def _parse_date(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.strftime('%Y-%m-%d')
    s = _clean_str(v, "")
    if not s:
        return datetime.date.today().strftime('%Y-%m-%d')
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%Y-%m-%d')
    except Exception:
        pass
    return s

def _build_bulk_advance_template():
    cols = ["GR No", "Payment Date", "Amount", "Mode", "Bank/UTR", "Remark"]
    sample = pd.DataFrame([
        {"GR No": "176", "Payment Date": datetime.date.today().strftime('%Y-%m-%d'), "Amount": 49500, "Mode": "Cash", "Bank/UTR": "", "Remark": "Advance paid"},
        {"GR No": "177", "Payment Date": datetime.date.today().strftime('%Y-%m-%d'), "Amount": 22390, "Mode": "Canara 311", "Bank/UTR": "UTR123", "Remark": "Bank advance"},
    ], columns=cols)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        pd.DataFrame(columns=cols).to_excel(writer, index=False, sheet_name='BulkAdvance')
        sample.to_excel(writer, index=False, sheet_name='Sample')
    return buf.getvalue()

@st.cache_data(ttl=60)
def get_all_advances():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Advances").get_all_values()
        if not data:
            return pd.DataFrame()
        # Advances sheet often has no header. Keep positional columns.
        return pd.DataFrame(data[1:] if len(data) > 1 and str(data[0][0]).lower() in ('date','payment date') else data)
    except Exception:
        return pd.DataFrame()

def _is_duplicate_advance(df_adv, trip_id, date_str, amount, mode):
    if df_adv is None or df_adv.empty:
        return False
    try:
        for _, r in df_adv.iterrows():
            vals = [str(x).strip() for x in list(r.values)]
            if len(vals) < 6:
                continue
            same_trip = _norm_key(vals[1]) == _norm_key(trip_id)
            same_date = _parse_date(vals[0]) == _parse_date(date_str)
            same_amt = _clean_amount(vals[5]) == int(amount)
            same_mode = _norm_key(vals[3]) == _norm_key(mode)
            if same_trip and same_date and same_amt and same_mode:
                return True
    except Exception:
        return False
    return False

def save_bulk_advances_to_db(advance_rows):
    """advance_rows: list of dict(date, trip_id, truck_no, mode, remarks, amount)"""
    if not advance_rows:
        return False, "No rows to save"
    try:
        db = connect_to_sheet()
        rows = [[
            str(r["date"]), str(r["trip_id"]), str(r["truck_no"]),
            str(r["mode"]), str(r["remarks"]), int(r["amount"])
        ] for r in advance_rows]
        db.worksheet("Advances").append_rows(rows, value_input_option="USER_ENTERED", table_range="A1")

        s_map = {
            "Cash":                 "Cash_Ledger",
            "Canara 311":           "Canara_311_Ledger",
            "Canara 41":            "Canara_41_Ledger",
            "BOB":                  "BOB_Ledger",
            "Canara 1747":          "canara_1747",
            "Pump (Shekh Filling)": "Shekh_Filling_Ledger"
        }
        ledger_batches = {}
        for r in advance_rows:
            mode = str(r["mode"])
            ledger_name = s_map.get(mode)
            if not ledger_name:
                continue
            if mode == "Canara 1747":
                ledger_row = [str(r["date"]), "Advance", f"Truck: {r['truck_no']} | GR: {r.get('gr_no','')}", -int(r["amount"])]
            else:
                ledger_row = [str(r["date"]), "Advance", "Debit", f"Truck: {r['truck_no']} | GR: {r.get('gr_no','')} | {r['remarks']}", -int(r["amount"])]
            ledger_batches.setdefault(ledger_name, []).append(ledger_row)

        for ledger_name, batch in ledger_batches.items():
            try:
                db.worksheet(ledger_name).append_rows(batch, value_input_option="USER_ENTERED", table_range="A1")
            except Exception:
                # Ledger failure should not block main Advance sheet save.
                pass
        st.cache_data.clear()
        return True, f"Saved {len(rows)} advance rows"
    except Exception as e:
        return False, str(e)

def _show_bulk_advance_upload(df_trips):
    st.markdown("### 📥 Bulk Advance Upload")
    with st.expander("📥 Excel से GR-wise advance payment load करें", expanded=False):
        cdl, cinf = st.columns([1, 2])
        with cdl:
            st.download_button(
                "⬇️ Bulk Advance Template",
                data=_build_bulk_advance_template(),
                file_name="bulk_advance_upload_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with cinf:
            st.info("Excel में minimum columns: GR No, Amount. Blank Mode = Cash, Blank Date = आज की date. Save से पहले preview आएगा।")

        bulk_file = st.file_uploader("Bulk Advance Excel/CSV upload करें", type=["xlsx", "xls", "csv"], key="bulk_advance_upload_file")
        if bulk_file is None:
            return
        try:
            df_bulk = pd.read_csv(bulk_file) if bulk_file.name.lower().endswith('.csv') else pd.read_excel(bulk_file)
        except Exception as e:
            st.error(f"File read error: {e}")
            return

        if df_bulk.empty:
            st.warning("Excel खाली है।")
            return
        if len(df_bulk) > 150:
            st.warning("एक बार में 100 rows तक recommended है। अभी पहले 100 rows process करें।")
            df_bulk = df_bulk.head(100)

        df_adv = get_all_advances()
        preview = []
        ready_rows = []
        for i, row in df_bulk.iterrows():
            gr = _clean_str(row.get("GR No", row.get("GR", "")))
            amount = _clean_amount(row.get("Amount", row.get("Advance Amount", 0)))
            pay_date = _parse_date(row.get("Payment Date", row.get("Date", "")))
            mode = _clean_str(row.get("Mode", row.get("Payment Mode", "Cash")), "Cash")
            bank = _clean_str(row.get("Bank/UTR", row.get("UTR", row.get("Bank", ""))))
            remark = _clean_str(row.get("Remark", row.get("Remarks", "")))

            matches = df_trips[df_trips.iloc[:, 8].apply(_norm_key) == _norm_key(gr)] if gr else pd.DataFrame()
            status = ""
            trip_id = truck = dest = ""
            duplicate = False
            if not gr:
                status = "❌ GR Missing"
            elif amount <= 0:
                status = "❌ Amount Missing/Invalid"
            elif len(matches) == 0:
                status = "❌ GR Not Found"
            elif len(matches) > 1:
                status = "⚠️ Duplicate GR in Booking"
            else:
                m = matches.iloc[0]
                trip_id = _clean_str(m.iloc[14])
                truck = _clean_str(m.iloc[6])
                dest = _clean_str(m.iloc[7])
                duplicate = _is_duplicate_advance(df_adv, trip_id, pay_date, amount, mode)
                status = "⚠️ Duplicate Advance" if duplicate else "✅ Ready"

            full_remark = " | ".join([x for x in [f"GR: {gr}", f"Dest: {dest}" if dest else "", bank, remark] if x])
            preview.append({
                "Status": status, "GR No": gr, "Date": pay_date, "Amount": amount,
                "Mode": mode, "Truck": truck, "Destination": dest, "Remark": full_remark
            })
            if status == "✅ Ready":
                ready_rows.append({
                    "date": pay_date, "trip_id": trip_id, "truck_no": truck, "mode": mode,
                    "remarks": full_remark, "amount": amount, "gr_no": gr
                })

        prev_df = pd.DataFrame(preview)
        st.dataframe(prev_df, use_container_width=True, height=260)
        ready_count = len(ready_rows)
        issue_count = len(prev_df) - ready_count
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Ready", ready_count)
        c2.metric("⚠️ Skip/Issue", issue_count)
        c3.metric("Total Amount", f"₹{sum(r['amount'] for r in ready_rows):,}")

        if ready_count == 0:
            st.warning("Save के लिए कोई ready row नहीं है।")
            return
        confirm = st.checkbox("Preview check हो गया — सिर्फ ✅ Ready rows save करें", key="bulk_adv_confirm")
        if st.button("🚀 Confirm & Save Bulk Advance", type="primary", use_container_width=True, disabled=not confirm):
            progress = st.progress(0, text="Bulk advance save हो रहा है...")
            saved_total = 0
            ok_all = True
            err_msg = ""
            # 50-50 rows batch to reduce timeout risk.
            for start in range(0, len(ready_rows), 50):
                batch = ready_rows[start:start+50]
                ok, msg = save_bulk_advances_to_db(batch)
                if ok:
                    saved_total += len(batch)
                    progress.progress(min(saved_total / len(ready_rows), 1.0), text=f"Saved {saved_total}/{len(ready_rows)}")
                else:
                    ok_all = False
                    err_msg = msg
                    break
            if ok_all:
                st.success(f"✅ Bulk Advance Complete: {saved_total} rows saved. Total ₹{sum(r['amount'] for r in ready_rows):,}")
                st.info("Data तुरंत न दिखे तो app के अंदर Refresh Data दबाएँ, browser hard refresh न करें।")
            else:
                st.error(f"❌ Bulk save error after {saved_total} rows: {err_msg}")

# ==========================================
# 🎨 CSS
# ==========================================

ADVANCE_CSS = """
<style>
/* ── Page layout ── */
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 0.3rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 98% !important;
}

/* ── Headings ── */
h2 { font-size: 1.2rem !important; margin: 0 0 4px 0 !important; color: #111 !important; }
h4 { font-size: 0.88rem !important; margin: 4px 0 2px 0 !important; color: #003399 !important; }

/* ── Element spacing ── */
.element-container {
    margin-bottom: 0.15rem !important;
    margin-top: 0 !important;
}
[data-testid="stVerticalBlock"] {
    gap: 0.15rem !important;
}
[data-testid="stHorizontalBlock"] {
    gap: 0.5rem !important;
}

/* ── Form card ── */
[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1px solid #dde3f0 !important;
    border-radius: 10px !important;
    padding: 12px 16px 10px 16px !important;
    box-shadow: 0 1px 5px rgba(0,0,0,0.06) !important;
}
[data-testid="stForm"] [data-testid="stVerticalBlock"] {
    gap: 0.2rem !important;
}

/* ── Inputs ── */
[data-baseweb="input"] {
    border-radius: 6px !important;
    min-height: 1.75rem !important;
}
[data-baseweb="input"] input {
    font-size: 0.82rem !important;
    padding: 2px 8px !important;
    min-height: 1.75rem !important;
    background: #fafafa !important;
}
[data-baseweb="input"]:focus-within {
    border-color: #003399 !important;
    box-shadow: 0 0 0 2px rgba(0,51,153,0.1) !important;
}

/* ── Number input ── */
[data-testid="stNumberInput"] [data-baseweb="input"] input {
    font-size: 0.82rem !important;
    min-height: 1.75rem !important;
}

/* ── Selectbox ── */
[data-baseweb="select"] > div:first-child {
    border-radius: 6px !important;
    min-height: 1.75rem !important;
    font-size: 0.82rem !important;
    background: #fafafa !important;
}
[data-baseweb="select"] > div:first-child:focus-within {
    border-color: #003399 !important;
}

/* ── Date input ── */
[data-testid="stDateInput"] input {
    font-size: 0.82rem !important;
    min-height: 1.75rem !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
}

/* ── Labels ── */
label, [data-testid="stWidgetLabel"] p {
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    color: #374151 !important;
    margin-bottom: 0 !important;
    line-height: 1.1 !important;
}

/* ── Buttons ── */
[data-testid="stButton"] button {
    border-radius: 6px !important;
    min-height: 1.75rem !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 0 12px !important;
    border: none !important;
    transition: all 0.15s ease !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #003399 0%, #0055cc 100%) !important;
    color: #fff !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    background: linear-gradient(135deg, #002277 0%, #0044aa 100%) !important;
    box-shadow: 0 2px 8px rgba(0,51,153,0.3) !important;
}
[data-testid="stButton"] button[kind="secondary"] {
    background: #f0f4ff !important;
    color: #003399 !important;
    border: 1px solid #c7d4f5 !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    padding: 5px 10px !important;
    margin: 2px 0 !important;
}
[data-testid="stAlert"] p { font-size: 0.82rem !important; margin: 0 !important; }

/* ── Metrics compact ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #f0f4ff, #e8eeff) !important;
    border: 1px solid #c7d4f5 !important;
    border-radius: 8px !important;
    padding: 5px 10px !important;
}
[data-testid="stMetricValue"]  { font-size: 0.95rem !important; font-weight: 700 !important; color: #003399 !important; }
[data-testid="stMetricLabel"]  { font-size: 0.68rem !important; font-weight: 600 !important; color: #555 !important; }
[data-testid="stMetricDelta"]  { font-size: 0.68rem !important; }

/* ── Selectbox dropdown text ── */
[data-testid="stSelectbox"] [data-baseweb="select"] span {
    font-size: 0.82rem !important;
}

/* ── HR ── */
hr { margin: 0.3em 0 !important; border-color: #e2e8f0 !important; }

/* ── Trip info card ── */
.trip-card {
    background: linear-gradient(135deg, #f0f4ff, #e8eeff);
    border: 1px solid #c7d4f5;
    border-left: 4px solid #003399;
    border-radius: 8px;
    padding: 8px 14px;
    margin: 4px 0;
    font-size: 0.82rem;
    line-height: 1.6;
}
.trip-card b { color: #003399; }

/* ── Selectbox main dropdown ── */
[data-testid="stSelectbox"] > div > div {
    min-height: 1.75rem !important;
    font-size: 0.82rem !important;
}
</style>
"""

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================

def show_advance_page():
    st.markdown(ADVANCE_CSS, unsafe_allow_html=True)
    st.header("💸 एडवांस पेमेंट")

    # Refresh
    col_r, _ = st.columns([1, 7])
    with col_r:
        if st.button("🔄 Refresh", key="adv_refresh"):
            st.cache_data.clear()
            st.rerun()

    df_trips = get_all_trips()

    if df_trips.empty:
        st.info("⚠️ कोई बुकिंग नहीं मिली। पहले 'बुकिंग' पेज से गाड़ी लगाएँ।")
        return

    # ── Bulk Advance Upload ──
    _show_bulk_advance_upload(df_trips)
    st.divider()

    # ── Trip selector ──
    df_last = df_trips.tail(50).iloc[::-1]
    labels, trip_ids, truck_nos = [], [], []

    for _, row in df_last.iterrows():
        try:
            labels.append(f"🚛 {row.iloc[6]}  |  📅 {row.iloc[0]}  |  📍 {row.iloc[7]}")
            trip_ids.append(str(row.iloc[14]))
            truck_nos.append(str(row.iloc[6]))
        except:
            pass

    selected_label = st.selectbox(
        "गाड़ी चुनें:", ["चुनें..."] + labels,
        label_visibility="collapsed"
    )

    if selected_label == "चुनें...":
        st.info("👆 ऊपर से गाड़ी चुनें।")
        return

    idx          = labels.index(selected_label)
    sel_trip_id  = trip_ids[idx]
    sel_truck_no = truck_nos[idx]

    # ── Trip Info Card ──
    sel_row = df_last[df_last.iloc[:, 14].astype(str) == sel_trip_id].iloc[0]
    try:
        dest      = str(sel_row.iloc[7])
        trip_date = str(sel_row.iloc[0])
        try:    owner_freight = int(float(str(sel_row.iloc[12]).replace(',', '')))
        except: owner_freight = 0
    except:
        dest, trip_date, owner_freight = "—", "—", 0

    st.markdown(f"""
        <div class='trip-card'>
            🚛 <b>{sel_truck_no}</b> &nbsp;&nbsp;
            📅 {trip_date} &nbsp;&nbsp;
            📍 {dest} &nbsp;&nbsp;
            💵 कुल गाड़ी भाड़ा: <b>₹{owner_freight:,}</b>
        </div>
    """, unsafe_allow_html=True)

    # ── Advance Form ──
    with st.form("advance_form"):
        st.markdown("#### 💳 एडवांस की जानकारी")

        c1, c2, c3 = st.columns(3)
        with c1: adv_date   = st.date_input("📅 तारीख", datetime.date.today())
        with c2: adv_amount = st.number_input("💵 अमाउंट (₹)", min_value=0, step=500)
        with c3: pay_mode   = st.selectbox("🏦 पेमेंट मोड",
                                            ["Cash", "Canara 311", "Canara 41",
                                             "BOB", "Canara 1747",
                                             "Pump (Shekh Filling)", "Other"])

        c4, c5 = st.columns([3, 1])
        with c4:
            remarks = st.text_input("📝 विवरण / UTR No.")
        with c5:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "💾 एडवांस सेव करें",
                use_container_width=True,
                type="primary"
            )

        # ── Live preview ──
        if adv_amount > 0:
            bal_after = owner_freight - adv_amount
            m1, m2, m3 = st.columns(3)
            m1.metric("💵 एडवांस",        f"₹{adv_amount:,}")
            m2.metric("🚛 कुल भाड़ा",     f"₹{owner_freight:,}")
            m3.metric("🔄 बचेगा बाद में", f"₹{max(bal_after,0):,}")

        if submitted:
            if adv_amount <= 0:
                st.error("⚠️ सही अमाउंट दर्ज करें!")
            else:
                with st.spinner("⏳ सेव हो रहा है..."):
                    if save_advance_to_db(adv_date, sel_trip_id, sel_truck_no,
                                          pay_mode, remarks, adv_amount):
                        st.success(
                            f"✅ गाड़ी {sel_truck_no} को "
                            f"₹{adv_amount:,} का एडवांस सेव हो गया! ({pay_mode})"
                        )
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ एडवांस सेव नहीं हो पाया।")
