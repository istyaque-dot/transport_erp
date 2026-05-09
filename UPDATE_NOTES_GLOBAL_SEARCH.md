# Global Search Update

Added same search sequence across trip/data screens:

GR / Truck No / Destination / Date / Trip ID

Updated screens:
- Booking Edit dropdown
- Advance trip dropdown
- POD trip dropdown
- Receivable payment entry dropdown
- Receivable documents/data list
- Company Hisaab dropdown
- Reports single truck account dropdown
- Reports document print search
- Outstanding data list

Technical:
- Central helpers added in sheet_utils.py
- Search works with empty input showing full list
- Google Sheets read cache remains enabled
- Python compile check passed
