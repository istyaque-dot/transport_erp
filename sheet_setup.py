import streamlit as st
from sheet_utils import REQUIRED_SHEETS, ensure_required_sheets, connect_to_sheet, worksheet_values


def show_sheet_setup_page():
    st.header("🧩 Google Sheet Setup / Health Check")
    st.write("यह tab missing worksheets और empty headers को safely create करता है। Existing data overwrite नहीं होता।")

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("✅ Required Sheets Check / Create", type="primary", use_container_width=True):
            with st.spinner("Google Sheet check हो रही है..."):
                result = ensure_required_sheets()
            st.success("Check complete")
            st.dataframe(
                [{"Sheet": k, "Status": v} for k, v in result.items()],
                use_container_width=True,
                hide_index=True,
            )
    with c2:
        st.info("Run this once after deployment, and again only when a new tab/sheet is added.")

    st.divider()
    st.subheader("Required sheet tabs")
    summary = []
    try:
        connect_to_sheet()
        for sheet_name, headers in REQUIRED_SHEETS.items():
            values = worksheet_values(sheet_name)
            summary.append({
                "Sheet": sheet_name,
                "Rows": max(0, len(values) - 1) if values else 0,
                "Required Columns": len(headers),
                "Status": "OK" if values else "Missing/Empty",
            })
        st.dataframe(summary, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Google Sheet connection error: {exc}")
