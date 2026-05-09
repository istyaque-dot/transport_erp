import json
import time
from typing import Any, Iterable

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from oauth2client.service_account import ServiceAccountCredentials

WORKBOOK_NAME = "Khan_Transport_ERP"
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Keep read cache longer to avoid Google Sheets per-minute read quota errors.
# Manual Refresh / successful write will invalidate this cache.
SHEET_READ_TTL_SECONDS = 600

REQUIRED_SHEETS = {
    "Bookings": [
        "Date", "From", "Company", "Owner Rate", "Company Rate", "Weight", "Truck No", "Destination",
        "GR Number", "Universal Amount", "Comments", "Company Freight", "Owner Freight", "Universal Payment",
        "Trip ID", "Ishtyaque", "GR Link"
    ],
    "Advances": ["Date", "Trip ID", "Truck No", "Cash Amt", "Bank Amt", "Bank Name", "Diesel Amt", "Pump Name", "Total Amt"],
    "Receivables": ["Date", "Trip ID", "Truck No", "Company", "Received Amt", "Bank Name", "Shortage", "Remarks"],
    "Company_PODs": ["Date", "Trip ID", "GR No", "Truck No", "Status", "Shortage"],
    "Owner_Ledger": ["Date", "Trip ID", "GR No", "Truck No", "Description", "Amount"],
    "Company_Ledger": ["Date", "Trip ID", "GR No", "Truck No", "Description", "Amount"],
    "Universal_Ledger": ["Date", "Trip ID", "GR No", "Comment", "Description", "Amount"],
    "Ishtyaque_Ledger": ["Date", "Trip ID", "GR No", "Comment", "Description", "Amount"],
    "Cash_Ledger": ["Date", "Trip ID", "Type", "Description", "Amount"],
    "Canara_311_Ledger": ["Date", "Trip ID", "Type", "Description", "Amount"],
    "Canara_41_Ledger": ["Date", "Trip ID", "Type", "Description", "Amount"],
    "BOB_Ledger": ["Date", "Trip ID", "Type", "Description", "Amount"],
    "Shekh_Filling_Ledger": ["Date", "Trip ID", "Type", "Description", "Amount"],
    "canara_1747": ["Date", "Comment", "To/From", "Amount"],
    "Day_Book": ["Date", "Account", "Entry Type", "Category", "Amount", "Remarks"],
}


def _secrets_get(key: str) -> Any:
    try:
        return st.secrets[key]
    except Exception:
        return None


def _credentials_dict() -> dict:
    raw = _secrets_get("gcp_service_account")
    if raw is None:
        raise RuntimeError("Streamlit secrets में gcp_service_account missing है।")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


@st.cache_resource(ttl=3600, show_spinner=False)
def _raw_spreadsheet():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(_credentials_dict(), SCOPE)
    client = gspread.authorize(creds)
    return client.open(WORKBOOK_NAME)


@st.cache_resource(ttl=3600, show_spinner=False)
def _raw_worksheet(sheet_name: str):
    return _raw_spreadsheet().worksheet(sheet_name)


def _cache_version() -> int:
    return int(st.session_state.get("_sheet_cache_version", 0))


def _remember_last_good(sheet_name: str, values: list[list[Any]]) -> None:
    try:
        st.session_state.setdefault("_last_good_sheet_values", {})[sheet_name] = values
    except Exception:
        pass


def _last_good(sheet_name: str) -> list[list[Any]]:
    try:
        return st.session_state.get("_last_good_sheet_values", {}).get(sheet_name, [])
    except Exception:
        return []


@st.cache_data(ttl=SHEET_READ_TTL_SECONDS, show_spinner=False)
def _cached_values_from_api(sheet_name: str, version: int) -> list[list[Any]]:
    # One real Google Sheets read per sheet per TTL/version.
    return _raw_worksheet(sheet_name).get_all_values()


def _quota_message(exc: Exception) -> str:
    text = str(exc)
    if "Quota exceeded" in text or "Read requests" in text or "429" in text:
        return (
            "Google Sheets read quota limit hit हो गई है. 60-90 seconds wait करके reload करें. "
            "App अब cached reads use करेगा, इसलिए बार-बार tab switch करने पर read requests कम होंगी."
        )
    return text


def invalidate_sheet_cache() -> None:
    """Call after writes or manual refresh. Avoid direct st.cache_data.clear() in pages."""
    st.session_state["_sheet_cache_version"] = _cache_version() + 1
    try:
        # Clear cached data functions in app-level pages and central sheet cache.
        # This is intentionally triggered only on write/manual refresh, not on normal navigation.
        st.cache_data.clear()
    except Exception:
        pass


class CachedWorksheet:
    """Small wrapper over gspread.Worksheet with cached read methods."""

    def __init__(self, sheet_name: str):
        self.sheet_name = sheet_name
        self.title = sheet_name

    @property
    def _ws(self):
        return _raw_worksheet(self.sheet_name)

    def get_all_values(self, *args, **kwargs):
        if args or kwargs:
            # Rare non-default calls should go to gspread directly.
            try:
                return self._ws.get_all_values(*args, **kwargs)
            except Exception as exc:
                st.warning(_quota_message(exc))
                return _last_good(self.sheet_name)
        try:
            values = _cached_values_from_api(self.sheet_name, _cache_version())
            _remember_last_good(self.sheet_name, values)
            return values
        except Exception as exc:
            st.warning(_quota_message(exc))
            return _last_good(self.sheet_name)

    def get_all_records(self, *args, **kwargs):
        if args or kwargs:
            return self._ws.get_all_records(*args, **kwargs)
        values = self.get_all_values()
        if not values or len(values) <= 1:
            return []
        header = [str(h).strip() for h in values[0]]
        records = []
        for row in values[1:]:
            norm = list(row) + [""] * max(0, len(header) - len(row))
            records.append({header[i]: norm[i] for i in range(len(header)) if header[i]})
        return records

    def row_values(self, row: int, *args, **kwargs):
        if args or kwargs:
            return self._ws.row_values(row, *args, **kwargs)
        values = self.get_all_values()
        idx = row - 1
        return values[idx] if 0 <= idx < len(values) else []

    def col_values(self, col: int, *args, **kwargs):
        if args or kwargs:
            return self._ws.col_values(col, *args, **kwargs)
        values = self.get_all_values()
        idx = col - 1
        return [(r[idx] if idx < len(r) else "") for r in values]

    def append_row(self, *args, **kwargs):
        result = self._ws.append_row(*args, **kwargs)
        invalidate_sheet_cache()
        return result

    def append_rows(self, *args, **kwargs):
        result = self._ws.append_rows(*args, **kwargs)
        invalidate_sheet_cache()
        return result

    def update(self, *args, **kwargs):
        result = self._ws.update(*args, **kwargs)
        invalidate_sheet_cache()
        return result

    def update_cell(self, *args, **kwargs):
        result = self._ws.update_cell(*args, **kwargs)
        invalidate_sheet_cache()
        return result

    def batch_update(self, *args, **kwargs):
        result = self._ws.batch_update(*args, **kwargs)
        invalidate_sheet_cache()
        return result

    def clear(self, *args, **kwargs):
        result = self._ws.clear(*args, **kwargs)
        invalidate_sheet_cache()
        return result

    def __getattr__(self, item):
        return getattr(self._ws, item)


class CachedSpreadsheet:
    """Spreadsheet wrapper: existing code can keep using db.worksheet(name)."""

    def worksheet(self, sheet_name: str):
        # Validate existence once and cache the raw worksheet handle.
        _raw_worksheet(sheet_name)
        return CachedWorksheet(sheet_name)

    def add_worksheet(self, title: str, rows: int = 1000, cols: int = 26, **kwargs):
        ws = _raw_spreadsheet().add_worksheet(title=title, rows=rows, cols=cols, **kwargs)
        try:
            _raw_worksheet.clear(title)
        except Exception:
            try:
                _raw_worksheet.clear()
            except Exception:
                pass
        invalidate_sheet_cache()
        return ws

    def __getattr__(self, item):
        return getattr(_raw_spreadsheet(), item)


@st.cache_resource(ttl=3600, show_spinner=False)
def connect_to_sheet():
    # Return wrapper, not raw gspread object. It prevents repeated get_all_values reads on reruns.
    return CachedSpreadsheet()


def get_or_create_worksheet(sheet_name, rows=1000, cols=26):
    try:
        _raw_worksheet(sheet_name)
        return CachedWorksheet(sheet_name)
    except WorksheetNotFound:
        _raw_spreadsheet().add_worksheet(title=sheet_name, rows=rows, cols=cols)
        try:
            _raw_worksheet.clear(sheet_name)
        except Exception:
            try:
                _raw_worksheet.clear()
            except Exception:
                pass
        invalidate_sheet_cache()
        return CachedWorksheet(sheet_name)


def ensure_headers(sheet_name, headers):
    ws = get_or_create_worksheet(sheet_name, rows=1000, cols=max(26, len(headers) + 3))
    first_row = ws.row_values(1)
    if not first_row:
        ws.update("A1", [headers])
        return "created_headers"
    return "kept_existing_headers"


def ensure_required_sheets():
    result = {}
    for sheet_name, headers in REQUIRED_SHEETS.items():
        try:
            result[sheet_name] = ensure_headers(sheet_name, headers)
            time.sleep(0.15)  # small throttle for setup page only
        except Exception as exc:
            result[sheet_name] = f"error: {_quota_message(exc)}"
    return result


def worksheet_values(sheet_name):
    try:
        return get_or_create_worksheet(sheet_name).get_all_values()
    except Exception as exc:
        st.warning(_quota_message(exc))
        return _last_good(sheet_name)


def values_to_dataframe(values):
    if not values or len(values) <= 1:
        return pd.DataFrame()
    max_cols = max(len(row) for row in values)
    rows = [row + [""] * (max_cols - len(row)) for row in values]
    header = rows[0]
    return pd.DataFrame(rows[1:], columns=header)


def sheet_to_dataframe(sheet_name):
    return values_to_dataframe(worksheet_values(sheet_name))


def append_row(sheet_name, row):
    ws = get_or_create_worksheet(sheet_name)
    ws.append_row(row, table_range="A1")
    return True


def append_rows(sheet_name, rows):
    if not rows:
        return True
    ws = get_or_create_worksheet(sheet_name)
    ws.append_rows(rows, table_range="A1")
    return True


def clean_amount(value, default=0):
    try:
        text = str(value).replace(",", "").replace("₹", "").strip()
        return float(text) if text else default
    except Exception:
        return default


def clean_int(value, default=0):
    return int(clean_amount(value, default))
