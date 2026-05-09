# Dashboard Direct Links Update

Updated:
- dashboard.py
- advance.py
- documents.py
- daybook.py

Changes:
- Dashboard now has Direct Work Links section.
- Expense button routes only to Day Book.
- Advance button routes only to Advance page with selected GR/truck prefilled.
- POD Upload button routes only to Docs Upload with POD selected and GR/truck prefilled.
- Documents Upload auto-selects trip when one exact match exists.
- Advance auto-selects selected trip from Dashboard when possible.
- Day Book shows a Dashboard-origin notice for expense entry.

Route safety:
- Buttons use pending_page_choice and do not mutate the sidebar radio key directly.
- POD Upload does not open POD settlement page; it opens Docs Upload.
- Expense does not open Reports/Transfer; it opens Day Book.
