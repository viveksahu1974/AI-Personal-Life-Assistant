# LifePilot — AI Personal Life Assistant

A mobile-friendly, **working single-user local web app** built with **React + Vite**, **Python FastAPI**, and **SQLite**. No paid service or account is required for the core features.

## What works

- **Overview:** summary cards, task-completion ring, priority list, expense breakdown, upcoming reminders.
- **Tasks:** add, edit, search, mark complete/incomplete, delete, choose category and priority, optional due date.
- **Reminders:** create, see due/pending/completed, acknowledge, delete, view alerts in the app. Optional browser notifications while the page is open.
- **Expenses:** add/delete entries, browse by month, categorize spending, save a monthly budget and see remaining balance.
- **Assistant:** **offline rule-based** answers based on saved tasks/reminders/budget. Optional **genuine generative AI** via a server-side `OPENAI_API_KEY`; no key is required to use the rest of the app.
- **Optional SMTP:** email reminders while the backend is running, even if the browser is closed (requires a mail account/server configuration).
- **Data persistence:** SQLite stores data between app restarts. No example records are inserted.

> IMPORTANT: This is a **single-user local project without login/authentication**. Do not deploy the backend as a public internet service without adding authentication, access controls, HTTPS, rate limiting and backups.

## Folder structure

```text
LifePilot/
├── README.md
├── START_BACKEND.bat         # Double-click in Windows
├── START_FRONTEND.bat        # Double-click in Windows
├── start_backend.sh          # Linux/macOS
├── start_frontend.sh         # Linux/macOS
├── backend/
│   ├── .env.example          # Private configuration template
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py           # FastAPI endpoints, SQLite, assistant, optional SMTP
│   └── tests/
│       └── test_api.py       # API unit/integration tests
└── frontend/
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── vite.config.js        # Proxies /api to FastAPI on 127.0.0.1:8000
    └── src/
        ├── main.jsx         # React UI and all pages
        ├── api.js            # API client + date/currency helpers
        └── style.css        # Responsive dashboard styling
```

## Setup on Windows (VS Code)

Install **Python 3.10+** and **Node.js 20.19+** (or a later compatible LTS release). During Python installation, check **Add Python to PATH**.

**Step 1:** Download and unzip `LifePilot.zip`, then open the `LifePilot` folder in VS Code.

**Step 2 — Backend:** Open Terminal > New Terminal, and type:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Leave that terminal running. Test the backend at **http://127.0.0.1:8000/docs** — it shows the interactive Swagger API. If `py` is unavailable, use `python` to create the virtual environment.

**Step 3 — Frontend:** Open a **second** terminal in the root `LifePilot` directory:

```powershell
cd frontend
npm install
npm run dev
```

**Step 4:** Open **http://127.0.0.1:5173** in your browser. Add a task, set a reminder, add an expense and try the assistant.

**Next time:** After setup, run `START_BACKEND.bat` and `START_FRONTEND.bat` in separate windows from the extracted LifePilot folder.

### One-command Windows setup (alternative)

You can also run `START_BACKEND.bat` and `START_FRONTEND.bat` from the project folder without typing the setup commands. They install missing dependencies on first run. **Both windows must remain open** while you use the app.

## Linux/macOS

```bash
# terminal 1
cd LifePilot
bash start_backend.sh

# terminal 2
cd LifePilot
bash start_frontend.sh
```

Open **http://127.0.0.1:5173**.

## Optional: real AI replies

By default the assistant operates without internet or API keys, using a **rule-based response engine**. For general-purpose generative AI:

1. Copy `backend/.env.example` to `backend/.env` if you haven't already.
2. Set `OPENAI_API_KEY=YOUR_SECRET_KEY` in **backend/.env**.
3. Optionally change `OPENAI_MODEL=gpt-4.1-mini` to an available model in your account.
4. Restart the backend. Check **Settings** in the app for **Generative AI: Enabled**.

The backend calls OpenAI's `/v1/responses` API. It sends the question and a brief summary of task titles/priorities and budget statistics. **API calls may have a cost** depending on the service account. If the AI request fails, the app transparently falls back to offline mode. Never put API keys in the React/frontend `.env` file or commit your backend `.env` to GitHub.

## Optional: email reminders while browser is closed

Update `backend/.env`:

```dotenv
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=you@example.com
REMINDER_TO_EMAIL=you@example.com
SMTP_USE_TLS=true
```

Restart the backend. The email worker checks due reminders approximately every 30 seconds **while the backend server is running**. Port 465 can also be used for SSL. Avoid using your regular account password; use an app password or a dedicated SMTP service. Failed emails are retried later. Acknowledged reminders are no longer emailed. For reliability on multiple backend processes you would need a real job queue/locking system; the local project is intended for **one server process**.

**Notification limits:** Browser notification alerts only work while this website is open, and require permission. If you close it without configuring SMTP, no notification is pushed in the background; unacknowledged due reminders appear when you reopen the app. The email worker still needs the Python backend running. Full web push while both browser and backend are closed requires a separate hosted push infrastructure.

## Architecture

```text
React + Vite (http://127.0.0.1:5173)
    │
    └── fetch /api/... (Vite dev proxy)
          │
          ▼
FastAPI (http://127.0.0.1:8000)
    ├── SQLite (lifepilot.db on disk)
    ├── Offline assistant (rule-based)
    ├── Optional hosted AI (OPENAI_API_KEY)
    └── Optional background SMTP email loop (server running)
```

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Safe feature-state booleans only |
| GET/POST | `/api/tasks` | List/create tasks |
| PATCH/DELETE | `/api/tasks/{id}` | Edit/delete task |
| GET/POST | `/api/reminders` | List/create reminders |
| GET | `/api/reminders/due` | Pending reminders that are due |
| PATCH | `/api/reminders/{id}/acknowledge` | Mark reminder done |
| DELETE | `/api/reminders/{id}` | Delete reminder |
| GET/POST | `/api/expenses` | List/create expenses |
| DELETE | `/api/expenses/{id}` | Delete an expense |
| GET/PUT | `/api/budgets/{YYYY-MM}` | Read/save monthly budget |
| GET | `/api/dashboard?month=YYYY-MM` | Dashboard summary |
| POST | `/api/assistant` | Local assistant or configured AI |

Explore full request schemas and response formats at `/docs` when the backend is running.

## Testing

From `backend` (after installing backend dependencies):

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux/macOS use `.venv/bin/python` instead. Tests use a temporary **separate** SQLite database.

Front-end build validation (after `npm install`):

```bash
cd frontend
npm run build
```

### Demo checklist

1. Create a College task: "Finish assignment" with High priority and a due date. Check it in the Overview focus list.
2. Mark the task complete, then undo it; verify the dashboard counters change.
3. Set a reminder one minute in the future; leave the app open, grant browser permissions and verify the due alert. Acknowledge it.
4. Create an expense of ₹120, set this month's budget to ₹1000; verify ₹880 remains (unless other expenses exist).
5. Ask the assistant **"Plan my day"**, **"How is my budget?"** or **"What are my reminders?"**.
6. Stop and restart both servers; your stored task and expense should still be present.

## Common troubleshooting

- **Frontend says "Cannot reach LifePilot backend"**: run the backend first. Visit `http://127.0.0.1:8000/api/health`, and check that it returns `{"ok":true,...}`.
- **`python` or `py` not recognized**: install Python and ensure it is added to PATH; restart your terminal.
- **`npm` not recognized**: install Node.js LTS and restart your terminal.
- **Port already in use**: shut down the previously running backend/frontend process, then retry.
- **AI isn't giving open-ended answers**: without `OPENAI_API_KEY`, the app intentionally uses offline, rule-based answers.
- **No reminder while the laptop is asleep**: sleeping/stopped servers cannot send scheduled SMTP emails. Browser alerts require an open site.
- **Data backups**: back up `backend/lifepilot.db` **after stopping the backend**, or use SQLite's backup API if you need a live backup. Don't delete this file when updating the frontend.

## Future upgrades

Authentication and user accounts; recurring reminders; voice commands; calendar sync; end-to-end testing in a browser; mobile PWA with true push notifications; deployment with HTTPS and backup rotation; multi-user database isolation.

---

**Educational local-first project** built for learning full-stack development. Core tasks, budgets and reminders require no paid AI service. Data is stored locally unless you explicitly enable an external AI or SMTP provider.

---

## LifePilot v2.0 — Expense & Income Tracker upgrade (November 2026)

The old task and reminder modules continue to work. The Expenses section is now a full money manager:

- **Expense dashboard:** monthly credit (money in), debit (money out), net movement, budget remaining, debit category bars and day-by-day activity.
- **Create / Edit / Delete:** transactions have amount, title, category, date, notes and type (credit or debit).
- **13 requested categories:** Food, Study, Travel, Shopping, Bank, House Rent, Personal, Gym, Health, Drink, Petrol, Clothes, Other. Older `Bills`/`Education` labels are also readable to preserve existing data.
- **Undo:** click Undo to reverse the most recent expense create, update, or delete. The history is kept in SQLite and survives reloads. Undo is for expense changes, not every action elsewhere in LifePilot.
- **Download selected month's report:** PDF, Excel (`.xlsx` with Dashboard and Transactions sheets), or CSV. CSV and XLSX treat entered strings as text to reduce formula-injection risk.
- **Non-destructive database migration:** older expense records are kept; they become debit entries. Database stays at `backend/lifepilot.db` unless overridden.
- **Standalone browser website:** `docs/index.html` works independently of FastAPI using your browser's localStorage. It includes the above money-tracking basics, undo, CSV, true XLSX, JSON backup/import, and `Print / Save PDF` via the browser print dialog. For this website, undo and data persistence are stored locally in the browser. Data does NOT sync with the Python/SQLite version.

### Run complete React + Python project

On Windows, extract the ZIP and double-click `START_BACKEND.bat`, then `START_FRONTEND.bat`. Open `http://127.0.0.1:5173` and choose **Expenses** in the sidebar, then **Dashboard** or **Transactions**.

Backend REST routes for the upgrade:

| Method | API route | Purpose |
| --- | --- | --- |
| GET | `/api/expenses?month=YYYY-MM` | List month's active transactions |
| POST | `/api/expenses` | Create credit or debit |
| PATCH | `/api/expenses/{id}` | Edit a transaction |
| DELETE | `/api/expenses/{id}` | Soft-delete transaction (undoable) |
| POST | `/api/expenses/undo` | Undo latest transaction edit/create/delete |
| GET | `/api/expenses/undo-status` | Show whether undo is possible |
| GET | `/api/expenses/summary?month=YYYY-MM` | Statistics, categories, daily totals |
| GET | `/api/expenses/categories` | 13 default categories |
| GET | `/api/expenses/export?month=YYYY-MM&format=pdf` | Download a PDF |
| GET | `/api/expenses/export?month=YYYY-MM&format=xlsx` | Download actual Excel workbook |
| GET | `/api/expenses/export?month=YYYY-MM&format=csv` | Download CSV |

Budget APIs remain `/api/budgets/{month}`. Budget counts debits, not credits. "Net movement" is credits minus debits for a date range; it is NOT actual bank-account balance. The full project is intentionally localhost-only until proper accounts, authentication and HTTPS are implemented.

### Open standalone expense-tracker website

Open `docs/index.html` (or the separate `LifePilot_Expense_Tracker_Website.html` download) in Chrome or Edge; no installation or server is required. Create a credit and debit; the charts update instantly. Press Undo after adding, editing or deleting. Open Reports to download an Excel, CSV or JSON file, or click **Print / Save PDF** and choose your browser's PDF printer.

**Important:** The standalone website saves records to your current browser's localStorage only. Export a JSON backup regularly. It is not connected to your bank and it does not sync between devices or with the Python backend.

### Publish the standalone website using GitHub Pages

GitHub Pages hosts static files but not Python/FastAPI. To publish the independent expense-tracker version: upload the `docs/index.html` file to your GitHub repository, then open the repository's **Settings → Pages → Build and deployment**. Select **Deploy from a branch** → `main` → `/docs`, then Save. The URL will typically be `https://<username>.github.io/<repository>/` once GitHub confirms publishing; verify the actual URL shown by GitHub Pages before sharing it. **Do not publish `backend/lifepilot.db` or any `.env` or API-key files.** To host the full React + FastAPI version publicly, you need separate backend hosting with user authentication and a persistent database.

### Tests and compatibility

Run the backend tests with `cd backend && python -m pytest -q` (install `pytest` first if missing). Backend tests cover credit/debit, categories, edit, undo, delete, summary and all three export formats. React source was checked for JSX syntax but a full Vite dependency install/build was not available in this environment; run `npm install && npm run build` on your computer.
