# Bulk Booking Edit from Google Sheet

Added inside Booking → Bulk Upload page:

- Bulk_Booking_Edit Google Sheet tab setup/check
- Preview pending rows from Bulk_Booking_Edit
- Match existing bookings by GR No
- Blank cells do not overwrite old booking values
- READY rows update Bookings sheet
- ERROR/SKIP rows are marked in Bulk_Booking_Edit
- Ledgers are refreshed for updated bookings

Required Bulk_Booking_Edit columns:
Status, GR No, Date, Truck No, Company, From, Destination, Weight, Company Rate, Owner Rate, Universal Amt, Ishtyaque Profit, Comments, Error, Processed At
