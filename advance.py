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

from sheet_utils import connect_to_sheet, invalidate_sheet_cache, format_trip_label, filter_trip_dataframe, safe_cell

@st.cache_data(ttl=600)
def get_all_trips():
    try:
        db   = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_values()
        return pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame()
    except:
        return pd.DataFrame()

def save_advance_to_db(date_val, trip_id, truck_no, mode, remarks, amount):
    """Save advance in the 9-column schema used by POD/Reports.
    Columns: Date, Trip ID, Truck, Cash Amt, Bank Amt, Bank Name, Diesel Amt, Pump Name, Total Amt
    """
    try:
        db = connect_to_sheet()
        amt = int(amount)
        cash_amt = amt if mode == "Cash" else 0
        bank_amt = amt if mode in ["Canara 311", "Canara 41", "BOB", "Canara 1747"] else 0
        diesel_amt = amt if mode == "Pump (Shekh Filling)" else 0
        bank_name = mode if bank_amt else "N/A"
        pump_name = "Shekh Filling" if diesel_amt else "N/A"
        row_data = [str(date_val), str(trip_id), str(truck_no), cash_amt, bank_amt, bank_name, diesel_amt, pump_name, amt]
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
                    [str(date_val), "Advance", f"Truck: {truck_no}", -amt],
                    table_range="A1")
            else:
                db.worksheet(ledger_name).append_row(
                    [str(date_val), str(trip_id), "Debit", f"Advance: {truck_no} | {remarks}", -amt],
                    table_range="A1")
        invalidate_sheet_cache()
        return True
    except Exception as e:
        st.error(f"Advance save error: {e}")
        return False


# ==========================================
# 📥 BULK ADVANCE UPLOAD HELPERS
# ==========================================
import io


def _clean_str(v, default=""):
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return str(v).strip()


def _norm_key(v):
    s = _clean_str(v, "")
    # GR 176, 176.0, gr-176 -> 176
    s = s.replace("GR", "").replace("Gr", "").replace("gr", "")
    s = s.replace("G.R.", "").replace("G.R", "")
    s = s.replace("-", "").replace("/", "").replace(" ", "")
    try:
        if s.endswith(".0"):
            s = s[:-2]
        # numeric strings like 176.00
        f = float(s)
        if f.is_integer():
            s = str(int(f))
    except Exception:
        pass
    return s.upper().strip()


def _clean_amount(v):
    s = _clean_str(v, "0").replace(",", "").replace("₹", "").strip()
    try:
        return int(round(float(s)))
    except Exception:
        return 0


def _parse_date(v):
    if v is None or _clean_str(v, "") == "":
        return str(datetime.date.today())
    try:
        dt = pd.to_datetime(v, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return str(datetime.date.today())
        return str(dt.date())
    except Exception:
        return str(datetime.date.today())


def _build_bulk_advance_template():
    cols = ["GR No", "Payment Date", "Amount", "Mode", "Bank/UTR", "Remark"]
    sample = pd.DataFrame([
        {"GR No": "176", "Payment Date": str(datetime.date.today()), "Amount": 49500, "Mode": "Cash", "Bank/UTR": "", "Remark": "Advance paid"},
        {"GR No": "177", "Payment Date": str(datetime.date.today()), "Amount": 22390, "Mode": "Canara 311", "Bank/UTR": "UTR123", "Remark": "Advance paid"},
    ], columns=cols)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        sample.to_excel(writer, index=False, sheet_name="BulkAdvance")
    return out.getvalue()


@st.cache_data(ttl=300)
def get_all_advances():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Advances").get_all_values()
        if len(data) <= 1:
            return pd.DataFrame()
        return pd.DataFrame(data[1:], columns=data[0])
    except Exception:
        return pd.DataFrame()


def _is_duplicate_advance(df_adv, trip_id, date_str, amount):
    if df_adv is None or df_adv.empty:
        return False
    try:
        # Expected schema: Date, Trip ID, Truck, Cash Amt, Bank Amt, Bank Name, Diesel Amt, Pump Name, Total Amt
        c_date = df_adv.iloc[:, 0].astype(str).str.strip()
        c_trip = df_adv.iloc[:, 1].astype(str).str.strip()
        c_total = pd.to_numeric(df_adv.iloc[:, 8].astype(str).str.replace(',', '').str.replace('₹',''), errors='coerce').fillna(0).astype(int)
        return bool(((c_date == str(date_str)) & (c_trip == str(trip_id)) & (c_total == int(amount))).any())
    except Exception:
        return False


def _mode_to_advance_row(date_val, trip_id, truck_no, mode, amount):
    amt = int(amount)
    cash_amt = amt if mode == "Cash" else 0
    bank_amt = amt if mode in ["Canara 311", "Canara 41", "BOB", "Canara 1747"] else 0
    diesel_amt = amt if mode == "Pump (Shekh Filling)" else 0
    bank_name = mode if bank_amt else "N/A"
    pump_name = "Shekh Filling" if diesel_amt else "N/A"
    return [str(date_val), str(trip_id), str(truck_no), cash_amt, bank_amt, bank_name, diesel_amt, pump_name, amt]


def save_bulk_advances_to_db(advance_rows):
    try:
        db = connect_to_sheet()
        ws_adv = db.worksheet("Advances")
        adv_values = []
        ledger_map = {}
        for r in advance_rows:
            date_val = r["date"]
            trip_id = r["trip_id"]
            truck_no = r["truck_no"]
            mode = r["mode"]
            amount = int(r["amount"])
            remarks = r.get("remarks", "")
            adv_values.append(_mode_to_advance_row(date_val, trip_id, truck_no, mode, amount))

            s_map = {
                "Cash": "Cash_Ledger",
                "Canara 311": "Canara_311_Ledger",
                "Canara 41": "Canara_41_Ledger",
                "BOB": "BOB_Ledger",
                "Canara 1747": "canara_1747",
                "Pump (Shekh Filling)": "Shekh_Filling_Ledger",
            }
            ledger_name = s_map.get(mode)
            if ledger_name:
                if mode == "Canara 1747":
                    ledger_row = [str(date_val), "Advance", f"Truck: {truck_no}", -amount]
                else:
                    ledger_row = [str(date_val), str(trip_id), "Debit", f"Advance: {truck_no} | {remarks}", -amount]
                ledger_map.setdefault(ledger_name, []).append(ledger_row)

        if adv_values:
            ws_adv.append_rows(adv_values, value_input_option="USER_ENTERED")
        for ledger_name, rows in ledger_map.items():
            try:
                db.worksheet(ledger_name).append_rows(rows, value_input_option="USER_ENTERED")
            except Exception:
                # Ledger sheet missing हो तो Advance save को fail न करें
                pass
        invalidate_sheet_cache()
        try:
            get_all_advances.clear()
            get_all_trips.clear()
        except Exception:
            pass
        return True, f"{len(adv_values)} advance rows saved"
    except Exception as e:
        return False, str(e)



# ==========================================
# 📥 BULK ADVANCE FROM GOOGLE SHEET
# ==========================================
BULK_ADVANCE_SHEET_NAME = "Bulk_Advance"
BULK_ADVANCE_HEADERS = [
    "Status", "GR No", "Payment Date", "Amount", "Mode", "Bank/UTR", "Remark", "Error", "Processed At"
]


def _ensure_bulk_advance_sheet():
    """Create Bulk_Advance sheet and headers if missing. Existing data is not overwritten."""
    db = connect_to_sheet()
    try:
        ws = db.worksheet(BULK_ADVANCE_SHEET_NAME)
    except Exception:
        ws = db.add_worksheet(title=BULK_ADVANCE_SHEET_NAME, rows=1000, cols=len(BULK_ADVANCE_HEADERS) + 2)
        ws.update(f"A1:I1", [BULK_ADVANCE_HEADERS])
        invalidate_sheet_cache()
        return ws

    try:
        first_row = ws.row_values(1)
        if not first_row:
            ws.update(f"A1:I1", [BULK_ADVANCE_HEADERS])
        else:
            existing = [str(x).strip() for x in first_row]
            # Fill missing headers to the right without touching existing rows.
            if existing[:len(BULK_ADVANCE_HEADERS)] != BULK_ADVANCE_HEADERS:
                # If the row is blank/old, set a standard header row. Data rows remain unchanged.
                ws.update(f"A1:I1", [BULK_ADVANCE_HEADERS])
        invalidate_sheet_cache()
    except Exception:
        pass
    return ws


def _get_header_index(headers, name):
    wanted = str(name).strip().lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == wanted:
            return i
    return None


def _cell_from_row(row, headers, *names, default=""):
    for name in names:
        idx = _get_header_index(headers, name)
        if idx is not None and idx < len(row):
            return row[idx]
    return default


@st.cache_data(ttl=120)
def _load_bulk_advance_sheet_values():
    try:
        db = connect_to_sheet()
        values = db.worksheet(BULK_ADVANCE_SHEET_NAME).get_all_values()
        return values
    except Exception:
        return []


def _build_bulk_advance_gsheet_template_df():
    return pd.DataFrame([
        {"Status": "PENDING", "GR No": "176", "Payment Date": str(datetime.date.today()), "Amount": 49500, "Mode": "Cash", "Bank/UTR": "", "Remark": "Advance paid", "Error": "", "Processed At": ""},
        {"Status": "PENDING", "GR No": "177", "Payment Date": str(datetime.date.today()), "Amount": 22390, "Mode": "Canara 311", "Bank/UTR": "UTR123", "Remark": "Advance paid", "Error": "", "Processed At": ""},
    ], columns=BULK_ADVANCE_HEADERS)


def _prepare_bulk_advance_preview_from_rows(raw_values, df_trips):
    if not raw_values or len(raw_values) <= 1:
        return [], [], []

    headers = [str(x).strip() for x in raw_values[0]]
    data_rows = raw_values[1:]

    # Build GR map from Bookings
    gr_map = {}
    duplicates = set()
    for _, tr in df_trips.iterrows():
        gr = _norm_key(safe_cell(tr, 8, ""))
        if not gr or gr in ["NA", "N/A"]:
            continue
        if gr in gr_map:
            duplicates.add(gr)
        gr_map.setdefault(gr, []).append(tr)

    df_adv = get_all_advances()
    allowed_modes = ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747", "Pump (Shekh Filling)", "Other"]
    preview_rows = []
    ready_rows = []
    status_updates = []

    pending_count = 0
    for row_num, row in enumerate(data_rows, start=2):
        current_status = _clean_str(_cell_from_row(row, headers, "Status", default=""), "").upper()
        if current_status not in ["", "PENDING"]:
            continue
        pending_count += 1
        if pending_count > 100:
            break

        gr_raw = _cell_from_row(row, headers, "GR No", "GR", "Gr No", default="")
        gr_key = _norm_key(gr_raw)
        amount = _clean_amount(_cell_from_row(row, headers, "Amount", "Amt", "Advance", default="0"))
        date_str = _parse_date(_cell_from_row(row, headers, "Payment Date", "Date", default=""))
        mode = _clean_str(_cell_from_row(row, headers, "Mode", "Payment Mode", default="Cash"), "Cash")
        if mode not in allowed_modes:
            mode = "Other"
        bank_utr = _clean_str(_cell_from_row(row, headers, "Bank/UTR", "UTR", "Bank", default=""), "")
        remark = _clean_str(_cell_from_row(row, headers, "Remark", "Remarks", default=""), "")
        remarks = " | ".join([x for x in [bank_utr, remark] if x])

        status = "✅ Ready"
        reason = ""
        tr = None
        if not gr_key:
            status, reason = "❌ Error", "GR No blank"
        elif gr_key not in gr_map:
            status, reason = "❌ Error", "GR booking में नहीं मिला"
        elif gr_key in duplicates or len(gr_map.get(gr_key, [])) > 1:
            status, reason = "⚠️ Error", "Same GR की multiple bookings मिलीं"
        elif amount <= 0:
            status, reason = "❌ Error", "Amount invalid"
        else:
            tr = gr_map[gr_key][0]
            trip_id = safe_cell(tr, 14, "")
            if _is_duplicate_advance(df_adv, trip_id, date_str, amount):
                status, reason = "⚠️ Duplicate", "Same GR + Date + Amount already saved"

        if tr is not None:
            trip_id = safe_cell(tr, 14, "")
            truck_no = safe_cell(tr, 6, "")
            dest = safe_cell(tr, 7, "")
            book_date = safe_cell(tr, 0, "")
        else:
            trip_id = truck_no = dest = book_date = ""

        out = {
            "Sheet Row": row_num,
            "GR No": _clean_str(gr_raw),
            "Payment Date": date_str,
            "Amount": amount,
            "Mode": mode,
            "Truck No": truck_no,
            "Destination": dest,
            "Trip ID": trip_id,
            "Booking Date": book_date,
            "Status": status,
            "Reason": reason,
        }
        preview_rows.append(out)
        if status == "✅ Ready":
            ready_rows.append({
                "source_row": row_num,
                "date": date_str,
                "trip_id": trip_id,
                "truck_no": truck_no,
                "mode": mode,
                "amount": amount,
                "remarks": remarks,
            })
        else:
            status_updates.append({"source_row": row_num, "status": "ERROR" if "Error" in status else "DUPLICATE", "error": reason})

    return preview_rows, ready_rows, status_updates


def _update_bulk_advance_statuses(row_statuses):
    """Batch update Status/Error/Processed At columns for Bulk_Advance rows."""
    if not row_statuses:
        return
    db = connect_to_sheet()
    ws = db.worksheet(BULK_ADVANCE_SHEET_NAME)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = []
    # Columns: A Status, H Error, I Processed At
    for item in row_statuses:
        r = int(item["source_row"])
        updates.append({"range": f"A{r}", "values": [[item.get("status", "")]]})
        updates.append({"range": f"H{r}", "values": [[item.get("error", "")]]})
        updates.append({"range": f"I{r}", "values": [[ts]]})
    ws.batch_update(updates)
    invalidate_sheet_cache()
    try:
        _load_bulk_advance_sheet_values.clear()
    except Exception:
        pass


def _show_bulk_advance_from_google_sheet(df_trips):
    with st.expander("📥 Bulk Advance from Google Sheet", expanded=False):
        st.caption("Google Sheet में `Bulk_Advance` tab में rows डालें. Status खाली/PENDING rows ही process होंगी. DONE rows दोबारा process नहीं होंगी.")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("🧩 Bulk_Advance tab बनाएं/check", key="bulk_adv_sheet_setup", use_container_width=True):
                try:
                    _ensure_bulk_advance_sheet()
                    st.success("Bulk_Advance tab/header ready है।")
                except Exception as e:
                    st.error(f"Sheet setup error: {e}")
        with c2:
            if st.button("🔄 Bulk data refresh", key="bulk_adv_sheet_refresh", use_container_width=True):
                try:
                    _load_bulk_advance_sheet_values.clear()
                except Exception:
                    pass
                invalidate_sheet_cache()
                st.rerun()
        with c3:
            st.download_button(
                "⬇️ Template Excel download",
                data=_build_bulk_advance_template(),
                file_name="bulk_advance_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.markdown("""
**Bulk_Advance columns:** `Status | GR No | Payment Date | Amount | Mode | Bank/UTR | Remark | Error | Processed At`  
`Status` खाली या `PENDING` रखें. Process के बाद app `DONE / ERROR / DUPLICATE` mark करेगा.
""")

        try:
            _ensure_bulk_advance_sheet()
            raw_values = _load_bulk_advance_sheet_values()
        except Exception as e:
            st.error(f"Bulk_Advance read error: {e}")
            return

        if not raw_values or len(raw_values) <= 1:
            st.info("Bulk_Advance tab में अभी pending rows नहीं हैं।")
            return

        preview_rows, ready_rows, problem_statuses = _prepare_bulk_advance_preview_from_rows(raw_values, df_trips)
        if not preview_rows:
            st.info("कोई PENDING/blank status row नहीं मिली।")
            return

        st.markdown("#### Preview — Google Sheet Bulk Advance")
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
        total_amt = sum(int(r["amount"]) for r in ready_rows)
        st.info(f"Ready: {len(ready_rows)} | Problems: {len(problem_statuses)} | Total ready amount: ₹{total_amt:,}")

        confirm = st.checkbox("Preview check हो गया — Google Sheet की ✅ Ready rows save करें", key="bulk_adv_gsheet_confirm")
        if st.button("🚀 Confirm & Process Bulk_Advance Sheet", type="primary", use_container_width=True, disabled=(not confirm or not ready_rows)):
            progress = st.progress(0, text="Bulk_Advance process हो रहा है...")
            saved_total = 0
            errors = []
            done_statuses = []
            for start in range(0, len(ready_rows), 50):
                batch = ready_rows[start:start+50]
                ok, msg = save_bulk_advances_to_db(batch)
                if ok:
                    saved_total += len(batch)
                    for r in batch:
                        done_statuses.append({"source_row": r["source_row"], "status": "DONE", "error": ""})
                    progress.progress(min(saved_total / max(len(ready_rows), 1), 1.0), text=f"Saved {saved_total}/{len(ready_rows)}")
                else:
                    errors.append(msg)
                    break

            try:
                _update_bulk_advance_statuses(done_statuses + problem_statuses)
            except Exception as e:
                st.warning(f"Advance saved, लेकिन Bulk_Advance status update में issue आया: {e}")

            if errors:
                st.error(f"Bulk save error after {saved_total} rows: {errors[0]}")
            else:
                st.success(f"✅ Bulk_Advance Complete: {saved_total} rows saved. Total ₹{total_amt:,}")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()


def _show_bulk_advance_upload(df_trips):
    with st.expander("📥 Bulk Advance Upload — Excel से GR based advance entry", expanded=False):
        c1, c2 = st.columns([1, 2])
        with c1:
            st.download_button(
                "⬇️ Template डाउनलोड करें",
                data=_build_bulk_advance_template(),
                file_name="bulk_advance_upload_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            st.caption("Minimum columns: GR No, Amount. Blank/invalid rows skip होंगी. पहले preview आएगा, फिर save होगा.")

        bulk_file = st.file_uploader("Bulk Advance Excel/CSV upload करें", type=["xlsx", "xls", "csv"], key="bulk_advance_upload_file_v2")
        if bulk_file is None:
            return
        try:
            df_bulk = pd.read_csv(bulk_file) if bulk_file.name.lower().endswith(".csv") else pd.read_excel(bulk_file)
        except Exception as e:
            st.error(f"Excel read error: {e}")
            return
        if df_bulk.empty:
            st.warning("Excel खाली है।")
            return
        if len(df_bulk) > 100:
            st.warning("एक बार में max 100 rows process होंगी। Extra rows ignore कर दी गई हैं।")
            df_bulk = df_bulk.head(100)

        # Build GR map from Bookings
        gr_map = {}
        duplicates = set()
        for _, tr in df_trips.iterrows():
            gr = _norm_key(safe_cell(tr, 8, ""))
            if not gr or gr in ["NA", "N/A"]:
                continue
            if gr in gr_map:
                duplicates.add(gr)
            gr_map.setdefault(gr, []).append(tr)

        df_adv = get_all_advances()
        preview_rows = []
        ready_rows = []
        allowed_modes = ["Cash", "Canara 311", "Canara 41", "BOB", "Canara 1747", "Pump (Shekh Filling)", "Other"]

        for i, row in df_bulk.iterrows():
            gr_raw = row.get("GR No", row.get("GR", row.get("Gr No", "")))
            gr_key = _norm_key(gr_raw)
            amount = _clean_amount(row.get("Amount", row.get("Amt", row.get("Advance", 0))))
            date_str = _parse_date(row.get("Payment Date", row.get("Date", "")))
            mode = _clean_str(row.get("Mode", row.get("Payment Mode", "Cash")), "Cash")
            if mode not in allowed_modes:
                mode = "Other"
            bank_utr = _clean_str(row.get("Bank/UTR", row.get("UTR", row.get("Bank", ""))), "")
            remark = _clean_str(row.get("Remark", row.get("Remarks", "")), "")
            remarks = " | ".join([x for x in [bank_utr, remark] if x])

            status = "✅ Ready"
            reason = ""
            tr = None
            if not gr_key:
                status, reason = "❌ Skip", "GR No blank"
            elif gr_key not in gr_map:
                status, reason = "❌ Skip", "GR booking में नहीं मिला"
            elif gr_key in duplicates or len(gr_map.get(gr_key, [])) > 1:
                status, reason = "⚠️ Skip", "Same GR की multiple bookings मिलीं"
            elif amount <= 0:
                status, reason = "❌ Skip", "Amount invalid"
            else:
                tr = gr_map[gr_key][0]
                trip_id = safe_cell(tr, 14, "")
                if _is_duplicate_advance(df_adv, trip_id, date_str, amount):
                    status, reason = "⚠️ Duplicate", "Same GR + Date + Amount already saved"

            if tr is not None:
                trip_id = safe_cell(tr, 14, "")
                truck_no = safe_cell(tr, 6, "")
                dest = safe_cell(tr, 7, "")
                book_date = safe_cell(tr, 0, "")
            else:
                trip_id = truck_no = dest = book_date = ""

            out = {
                "Row": i + 2,
                "GR No": _clean_str(gr_raw),
                "Payment Date": date_str,
                "Amount": amount,
                "Mode": mode,
                "Truck No": truck_no,
                "Destination": dest,
                "Trip ID": trip_id,
                "Booking Date": book_date,
                "Status": status,
                "Reason": reason,
            }
            preview_rows.append(out)
            if status == "✅ Ready":
                ready_rows.append({
                    "date": date_str,
                    "trip_id": trip_id,
                    "truck_no": truck_no,
                    "mode": mode,
                    "amount": amount,
                    "remarks": remarks,
                })

        st.markdown("#### Preview")
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
        st.info(f"Ready: {len(ready_rows)} | Total rows: {len(preview_rows)}")
        confirm = st.checkbox("Preview check हो गया — सिर्फ ✅ Ready rows save करें", key="bulk_adv_confirm_v2")
        if st.button("🚀 Confirm & Save Bulk Advance", type="primary", use_container_width=True, disabled=(not confirm or not ready_rows)):
            progress = st.progress(0, text="Bulk advance save हो रहा है...")
            saved_total = 0
            errors = []
            for start in range(0, len(ready_rows), 50):
                batch = ready_rows[start:start+50]
                ok, msg = save_bulk_advances_to_db(batch)
                if ok:
                    saved_total += len(batch)
                    progress.progress(min(saved_total / max(len(ready_rows), 1), 1.0), text=f"Saved {saved_total}/{len(ready_rows)}")
                else:
                    errors.append(msg)
                    break
            if errors:
                st.error(f"Bulk save error after {saved_total} rows: {errors[0]}")
            else:
                st.success(f"✅ Bulk Advance Complete: {saved_total} rows saved. Total ₹{sum(r['amount'] for r in ready_rows):,}")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()


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
            invalidate_sheet_cache()
            st.rerun()

    df_trips = get_all_trips()

    if df_trips.empty:
        st.info("⚠️ कोई बुकिंग नहीं मिली। पहले 'बुकिंग' पेज से गाड़ी लगाएँ।")
        return

    # ── Bulk Advance Upload ──
    _show_bulk_advance_upload(df_trips)

    # ── Trip selector: full list + global search sequence ──
    df_all = df_trips.copy()
    if df_all.shape[1] > 14:
        df_all = df_all[df_all.iloc[:, 14].astype(str).str.strip() != ""]
    df_all = df_all.iloc[::-1].reset_index(drop=True)

    prefill_search = st.session_state.pop("advance_prefill_search", "")
    prefill_trip_id = st.session_state.pop("advance_prefill_trip_id", "")
    prefill_notice = st.session_state.pop("advance_prefill_notice", "")
    if prefill_search:
        st.session_state["adv_trip_search"] = str(prefill_search).strip()
    if prefill_notice:
        st.info(prefill_notice)

    search_text = st.text_input(
        "🔎 Trip search",
        placeholder="GR / गाड़ी नंबर / Destination / Date / Trip ID लिखें — खाली छोड़ें तो पूरी list",
        key="adv_trip_search"
    )
    df_show = filter_trip_dataframe(df_all, search_text)
    st.caption(f"Dropdown में {len(df_show)} trip(s) loaded | Total bookings: {len(df_all)}")

    labels, trip_ids, truck_nos = [], [], []
    for _, row in df_show.iterrows():
        try:
            labels.append(format_trip_label(row))
            trip_ids.append(safe_cell(row, 14, ""))
            truck_nos.append(safe_cell(row, 6, ""))
        except Exception:
            pass

    default_select_index = 0
    if prefill_trip_id and prefill_trip_id in trip_ids:
        default_select_index = trip_ids.index(prefill_trip_id) + 1
    elif str(search_text or "").strip() and len(labels) == 1:
        default_select_index = 1

    selected_label = st.selectbox(
        "गाड़ी चुनें:", ["चुनें..."] + labels,
        index=default_select_index,
        label_visibility="collapsed"
    )

    if selected_label == "चुनें...":
        st.info("👆 ऊपर से गाड़ी चुनें।")
        return

    idx          = labels.index(selected_label)
    sel_trip_id  = trip_ids[idx]
    sel_truck_no = truck_nos[idx]

    # ── Trip Info Card ──
    sel_row = df_show[df_show.iloc[:, 14].astype(str) == sel_trip_id].iloc[0]
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
