import streamlit as st
import pandas as pd

from sheet_utils import (
    invalidate_sheet_cache,
    worksheet_values,
    clean_amount,
    format_trip_label,
    filter_trip_dataframe,
    safe_cell,
)


@st.cache_data(ttl=600)
def get_dashboard_data():
    """Google Sheets से dashboard numbers index-safe तरीके से निकालना."""
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

    booking_rows = worksheet_values("Bookings")
    total_owner_freight = 0
    for row in booking_rows[1:]:
        if len(row) > 12:
            total_owner_freight += clean_amount(row[12])

    adv_rows = worksheet_values("Advances")
    total_adv = 0
    for row in adv_rows[1:]:
        total_adv += clean_amount(row[8] if len(row) > 8 else (row[5] if len(row) > 5 else 0))

    owner_rows = worksheet_values("Owner_Ledger")
    owner_adjustments = 0
    for row in owner_rows[1:]:
        if len(row) > 5 and any(k in str(row[4]) for k in ["Final Balance", "Shortage", "Extra", "Detention"]):
            owner_adjustments += clean_amount(row[5])

    payable = total_owner_freight - total_adv + owner_adjustments
    return results, ish_bal, uni_bal, int(payable)


@st.cache_data(ttl=600)
def get_dashboard_trips_df():
    """Bookings को cached dataframe में load करें. Dashboard direct links इसी से चलेंगे."""
    rows = worksheet_values("Bookings")
    if len(rows) <= 1:
        return pd.DataFrame()
    max_cols = max(len(r) for r in rows)
    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]
    return pd.DataFrame(norm_rows[1:], columns=norm_rows[0])


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
.quick-card { background:#ffffff; border:1px solid #d8e2f3; border-radius:14px; padding:12px; box-shadow:0 3px 12px rgba(0,0,0,0.04); }
.route-note { background:#eff6ff; border:1px solid #bfdbfe; border-left:4px solid #2563eb; border-radius:10px; padding:8px 12px; color:#1e3a8a; font-size:0.82rem; margin:6px 0 10px 0; }
.small-muted { color:#64748b; font-size:0.78rem; }
</style>
"""


def _go_to(page_name: str, **state):
    """Dashboard से सही page पर route करें. Sidebar radio को direct mutate नहीं करते."""
    for key, value in state.items():
        st.session_state[key] = value
    st.session_state["pending_page_choice"] = page_name
    st.rerun()


def _render_direct_work_links():
    st.divider()
    st.markdown("<div class='pill'>⚡ Direct Work Links</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='route-note'>Dashboard से खुलने वाले buttons fixed route use करते हैं: Expense → Day Book, POD Upload → Docs Upload, Advance → Advance page.</div>",
        unsafe_allow_html=True,
    )

    expense_col, trip_col = st.columns([1, 2.2], gap="large")

    with expense_col:
        st.markdown("<div class='quick-card'>", unsafe_allow_html=True)
        st.subheader("💳 Expense")
        st.caption("खर्चा entry सीधे Day Book में खुलेगी.")
        if st.button("➕ खर्चा Direct डालें", use_container_width=True, type="primary"):
            _go_to(
                "📓 Day Book",
                daybook_quick_expense=True,
                daybook_quick_note="Dashboard से Expense entry mode खोला गया.",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with trip_col:
        st.markdown("<div class='quick-card'>", unsafe_allow_html=True)
        st.subheader("🚛 GR / गाड़ी wise काम")
        df = get_dashboard_trips_df()
        if df.empty:
            st.info("Bookings sheet में trip data नहीं मिला.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # Latest trips ऊपर रखें. Search खाली होने पर भी latest list दिखाई देगी.
        df_all = df.copy().iloc[::-1].reset_index(drop=True)
        search = st.text_input(
            "🔎 GR / गाड़ी search",
            placeholder="GR number या गाड़ी number लिखें",
            key="dash_trip_action_search",
        )
        df_show = filter_trip_dataframe(df_all, search)
        df_show = df_show.head(120)

        labels, trip_ids, gr_nos, truck_nos = [], [], [], []
        for _, row in df_show.iterrows():
            try:
                labels.append(format_trip_label(row))
                trip_ids.append(safe_cell(row, 14, ""))
                gr_nos.append(safe_cell(row, 8, ""))
                truck_nos.append(safe_cell(row, 6, ""))
            except Exception:
                continue

        st.caption(f"Dropdown में {len(labels)} trip(s) loaded")
        if not labels:
            st.warning("इस GR/गाड़ी से कोई trip नहीं मिला.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        default_index = 1 if search and len(labels) == 1 else 0
        selected = st.selectbox(
            "Trip चुनें",
            ["चुनें..."] + labels,
            index=default_index,
            key="dash_trip_action_select",
        )

        if selected == "चुनें...":
            st.caption("पहले trip चुनें, फिर नीचे button दबाएँ.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        selected_i = labels.index(selected)
        trip_id = trip_ids[selected_i]
        gr_no = gr_nos[selected_i]
        truck_no = truck_nos[selected_i]
        route_query = str(gr_no or truck_no or "").strip()

        st.write(f"Selected: **GR {gr_no or 'N/A'}** | 🚛 **{truck_no or 'N/A'}** | ID: `{trip_id}`")

        a1, a2 = st.columns(2)
        with a1:
            if st.button("💸 Advance Submit खोलें", use_container_width=True, type="primary"):
                _go_to(
                    "💸 Advance",
                    advance_prefill_search=route_query,
                    advance_prefill_trip_id=trip_id,
                    advance_prefill_notice=f"Dashboard से Advance खोला गया: GR {gr_no} / {truck_no}",
                )
        with a2:
            if st.button("📤 POD Upload खोलें", use_container_width=True, type="primary"):
                _go_to(
                    "📤 Docs Upload",
                    docs_upload_prefill_search=route_query,
                    docs_upload_prefill_doc_type="POD",
                    docs_upload_prefill_notice=f"Dashboard से POD Upload खोला गया: GR {gr_no} / {truck_no}",
                )

        st.markdown("</div>", unsafe_allow_html=True)


def show_dashboard_page():
    st.markdown(DASH_CSS, unsafe_allow_html=True)

    h1, h2 = st.columns([5, 1])
    with h1:
        st.header("📊 डैशबोर्ड")
    with h2:
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            invalidate_sheet_cache()
            st.rerun()

    bank_bals, ish_bal, uni_bal, payable = get_dashboard_data()

    cash = bank_bals.get("Cash", 0)
    c311 = bank_bals.get("Canara 311", 0)
    c41 = bank_bals.get("Canara 41", 0)
    bob = bank_bals.get("BOB", 0)
    c1747 = bank_bals.get("Canara 1747", 0)
    pump = bank_bals.get("Pump", 0)

    total_liquidity = cash + c311 + c41 + bob + c1747
    net_pos = total_liquidity - int(payable)
    net_color = "sum-green" if net_pos >= 0 else "sum-red"

    sb1, sb2, sb3 = st.columns(3)
    sb1.markdown(f"<div class='sum-card sum-blue'>💰 कुल बैंक + नकद<br><span style='font-size:1.1rem'>₹{total_liquidity:,}</span></div>", unsafe_allow_html=True)
    sb2.markdown(f"<div class='sum-card sum-red'>🚛 गाड़ी वालों को देना<br><span style='font-size:1.1rem'>₹{int(payable):,}</span></div>", unsafe_allow_html=True)
    sb3.markdown(f"<div class='sum-card {net_color}'>📊 नेट पोज़िशन<br><span style='font-size:1.1rem'>₹{net_pos:,}</span></div>", unsafe_allow_html=True)

    _render_direct_work_links()

    st.divider()
    st.markdown("<div class='pill'>🏦 बैंक और नकद</div>", unsafe_allow_html=True)
    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
    bc1.metric("💵 Cash", f"₹{cash:,}")
    bc2.metric("🏦 Canara 311", f"₹{c311:,}")
    bc3.metric("🏦 Canara 41", f"₹{c41:,}")
    bc4.metric("🏦 BOB", f"₹{bob:,}")
    bc5.metric("🏦 Canara 1747", f"₹{c1747:,}")

    st.divider()
    st.markdown("<div class='pill'>👤 खास खाते</div>", unsafe_allow_html=True)
    sp1, sp2, sp3 = st.columns(3)
    sp1.metric("👤 इश्तियाक भाई", f"₹{ish_bal:,}")
    sp2.metric("🏢 यूनिवर्सल", f"₹{uni_bal:,}")
    p_status = "देना बाकी ⏳" if pump < 0 else "एडवांस जमा ✅"
    sp3.metric("⛽ शेख फिलिंग", f"₹{abs(pump):,}", p_status, delta_color="inverse" if pump < 0 else "normal")
