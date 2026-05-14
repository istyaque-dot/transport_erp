# Click Response + Duplicate Save Guard Update

## Added
- Global click feedback for buttons/form submit actions.
- Save/upload/submit/update buttons now show immediate processing message.
- Duplicate save/upload clicks are blocked for a short cooldown window.
- Sidebar safety expander includes **Unlock Buttons** if a browser/session stays locked.

## Updated files
- action_guard.py
- app.py
- booking.py
- daybook.py
- receivable.py
- transfer.py

## Behavior
When user clicks any save/upload/submit/update button:
1. A visible message appears: processing / do not click again.
2. The same action is temporarily disabled.
3. Repeat click within cooldown is ignored to reduce duplicate rows/files.
