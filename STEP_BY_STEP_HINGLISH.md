# LifePilot ka Code Step-by-Step (Hinglish)

Ye guide tumhare B.Tech IT practical/mini-project demonstration ke liye hai. **Actual code** `backend/app/main.py`, `frontend/src/main.jsx`, `frontend/src/api.js`, aur `frontend/src/style.css` mein hai.

## Step 1: Project run karo

1. Python aur Node.js install karo.
2. **`START_BACKEND.bat`** par double-click karo; backend `127.0.0.1:8000` par run hoga.
3. **`START_FRONTEND.bat`** par double-click karo; React `127.0.0.1:5173` par run hoga.
4. Browser mein `http://127.0.0.1:5173` open karo.

Detailed manual terminal commands ke liye `README.md` dekho.

## Step 2: Frontend aur backend kaise connect hote hain

- React UI `src/main.jsx` mein hai.
- `src/api.js` ka `api('/tasks')` function `GET /api/tasks` request bhejta hai.
- `vite.config.js` automatically `/api/` requests ko Python port **8000** par proxy karta hai.
- FastAPI `app/main.py` request receive karke SQLite se data fetch/save karta hai.
- FastAPI JSON response bhejta hai, React `useState`/`refresh` se screen update karta hai.

Example React call:

```javascript
const tasks = await api('/tasks')
await api('/tasks', {
  method: 'POST',
  body: { title: 'Finish assignment', category: 'College', priority: 'High' }
})
```

## Step 3: SQLite database

`backend/app/main.py` ke `initialize_db()` function se 4 tables bante hain:

- `tasks`: task title, category, priority, due_at, completed
- `reminders`: title, message, remind_at, acknowledged_at, email_sent_at
- `expenses`: expense title, amount, category, spent_on
- `budgets`: YYYY-MM ke hisaab se monthly spending limit

Database file backend ke andar `lifepilot.db` hoti hai. App restart ke baad data bana rehta hai. **Important:** Ye local one-user database hai, production account management nahi.

## Step 4: Task manager

Task form bharke Add Task dabao. React `POST /api/tasks` call karega. Edit karne par `PATCH /api/tasks/{id}` call hota hai. Complete button `completed` field ko toggle karta hai. Delete action `DELETE /api/tasks/{id}` karta hai.

Tasks ko priority aur due date ke hisaab se sort kiya jaata hai. Dashboard par top 5 active tasks show hote hain.

## Step 5: Reminder ka working logic

Reminder set karte waqt browser ka local date/time `new Date(...).toISOString()` se **UTC** mein convert hota hai. Python database mein UTC save karta hai. API `/api/reminders/due` current UTC time ke compare se due reminders deta hai. React har **30 seconds** baad check karta hai.

Agar browser open hai aur permission granted hai, browser notification show hogi. Browser bandh hone par due reminders pending rehte hain aur next visit mein show honge. Browser ke closed state mein email chahiye to SMTP set karo aur backend running rakho.

## Step 6: Expense tracking

Expense save karne par `POST /api/expenses` call hoti hai. Backend month ke hisaab se totals calculate karta hai. Budget `PUT /api/budgets/YYYY-MM` se save hota hai. React spent, budget aur remaining amount show karta hai.

**Example:** Budget ₹1000 aur spent ₹120 ho to ₹880 remaining.

## Step 7: Assistant ka difference samjho

**Offline mode (default):** Python ka `offline_assistant()` user ke question mein keywords dekhkar real tasks/budget/reminder data se practical response banata hai. Ye *rules-based* hai, generative LLM nahi.

**Online AI mode (optional):** `backend/.env` mein `OPENAI_API_KEY` set karo. `POST /api/assistant` OpenAI's Responses API ko query aur brief personal summary bhejta hai. Service fail hone par offline assistant use hota hai.

Secrets frontend mein **kabhi mat likhna**. `.env` ko GitHub par upload mat karna.

## Step 8: Project demo plan

1. Overview dashboard dikhana.
2. Ek College task add aur complete karke dashboard refresh dikhana.
3. Next-minute reminder add karke in-app/browser notification dikhana.
4. Monthly budget set karna, expense add karna, remaining amount show karna.
5. Assistant mein `Plan my day` aur `How is my budget?` poochna.
6. Backend Swagger API page `http://127.0.0.1:8000/docs` open karke API endpoints explain karna.

**Teacher ko explanation:** "LifePilot is a full-stack personal productivity web application developed using React for frontend, FastAPI in Python for backend, and SQLite for database persistence. It manages tasks, time-based reminders and monthly expenses. An offline rule-based personal assistant is included, with optional hosted generative AI and SMTP reminders."

## Step 9: Test

Backend ke andar:

```bash
python -m pytest -q
```

`pytest` install na ho to `python -m pip install pytest` karo. Isme API health, task CRUD, reminders, budget/expense, assistant aur invalid input tests included hain.

## Step 10: Future versions

Multi-user login, voice assistant, Google Calendar sync, recurring reminders, truly background mobile push, cloud hosting aur analytics charts future enhancements hain. Current local MVP ke features ko unimplemented capabilities ke saath confuse mat karo.


## v2.0 Expense Tracker kaise use karein

Standalone website `docs/index.html` ko Chrome/Edge me open karo. Create -> Debit/Credit -> 13 categories me se option -> Save. Dashboard me summary aur charts dikhenge. Galat entry pe Undo. Reports me Excel/CSV/JSON aur browser Print -> Save as PDF.

Full React + FastAPI version ke liye START_BACKEND.bat aur START_FRONTEND.bat chalao, `http://127.0.0.1:5173` pe jao, Expenses select karo. PDF/XLSX/CSV seedha website se download hoga. SQLite me purana data preserved rahega.
