# Bulk OCR Upload Update

Added menu: 🤖 Bulk OCR Upload

Logic:
- OCR reads GR No, Truck No, Destination, Date.
- Score: GR 40 + Truck 30 + Destination 20 + Date 10.
- Score >= 90 auto matched; lower scores require confirmation.
- POD Copy: same matched trip files are combined into one multi-page A4 PDF.
- GR Copy: each file becomes one single-page A4 PDF.

Requires:
- google-cloud-vision in requirements.txt
- Google Cloud Vision API enabled on the same service account project
- existing gcp_service_account secret
