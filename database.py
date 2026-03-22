import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# --- 0. CONNECTION ---
@st.cache_resource(ttl=86400)
def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("secret.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Khan_Transport_ERP")
    return sheet

# --- 1. GOOGLE DRIVE UPLOAD ---
def upload_to_drive(file_bytes, file_name, folder_id):
    try:
        scope = ["https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("secret.json", scope)
        service = build('drive', 'v3', credentials=creds)
        meta = {'name': file_name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='application/octet-stream', resumable=True)
        file = service.files().create(body=meta, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Cloud Upload Error: {e}")
        return None

# --- 2. BOOKING LOGIC ---
def save_booking_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Bookings").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

@st.cache_data(ttl=60)
def get_all_trips():
    try:
        db = connect_to_sheet()
        data = db.worksheet("Bookings").get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def update_booking_in_db(trip_id, updated_row):
    try:
        db = connect_to_sheet()
        sheet = db.worksheet("Bookings")
        ids = sheet.col_values(15) 
        if trip_id in ids:
            row_index = ids.index(trip_id) + 1
            sheet.update(f"A{row_index}:O{row_index}", [updated_row])
            st.cache_data.clear()
            return True
    except: return False

def save_to_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        db = connect_to_sheet()
        gr = str(gr_no) if gr_no else "N/A"
        base = [str(date_val), str(trip_id), gr, str(truck_no), str(dest)]
        db.worksheet("Company_Ledger").append_row(base + [int(comp_amt)], table_range="A1")
        db.worksheet("Owner_Ledger").append_row(base + [int(owner_amt)], table_range="A1")
        db.worksheet("Universal_Ledger").append_row([str(date_val), str(trip_id), "N/A", "N/A", f"Freight: {truck_no}", int(uni_amt)], table_range="A1")
        db.worksheet("Ishtyaque_Ledger").append_row([str(date_val), str(trip_id), "N/A", "N/A", f"Profit: {truck_no}", int(ish_amt)], table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

def update_ledgers(date_val, trip_id, gr_no, truck_no, dest, comp_amt, owner_amt, uni_amt, ish_amt):
    try:
        db = connect_to_sheet()
        gr = str(gr_no).strip() if str(gr_no).strip() != "" else "N/A"
        ledgers = {"Company_Ledger": int(comp_amt), "Owner_Ledger": int(owner_amt), "Universal_Ledger": int(uni_amt), "Ishtyaque_Ledger": int(ish_amt)}
        for sheet_name, amt in ledgers.items():
            ws = db.worksheet(sheet_name)
            records = ws.get_all_values()
            row_to_update = -1
            for i, row in enumerate(records):
                if len(row) > 1 and trip_id in row:
                    row_to_update = i + 1; break
            
            new_row_data = [str(date_val), str(trip_id), gr, str(truck_no), str(dest), amt]
            if sheet_name in ["Universal_Ledger", "Ishtyaque_Ledger"]:
                desc = f"Freight: {truck_no}" if sheet_name == "Universal_Ledger" else f"Profit: {truck_no}"
                new_row_data = [str(date_val), str(trip_id), "N/A", "N/A", desc, amt]
            
            if row_to_update != -1: ws.update(f"A{row_to_update}:F{row_to_update}", [new_row_data])
            else: ws.append_row(new_row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

# --- 3. ADVANCE LOGIC ---
def save_advance_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Advances").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

@st.cache_data(ttl=60)
def get_total_advance_for_trip(trip_id):
    try:
        db = connect_to_sheet()
        records = db.worksheet("Advances").get_all_values()
        return sum([int(float(row[8])) for row in records[1:] if len(row) > 8 and row[1] == trip_id])
    except: return 0

def save_advance_ledgers(date_val, trip_id, gr_no, dest, cash_amt, bank_amt, bank_name, diesel_amt, pump_name):
    try:
        db = connect_to_sheet()
        gr = str(gr_no) if gr_no else "N/A"
        base = [str(date_val), str(trip_id), gr, str(dest)]
        if int(cash_amt) > 0: db.worksheet("Cash_Ledger").append_row(base + [-int(cash_amt)], table_range="A1")
        if int(bank_amt) > 0:
            s_name = {"canara bank 311":"Canara_311_Ledger", "canara bank 41":"Canara_41_Ledger", "bob":"BOB_Ledger"}.get(bank_name)
            if s_name: db.worksheet(s_name).append_row(base + [-int(bank_amt)], table_range="A1")
        if int(diesel_amt) > 0: db.worksheet("Shekh_Filling_Ledger").append_row(base + [int(diesel_amt)], table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

# --- 4. RECEIVABLES & TRANSFERS ---
def save_receivable_to_db(row_data):
    try:
        db = connect_to_sheet(); db.worksheet("Receivables").append_row(row_data, table_range="A1")
        st.cache_data.clear(); return True
    except: return False

@st.cache_data(ttl=60)
def get_total_received_for_trip(trip_id):
    try:
        db = connect_to_sheet()
        records = db.worksheet("Receivables").get_all_values()
        return sum([int(float(row[4])) for row in records[1:] if len(row) > 4 and row[1] == trip_id])
    except: return 0

def save_receivable_ledgers(date_val, trip_id, gr_no, comp_name, truck_no, received_amt, bank_name):
    try:
        db = connect_to_sheet()
        desc = f"{comp_name} | {truck_no}"
        base = [str(date_val), str(trip_id), str(gr_no), desc]
        s_name = {"Cash":"Cash_Ledger", "canara bank 311":"Canara_311_Ledger", "canara bank 41":"Canara_41_Ledger", "bob":"BOB_Ledger"}.get(bank_name)
        if s_name: db.worksheet(s_name).append_row(base + [int(received_amt)], table_range="A1")
        st.cache_data.clear(); return True
    except: return False

def save_transfer_ledgers(date_val, from_acc, to_acc, amount, remarks):
    try:
        db = connect_to_sheet()
        amt = int(amount)
        s_map = {"Cash":"Cash_Ledger", "canara bank 311":"Canara_311_Ledger", "canara bank 41":"Canara_41_Ledger", "bob":"BOB_Ledger", "Shekh Filling (Pump)":"Shekh_Filling_Ledger", "Ishtyaque Ledger":"Ishtyaque_Ledger", "Universal Ledger":"Universal_Ledger"}
        f_s = s_map.get(from_acc); t_s = s_map.get(to_acc)
        if f_s: db.worksheet(f_s).append_row([str(date_val), "Transfer", "Debit", f"To: {to_acc} | {remarks}", -amt], table_range="A1")
        if t_s:
            if to_acc in ["Ishtyaque Ledger", "Universal Ledger"]:
                db.worksheet(t_s).append_row([str(date_val), "Transfer", "N/A", "N/A", f"From: {from_acc}", amt], table_range="A1")
            else:
                db.worksheet(t_s).append_row([str(date_val), "Transfer", "Credit", f"From: {from_acc}", amt], table_range="A1")
        st.cache_data.clear(); return True
    except: return False

# --- 5. DAY BOOK LOGIC ---
def save_daybook_to_db(row_data):
    try:
        db = connect_to_sheet()
        db.worksheet("Day_Book").append_row(row_data, table_range="A1")
        st.cache_data.clear()
        return True
    except: return False

def save_daybook_ledgers(date_val, account_name, entry_type, category, amount, remarks):
    try:
        db = connect_to_sheet()
        final_amount = int(amount) if entry_type == "Credit (पैसा आया / जमा)" else -int(amount)
        base_data = [str(date_val), "Manual Entry", str(entry_type), f"{category} - {remarks}" if remarks else category]
        
        s_name = {"Cash":"Cash_Ledger", "canara bank 311":"Canara_311_Ledger", "canara bank 41":"Canara_41_Ledger", "bob":"BOB_Ledger"}.get(account_name)
        if s_name:
            db.worksheet(s_name).append_row(base_data + [final_amount], table_range="A1")
        
        st.cache_data.clear()
        return True
    except: return False

# --- 6. REPORTS, DASHBOARD & POD ---
@st.cache_data(ttl=60)
def get_sheet_data_for_reports(sheet_name):
    try:
        db = connect_to_sheet(); data = db.worksheet(sheet_name).get_all_values()
        return pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def get_ledger_stats(sheet_name):
    df = get_sheet_data_for_reports(sheet_name)
    if not df.empty:
        df.iloc[:, -1] = pd.to_numeric(df.iloc[:, -1], errors='coerce').fillna(0)
        return {"balance": int(df.iloc[:, -1].sum())}
    return {"balance": 0}

@st.cache_data(ttl=60)
def get_dashboard_stats():
    stats = {"total_freight": 0, "total_trips": 0, "total_advance": 0, "total_cleared": 0}
    try:
        db = connect_to_sheet()
        if db:
            try:
                b_data = db.worksheet("Bookings").get_all_values()
                stats["total_trips"] = len(b_data) - 1 if len(b_data) > 1 else 0
                for row in b_data[1:]:
                    try: stats["total_freight"] += int(row[11]) 
                    except: pass
            except: pass
            try:
                a_data = db.worksheet("Advances").get_all_values()
                for row in a_data[1:]:
                    try: stats["total_advance"] += abs(int(row[8])) 
                    except: pass
            except: pass
            try:
                r_data = db.worksheet("Receivables").get_all_values()
                for row in r_data[1:]:
                    try: stats["total_cleared"] += (int(row[4]) + int(row[6])) 
                    except: pass
            except: pass
        return stats
    except: return stats

@st.cache_data(ttl=60)
def get_company_shortage(trip_id):
    df = get_sheet_data_for_reports("Company_PODs")
    if not df.empty:
        row = df[df.iloc[:, 1] == trip_id]
        if not row.empty: return int(row.iloc[0, 5])
    return 0

def save_company_pod_status(date_val, trip_id, gr_no, truck_no, shortage):
    try:
        db = connect_to_sheet(); db.worksheet("Company_PODs").append_row([str(date_val), str(trip_id), str(gr_no), str(truck_no), "Submitted", int(shortage)], table_range="A1")
        st.cache_data.clear(); return True
    except: return False

def save_owner_adjustment(date_val, trip_id, gr_no, amount, remarks):
    try:
        db = connect_to_sheet()
        base_data = [str(date_val), str(trip_id), str(gr_no), "Adjustment / Penalty", remarks]
        db.worksheet("Owner_Ledger").append_row(base_data + [int(amount)], table_range="A1")
        st.cache_data.clear()
        return True
    except: return False