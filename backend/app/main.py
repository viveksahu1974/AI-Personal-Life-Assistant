"""LifePilot: local-first single-user personal assistant API.

No account authentication is included. Run on localhost only until secured.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import smtplib
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / '.env')
raw_db_path = Path(os.getenv('DATABASE_PATH', './lifepilot.db'))
DB_PATH = raw_db_path if raw_db_path.is_absolute() else BACKEND_DIR / raw_db_path
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger('lifepilot')


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(dt: datetime | None = None) -> str:
    return (dt or utc_now()).astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_dt(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError('Date/time must include a timezone offset')
    return timestamp(value)


def validate_month(month: str) -> str:
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise HTTPException(422, 'month must be YYYY-MM')
    return month


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=10000')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def to_dict(row: sqlite3.Row | None):
    return dict(row) if row else None


def initialize_db():
    with connect() as conn:
        conn.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'Personal',
            priority TEXT NOT NULL DEFAULT 'Medium',
            due_at TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_tasks_due ON tasks(due_at);
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            remind_at TEXT NOT NULL,
            acknowledged_at TEXT,
            email_sent_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_reminders_due ON reminders(remind_at);
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            category TEXT NOT NULL,
            spent_on TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_expenses_date ON expenses(spent_on);
        CREATE TABLE IF NOT EXISTS budgets (
            month TEXT PRIMARY KEY,
            amount REAL NOT NULL CHECK(amount >= 0)
        );
        ''')


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    notes: str = Field(default='', max_length=1500)
    category: Literal['Personal', 'College', 'Work', 'Health'] = 'Personal'
    priority: Literal['Low', 'Medium', 'High'] = 'Medium'
    due_at: datetime | None = None

    @field_validator('title')
    @classmethod
    def strip_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Title cannot be empty')
        return value

    @field_validator('due_at')
    @classmethod
    def aware_date(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('Date/time needs a timezone offset')
        return value


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    notes: str | None = Field(default=None, max_length=1500)
    category: Literal['Personal', 'College', 'Work', 'Health'] | None = None
    priority: Literal['Low', 'Medium', 'High'] | None = None
    due_at: datetime | None = None
    completed: bool | None = None

    @field_validator('title')
    @classmethod
    def strip_title(cls, value):
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError('Title cannot be empty')
        return value

    @field_validator('due_at')
    @classmethod
    def aware_date(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('Date/time needs a timezone offset')
        return value


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    message: str = Field(default='', max_length=1000)
    remind_at: datetime

    @field_validator('title')
    @classmethod
    def strip_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Title cannot be empty')
        return value

    @field_validator('remind_at')
    @classmethod
    def aware_date(cls, value):
        if value.tzinfo is None:
            raise ValueError('Date/time needs a timezone offset')
        return value


class ExpenseIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    amount: float = Field(gt=0, le=100000000)
    category: Literal['Food', 'Travel', 'Shopping', 'Bills', 'Education', 'Health', 'Other'] = 'Other'
    spent_on: date = Field(default_factory=date.today)

    @field_validator('title')
    @classmethod
    def strip_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Title cannot be empty')
        return value


class BudgetIn(BaseModel):
    amount: float = Field(ge=0, le=100000000)


class AssistantIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def smtp_configured():
    return all(os.getenv(k) for k in ('SMTP_HOST', 'SMTP_FROM', 'REMINDER_TO_EMAIL'))


def deliver_email(reminder: dict):
    message = EmailMessage()
    message['Subject'] = 'LifePilot reminder: ' + reminder['title']
    message['From'] = os.environ['SMTP_FROM']
    message['To'] = os.environ['REMINDER_TO_EMAIL']
    message.set_content(f"{reminder['title']}\n\n{reminder['message']}\n\nScheduled: {reminder['remind_at']}")
    port = int(os.getenv('SMTP_PORT', '587'))
    if port == 465:
        client = smtplib.SMTP_SSL(os.environ['SMTP_HOST'], port, timeout=12)
    else:
        client = smtplib.SMTP(os.environ['SMTP_HOST'], port, timeout=12)
    with client:
        if port != 465 and os.getenv('SMTP_USE_TLS', 'true').lower() == 'true':
            client.starttls()
        username = os.getenv('SMTP_USERNAME')
        if username:
            client.login(username, os.getenv('SMTP_PASSWORD', ''))
        client.send_message(message)


async def email_worker():
    """Optional email delivery. App reminders do not require this worker."""
    while True:
        try:
            if smtp_configured():
                with connect() as conn:
                    rows = conn.execute('''SELECT * FROM reminders WHERE remind_at <= ?
                        AND acknowledged_at IS NULL AND email_sent_at IS NULL
                        ORDER BY remind_at LIMIT 30''', (timestamp(),)).fetchall()
                for row in rows:
                    item = dict(row)
                    try:
                        await asyncio.to_thread(deliver_email, item)
                        with connect() as conn:
                            conn.execute('UPDATE reminders SET email_sent_at = ? WHERE id = ? AND email_sent_at IS NULL', (timestamp(), item['id']))
                    except Exception:
                        logger.exception('Could not send reminder email for %s', item['id'])
        except Exception:
            logger.exception('Reminder worker error')
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    worker = asyncio.create_task(email_worker())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title='LifePilot API', version='1.0.0', lifespan=lifespan)
origins = [s.strip() for s in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], allow_headers=['Content-Type'])


@app.get('/api/health')
def health():
    return {'ok': True, 'name': 'LifePilot', 'version': '1.0.0'}


@app.get('/api/config')
def config():
    return {'ai_enabled': bool(os.getenv('OPENAI_API_KEY')), 'email_enabled': smtp_configured(), 'mode': 'single-user-local'}


@app.get('/api/tasks')
def list_tasks(status: Literal['all', 'active', 'done'] = 'all', q: str = ''):
    query = 'SELECT * FROM tasks WHERE 1 = 1'
    values = []
    if status != 'all':
        query += ' AND completed = ?'
        values.append(1 if status == 'done' else 0)
    if q.strip():
        query += ' AND (title LIKE ? OR notes LIKE ?)'
        values.extend([f'%{q.strip()}%'] * 2)
    query += ' ORDER BY completed ASC, CASE priority WHEN "High" THEN 0 WHEN "Medium" THEN 1 ELSE 2 END, due_at IS NULL, due_at ASC, id DESC'
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, values).fetchall()]


@app.post('/api/tasks', status_code=201)
def create_task(task: TaskIn):
    now = timestamp()
    with connect() as conn:
        cur = conn.execute('INSERT INTO tasks (title, notes, category, priority, due_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (task.title, task.notes, task.category, task.priority, parse_dt(task.due_at) if task.due_at else None, now, now))
        return to_dict(conn.execute('SELECT * FROM tasks WHERE id = ?', (cur.lastrowid,)).fetchone())


@app.patch('/api/tasks/{task_id}')
def update_task(task_id: int, patch: TaskPatch):
    fields = patch.model_fields_set
    allowed = ('title', 'notes', 'category', 'priority', 'due_at', 'completed')
    updates = {}
    for key in allowed:
        if key in fields:
            value = getattr(patch, key)
            if key in ('title', 'notes', 'category', 'priority', 'completed') and value is None:
                raise HTTPException(422, f'{key} cannot be null')
            if key == 'due_at':
                value = parse_dt(value) if value else None
            if key == 'completed':
                value = int(value)
            updates[key] = value
    with connect() as conn:
        row = conn.execute('SELECT id FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Task not found')
        if updates:
            updates['updated_at'] = timestamp()
            columns = ', '.join(f'{name} = ?' for name in updates)
            conn.execute(f'UPDATE tasks SET {columns} WHERE id = ?', (*updates.values(), task_id))
        return to_dict(conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone())


@app.delete('/api/tasks/{task_id}')
def delete_task(task_id: int):
    with connect() as conn:
        cur = conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Task not found')
    return {'ok': True}


@app.get('/api/reminders')
def list_reminders():
    with connect() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM reminders ORDER BY acknowledged_at IS NOT NULL, remind_at ASC').fetchall()]


@app.get('/api/reminders/due')
def due_reminders():
    with connect() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM reminders WHERE acknowledged_at IS NULL AND remind_at <= ? ORDER BY remind_at', (timestamp(),)).fetchall()]


@app.post('/api/reminders', status_code=201)
def create_reminder(reminder: ReminderIn):
    with connect() as conn:
        cur = conn.execute('INSERT INTO reminders (title, message, remind_at, created_at) VALUES (?, ?, ?, ?)',
            (reminder.title, reminder.message, parse_dt(reminder.remind_at), timestamp()))
        return to_dict(conn.execute('SELECT * FROM reminders WHERE id = ?', (cur.lastrowid,)).fetchone())


@app.patch('/api/reminders/{reminder_id}/acknowledge')
def acknowledge_reminder(reminder_id: int):
    with connect() as conn:
        cur = conn.execute('UPDATE reminders SET acknowledged_at = COALESCE(acknowledged_at, ?) WHERE id = ?', (timestamp(), reminder_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Reminder not found')
        return to_dict(conn.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,)).fetchone())


@app.delete('/api/reminders/{reminder_id}')
def delete_reminder(reminder_id: int):
    with connect() as conn:
        cur = conn.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Reminder not found')
    return {'ok': True}


@app.get('/api/expenses')
def list_expenses(month: str | None = None):
    with connect() as conn:
        if month:
            validate_month(month)
            rows = conn.execute('SELECT * FROM expenses WHERE substr(spent_on, 1, 7) = ? ORDER BY spent_on DESC, id DESC', (month,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM expenses ORDER BY spent_on DESC, id DESC LIMIT 500').fetchall()
        return [dict(row) for row in rows]


@app.post('/api/expenses', status_code=201)
def create_expense(expense: ExpenseIn):
    with connect() as conn:
        cur = conn.execute('INSERT INTO expenses (title, amount, category, spent_on, created_at) VALUES (?, ?, ?, ?, ?)',
            (expense.title, round(expense.amount, 2), expense.category, expense.spent_on.isoformat(), timestamp()))
        return to_dict(conn.execute('SELECT * FROM expenses WHERE id = ?', (cur.lastrowid,)).fetchone())


@app.delete('/api/expenses/{expense_id}')
def delete_expense(expense_id: int):
    with connect() as conn:
        cur = conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Expense not found')
    return {'ok': True}


@app.get('/api/budgets/{month}')
def get_budget(month: str):
    validate_month(month)
    with connect() as conn:
        row = conn.execute('SELECT amount FROM budgets WHERE month = ?', (month,)).fetchone()
        return {'month': month, 'amount': row['amount'] if row else 0}


@app.put('/api/budgets/{month}')
def set_budget(month: str, data: BudgetIn):
    validate_month(month)
    with connect() as conn:
        conn.execute('INSERT INTO budgets(month, amount) VALUES (?, ?) ON CONFLICT(month) DO UPDATE SET amount = excluded.amount', (month, round(data.amount, 2)))
    return {'month': month, 'amount': round(data.amount, 2)}


@app.get('/api/dashboard')
def dashboard(month: str | None = None):
    month = validate_month(month or date.today().strftime('%Y-%m'))
    now = timestamp()
    with connect() as conn:
        tasks = conn.execute('''SELECT COUNT(*) AS total, SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS active,
           SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done,
           SUM(CASE WHEN completed = 0 AND due_at IS NOT NULL AND due_at < ? THEN 1 ELSE 0 END) AS overdue
           FROM tasks''', (now,)).fetchone()
        focus = [dict(row) for row in conn.execute('''SELECT * FROM tasks WHERE completed = 0
           ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
           due_at IS NULL, due_at ASC LIMIT 5''').fetchall()]
        monthly = conn.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE substr(spent_on, 1, 7) = ?', (month,)).fetchone()['total']
        categories = [dict(row) for row in conn.execute('''SELECT category, ROUND(SUM(amount), 2) AS total FROM expenses
           WHERE substr(spent_on, 1, 7) = ? GROUP BY category ORDER BY total DESC''', (month,)).fetchall()]
        budget = conn.execute('SELECT amount FROM budgets WHERE month = ?', (month,)).fetchone()
        upcoming_reminders = [dict(row) for row in conn.execute('''SELECT * FROM reminders WHERE acknowledged_at IS NULL
           ORDER BY remind_at LIMIT 4''').fetchall()]
        recent_expenses = [dict(row) for row in conn.execute('''SELECT * FROM expenses WHERE substr(spent_on, 1, 7) = ?
            ORDER BY spent_on DESC, id DESC LIMIT 4''', (month,)).fetchall()]
    return {
        'month': month,
        'tasks': {k: tasks[k] or 0 for k in ('total', 'active', 'done', 'overdue')},
        'focus': focus,
        'spending': round(monthly, 2),
        'budget': budget['amount'] if budget else 0,
        'categories': categories,
        'upcoming_reminders': upcoming_reminders,
        'recent_expenses': recent_expenses,
    }


def offline_assistant(message: str, snapshot: dict) -> str:
    prompt = message.lower()
    active = snapshot['tasks']['active']
    overdue = snapshot['tasks']['overdue']
    spending = snapshot['spending']
    budget = snapshot['budget']
    focus = snapshot['focus']
    if any(w in prompt for w in ('expense', 'spend', 'money', 'budget', 'paise', 'kharcha', 'save')):
        summary = f"This month you've spent ₹{spending:,.2f}. "
        if budget:
            left = budget - spending
            summary += f"Your budget is ₹{budget:,.2f}. "
            summary += f"You have ₹{left:,.2f} left." if left >= 0 else f"You're ₹{-left:,.2f} over budget."
        else:
            summary += 'Set a monthly budget in Expenses to track how much is left.'
        if snapshot['categories']:
            top = snapshot['categories'][0]
            summary += f" Your biggest category is {top['category']} (₹{top['total']:,.2f})."
        return summary
    if any(w in prompt for w in ('remind', 'alarm', 'notification', 'yaad')):
        reminders = snapshot['upcoming_reminders']
        if not reminders:
            return 'No pending reminders right now. Open Reminders to add a time and message. Enable browser notifications for alerts while the app is open.'
        return 'Your next reminders: ' + '; '.join(f"{r['title']} ({r['remind_at']})" for r in reminders[:3]) + '.'
    if any(w in prompt for w in ('plan', 'study', 'today', 'task', 'schedule', 'assignment', 'college', 'focus', 'din')):
        if not focus:
            return 'Your task list is clear! Add your next college, work or personal task, then I can prioritize it for you.'
        tasks = '\n'.join(f"{i}. {t['title']} — {t['priority']} priority" for i, t in enumerate(focus[:3], 1))
        return f"You have {active} unfinished tasks ({overdue} overdue). Here's a practical focus plan:\n{tasks}\nStart with a 25-minute focus session, then take a 5-minute break. Complete the highest-priority task first."
    return (f"I'm your offline LifePilot assistant. You have {active} active tasks, {overdue} overdue, and ₹{spending:,.2f} spent this month. "
            "Ask 'Plan my day', 'How is my budget?', or 'What are my reminders?'. For open-ended generative AI answers, configure OPENAI_API_KEY in backend/.env.")


@app.post('/api/assistant')
async def assistant(message: AssistantIn):
    snapshot = dashboard()
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if key:
        task_titles = [f"{t['title']} ({t['priority']}, due {t['due_at'] or 'unscheduled'})" for t in snapshot['focus']]
        system = ("You are LifePilot, a concise and practical personal productivity assistant. "
                  "Give simple plans, do not pretend you can perform changes to the user's records, "
                  "and never invent task details or reminders. Reply in the user's language. "
                  f"Current data: active tasks={snapshot['tasks']['active']}, overdue={snapshot['tasks']['overdue']}, "
                  f"monthly spending INR={snapshot['spending']}, budget INR={snapshot['budget']}, "
                  f"top current tasks={task_titles}.")
        try:
            async with httpx.AsyncClient(timeout=18) as client:
                response = await client.post('https://api.openai.com/v1/responses',
                    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                    json={'model': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), 'instructions': system, 'input': message.message, 'max_output_tokens': 450})
                response.raise_for_status()
                payload = response.json()
                segments = []
                for output in payload.get('output', []):
                    for part in output.get('content', []):
                        if part.get('type') == 'output_text':
                            segments.append(part.get('text', ''))
                if segments:
                    return {'reply': '\n'.join(segments), 'mode': 'ai'}
                logger.warning('AI response had no output_text fields')
        except Exception:
            logger.exception('AI provider failed; using offline assistant')
        return {'reply': 'Online AI was unavailable, so I switched to offline help.\n\n' + offline_assistant(message.message, snapshot), 'mode': 'offline'}
    return {'reply': offline_assistant(message.message, snapshot), 'mode': 'offline'}
