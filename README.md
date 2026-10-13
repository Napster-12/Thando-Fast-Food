# THANDO FAST FOOD

Website for Thando Fast Food in Ntuzuma: online menu with ordering for collection,
table bookings, a help chat with order tracking, and staff pages for orders, bookings and stock.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000.

## Pages

| Page | URL | Who |
|------|-----|-----|
| Home | `/` | Everyone |
| Menu & checkout | `/menu` | Everyone |
| Book a table | `/reservation` | Everyone |
| Help & chat (track orders with `TF-12345`) | `/chat` | Everyone |
| Orders & bookings | `/admin` | Staff (login) |
| Stock dashboard | `/management` | Staff (login) |

## Settings

Set these environment variables before going live:

- `ADMIN_PASSWORD` – staff login password (default `thando-admin`, **change it**).
- `SECRET_KEY` – any long random string, used to sign login sessions.
- `THANDO_DB` – path to the SQLite database file (default `thando.db` next to `app.py`, created automatically).

Menu items, prices, phone number, address and opening hours live at the top of `app.py`
(`STORE` and `MENU`). Images go in `static/images/`.
