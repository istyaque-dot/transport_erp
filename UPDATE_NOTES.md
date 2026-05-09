# Transport ERP — All Tabs Update

Backend: Google Sheets only.

## Updated navigation tabs
- Home
- Booking
- Advance
- POD
- Receivable
- Outstanding
- Ledger Hub
- Dashboard
- Reports
- Day Book
- Transfer
- Company Hisaab
- Sheet Setup / Health Check

## First run after deploy
1. Login.
2. Open **Sheet Setup / Health Check**.
3. Click **Required Sheets Check / Create**.
4. Test flow: Booking -> Advance -> POD -> Receivable -> Reports.

## Safety behavior
- Existing Google Sheet data is not overwritten.
- Missing worksheets are created.
- Headers are added only when a worksheet is empty.
- Supabase sync is not used in the main operational flow.

## Main required Google Sheet tabs
Bookings, Advances, Receivables, Company_PODs, Owner_Ledger, Company_Ledger, Universal_Ledger, Ishtyaque_Ledger, Cash_Ledger, Canara_311_Ledger, Canara_41_Ledger, BOB_Ledger, Shekh_Filling_Ledger, canara_1747, Day_Book.
