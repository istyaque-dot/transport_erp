# OCR API Disabled / Not Found Fix

- Long Google Vision API disabled error को clean message में बदला गया.
- अगर Vision API disabled/permission issue है तो page पर clear instruction दिखेगा.
- OCR raw error अब पूरी long URL warning की तरह screen पर नहीं फैलेगा.
- OCR fields Not found आने का main reason API disabled हो तो user को direct setup message मिलेगा.

Required setup:
1. Google Cloud Console में वही project खोलें जो service account में है.
2. Cloud Vision API enable करें.
3. Streamlit app reboot करें.
4. 2-5 minute wait करके फिर OCR test करें.
