import json
import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import WorksheetNotFound
from oauth2client.service_account import ServiceAccountCredentials

WORKBOOK_NAME = "Khan_Transport_ERP"
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

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


def _secrets_get(key):
    try:
        return st.secrets[key]
    except Exception:
        return None


def _credentials_dict():
    raw = _secrets_get("gcp_service_account")
    if raw is None:
        raise RuntimeError("Streamlit secrets में gcp_service_account missing है।")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


@st.cache_resource(ttl=3600)
def connect_to_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(_credentials_dict(), SCOPE)
    client = gspread.authorize(creds)
    return client.open(WORKBOOK_NAME)


def get_or_create_worksheet(sheet_name, rows=1000, cols=26):
    db = connect_to_sheet()
    try:
        return db.worksheet(sheet_name)
    except WorksheetNotFound:
        return db.add_worksheet(title=sheet_name, rows=rows, cols=cols)


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
        except Exception as exc:
            result[sheet_name] = f"error: {exc}"
    try:
        st.cache_data.clear()
    except Exception:
        pass
    return result


def worksheet_values(sheet_name):
    try:
        return get_or_create_worksheet(sheet_name).get_all_values()
    except Exception:
        return []


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
    try:
        st.cache_data.clear()
    except Exception:
        pass
    return True


def append_rows(sheet_name, rows):
    if not rows:
        return True
    ws = get_or_create_worksheet(sheet_name)
    ws.append_rows(rows, table_range="A1")
    try:
        st.cache_data.clear()
    except Exception:
        pass
    return True


def clean_amount(value, default=0):
    try:
        text = str(value).replace(",", "").replace("₹", "").strip()
        return float(text) if text else default
    except Exception:
        return default


def clean_int(value, default=0):
    return int(clean_amount(value, default))
