"""LifePilot: local-first single-user personal assistant API.

No account authentication is included. Run on localhost only until secured.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
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
from fastapi.responses import StreamingResponse
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
        # Non-destructive migration: older LifePilot databases contain debit-only expenses.
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(expenses)')}
        for column, ddl in (
            ('entry_type', "TEXT NOT NULL DEFAULT 'debit'"),
            ('notes', "TEXT NOT NULL DEFAULT ''"),
            ('deleted_at', 'TEXT'),
        ):
            if column not in columns:
                conn.execute(f'ALTER TABLE expenses ADD COLUMN {column} {ddl}')
        conn.execute('''CREATE TABLE IF NOT EXISTS expense_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            before_json TEXT,
            after_json TEXT,
            undone INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS ix_expense_actions_active ON expense_actions(undone, id)')


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


EXPENSE_CATEGORIES = (
    'Food', 'Study', 'Travel', 'Shopping', 'Bank', 'House Rent', 'Personal',
    'Gym', 'Health', 'Drink', 'Petrol', 'Clothes', 'Other',
    'Bills', 'Education',  # retained for old records
)


class ExpenseIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    amount: float = Field(gt=0, le=100000000)
    category: str = 'Other'
    entry_type: Literal['debit', 'credit'] = 'debit'
    notes: str = Field(default='', max_length=600)
    spent_on: date = Field(default_factory=date.today)

    @field_validator('title')
    @classmethod
    def strip_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Title cannot be empty')
        return value

    @field_validator('category')
    @classmethod
    def validate_category(cls, value):
        if value not in EXPENSE_CATEGORIES:
            raise ValueError('Choose a supported category')
        return value


class ExpensePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    amount: float | None = Field(default=None, gt=0, le=100000000)
    category: str | None = None
    entry_type: Literal['debit', 'credit'] | None = None
    notes: str | None = Field(default=None, max_length=600)
    spent_on: date | None = None

    @field_validator('title')
    @classmethod
    def strip_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError('Title cannot be empty')
        return value.strip() if value is not None else value

    @field_validator('category')
    @classmethod
    def validate_category(cls, value):
        if value is not None and value not in EXPENSE_CATEGORIES:
            raise ValueError('Choose a supported category')
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


def _log_expense_action(conn, action: str, entry_id: int, before: dict | None, after: dict | None):
    conn.execute('''INSERT INTO expense_actions (action, entry_id, before_json, after_json, created_at)
        VALUES (?, ?, ?, ?, ?)''', (action, entry_id,
        json.dumps(before) if before else None, json.dumps(after) if after else None, timestamp()))


def _finance_rows(conn, month: str | None):
    if month:
        validate_month(month)
        return [dict(x) for x in conn.execute('''SELECT * FROM expenses WHERE deleted_at IS NULL
            AND substr(spent_on, 1, 7) = ? ORDER BY spent_on DESC, id DESC''', (month,)).fetchall()]
    return [dict(x) for x in conn.execute('''SELECT * FROM expenses WHERE deleted_at IS NULL
            ORDER BY spent_on DESC, id DESC''').fetchall()]


def _finance_summary(rows):
    credit = round(sum(float(x['amount']) for x in rows if x['entry_type'] == 'credit'), 2)
    debit = round(sum(float(x['amount']) for x in rows if x['entry_type'] == 'debit'), 2)
    categories = {}
    for x in rows:
        if x['entry_type'] == 'debit':
            categories[x['category']] = round(categories.get(x['category'], 0) + float(x['amount']), 2)
    return {
        'credit': credit, 'debit': debit, 'balance': round(credit - debit, 2),
        'count': len(rows),
        'categories': [{'category': k, 'total': v} for k, v in sorted(categories.items(), key=lambda x: -x[1])],
    }


@app.get('/api/expenses/categories')
def expense_categories():
    return {'categories': list(EXPENSE_CATEGORIES[:13])}


@app.get('/api/expenses/summary')
def expense_summary(month: str | None = None):
    with connect() as conn:
        rows = _finance_rows(conn, month)
        summary = _finance_summary(rows)
        budget_row = conn.execute('SELECT amount FROM budgets WHERE month = ?', (month,)).fetchone() if month else None
        summary['budget'] = budget_row['amount'] if budget_row else 0
        days = {}
        for row in rows:
            day = row['spent_on']
            if day not in days:
                days[day] = {'date': day, 'credit': 0, 'debit': 0}
            days[day][row['entry_type']] += row['amount']
        summary['daily'] = [{**d, 'credit': round(d['credit'], 2), 'debit': round(d['debit'], 2)}
                            for d in sorted(days.values(), key=lambda x: x['date'])]
        return summary


@app.get('/api/expenses/undo-status')
def expense_undo_status():
    with connect() as conn:
        last = conn.execute('''SELECT id, action, entry_id FROM expense_actions
            WHERE undone = 0 ORDER BY id DESC LIMIT 1''').fetchone()
    return {'available': bool(last), 'action': last['action'] if last else None}


@app.get('/api/expenses')
def list_expenses(month: str | None = None):
    with connect() as conn:
        return _finance_rows(conn, month)


@app.post('/api/expenses', status_code=201)
def create_expense(expense: ExpenseIn):
    with connect() as conn:
        cur = conn.execute('''INSERT INTO expenses (title, amount, category, spent_on, created_at, entry_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', (expense.title, round(expense.amount, 2),
            expense.category, expense.spent_on.isoformat(), timestamp(), expense.entry_type, expense.notes))
        item = to_dict(conn.execute('SELECT * FROM expenses WHERE id = ?', (cur.lastrowid,)).fetchone())
        _log_expense_action(conn, 'create', item['id'], None, item)
        return item


@app.patch('/api/expenses/{expense_id}')
def update_expense(expense_id: int, patch: ExpensePatch):
    values = patch.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(422, 'No changes provided')
    if any(v is None for v in values.values()):
        raise HTTPException(422, 'Expense fields cannot be null')
    if 'spent_on' in values:
        values['spent_on'] = values['spent_on'].isoformat()
    if 'amount' in values:
        values['amount'] = round(values['amount'], 2)
    with connect() as conn:
        old = to_dict(conn.execute('SELECT * FROM expenses WHERE id=? AND deleted_at IS NULL', (expense_id,)).fetchone())
        if not old:
            raise HTTPException(404, 'Transaction not found')
        conn.execute('UPDATE expenses SET ' + ', '.join(f'{k}=?' for k in values) + ' WHERE id=?', (*values.values(), expense_id))
        new = to_dict(conn.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone())
        _log_expense_action(conn, 'edit', expense_id, old, new)
    return new


@app.delete('/api/expenses/{expense_id}')
def delete_expense(expense_id: int):
    with connect() as conn:
        old = to_dict(conn.execute('SELECT * FROM expenses WHERE id=? AND deleted_at IS NULL', (expense_id,)).fetchone())
        if not old:
            raise HTTPException(404, 'Transaction not found')
        conn.execute('UPDATE expenses SET deleted_at = ? WHERE id = ?', (timestamp(), expense_id))
        new = to_dict(conn.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone())
        _log_expense_action(conn, 'delete', expense_id, old, new)
    return {'ok': True, 'can_undo': True}


@app.post('/api/expenses/undo')
def undo_expense():
    # Server-backed undo survives browser reload and reverses the latest edit/create/delete.
    with connect() as conn:
        row = conn.execute('SELECT * FROM expense_actions WHERE undone=0 ORDER BY id DESC LIMIT 1').fetchone()
        if row is None:
            raise HTTPException(404, 'Nothing to undo')
        before = json.loads(row['before_json']) if row['before_json'] else None
        if row['action'] == 'create':
            conn.execute('UPDATE expenses SET deleted_at=? WHERE id=?', (timestamp(), row['entry_id']))
        else:
            if before is None:
                raise HTTPException(409, 'Cannot undo this action')
            cols = ['title', 'amount', 'category', 'spent_on', 'created_at', 'entry_type', 'notes', 'deleted_at']
            conn.execute('UPDATE expenses SET ' + ', '.join(f'{col}=?' for col in cols) + ' WHERE id=?',
                tuple(before[col] for col in cols) + (row['entry_id'],))
        conn.execute('UPDATE expense_actions SET undone=1 WHERE id=?', (row['id'],))
    return {'ok': True, 'reverted': row['action']}


@app.get('/api/expenses/export')
def export_expenses(format: Literal['csv', 'xlsx', 'pdf'] = 'csv', month: str | None = None):
    if month:
        validate_month(month)
    with connect() as conn:
        rows = _finance_rows(conn, month)
    summary = _finance_summary(rows)
    period = month or 'all-time'
    safe_filename = f'LifePilot_Transactions_{period}.{format}'
    headers = ['Date', 'Type', 'Category', 'Title', 'Amount (INR)', 'Notes']
    items = [[x['spent_on'], x['entry_type'].title(), x['category'], x['title'], x['amount'], x['notes']] for x in rows]
    if format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['LifePilot - Transaction Report', period])
        writer.writerow(['Total Credit', summary['credit'], 'Total Debit', summary['debit'], 'Net Movement', summary['balance']])
        writer.writerow([])
        writer.writerow(headers)
        for item in items:
            # Prevent spreadsheet formula execution when importing CSV into Excel.
            writer.writerow(["'" + str(v) if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in item])
        data = ('\ufeff' + output.getvalue()).encode('utf-8')
        media = 'text/csv; charset=utf-8'
    elif format == 'xlsx':
        import xlsxwriter
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        summary_tab = workbook.add_worksheet('Dashboard')
        records_tab = workbook.add_worksheet('Transactions')
        title_format = workbook.add_format({'bold': True, 'font_size': 20, 'font_color': '#342568'})
        head_format = workbook.add_format({'bold': True, 'bg_color': '#ede9fe', 'font_color': '#43346c', 'border': 1, 'border_color': '#ddd6fe'})
        money_format = workbook.add_format({'num_format': '"INR "#,##0.00;[Red]("INR "#,##0.00)'})
        summary_tab.set_column('A:A', 25); summary_tab.set_column('B:B', 20)
        summary_tab.write('A1', 'LifePilot Financial Dashboard', title_format)
        summary_tab.write('A3', 'Period'); summary_tab.write('B3', period)
        for i, (label, amount) in enumerate((('Credit (money in)', summary['credit']), ('Debit (money out)', summary['debit']), ('Net movement', summary['balance']))):
            summary_tab.write(4 + i, 0, label, head_format)
            summary_tab.write_number(4 + i, 1, amount, money_format)
        summary_tab.write_row('A10', ['Spending category', 'Total debit'], head_format)
        for i, c in enumerate(summary['categories'], 10):
            summary_tab.write(i, 0, c['category']); summary_tab.write_number(i, 1, c['total'], money_format)
        records_tab.set_column('A:A', 15); records_tab.set_column('B:C', 15)
        records_tab.set_column('D:D', 34); records_tab.set_column('E:E', 19); records_tab.set_column('F:F', 52)
        records_tab.freeze_panes(1, 0); records_tab.autofilter(0, 0, max(1, len(items)), 5)
        records_tab.write_row(0, 0, headers, head_format)
        for idx, item in enumerate(items, 1):
            for col, val in enumerate(item):
                if col == 4:
                    records_tab.write_number(idx, col, float(val), money_format)
                else:
                    # Explicit string writes prevent formula injection.
                    records_tab.write_string(idx, col, str(val))
        workbook.close(); data = buffer.getvalue()
        media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
        from xml.sax.saxutils import escape
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=17*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet()
        story = [Paragraph('LifePilot | Transaction Report', styles['Title']),
                 Paragraph(f'Period: {escape(period)}', styles['Normal']), Spacer(1, 9),
                 Paragraph(f'Credit: INR {summary["credit"]:,.2f}     Debit: INR {summary["debit"]:,.2f}     Net movement: INR {summary["balance"]:,.2f}', styles['Heading3']), Spacer(1, 12)]
        cells = [['Date', 'Type', 'Category', 'Description', 'Amount INR']]
        for item in items:
            cells.append([Paragraph(escape(str(item[0])), styles['BodyText']),
                          Paragraph(escape(str(item[1])), styles['BodyText']),
                          Paragraph(escape(str(item[2])), styles['BodyText']),
                          Paragraph(escape(str(item[3])), styles['BodyText']),
                          f'{float(item[4]):,.2f}'])
        if not items:
            cells.append(['-', '-', '-', 'No transactions this period', '-'])
        table = LongTable(cells, colWidths=[26*mm, 20*mm, 32*mm, 69*mm, 30*mm], repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ede9fe')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#43346c')),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafaff')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
        story.append(table)
        document.build(story); data = buffer.getvalue()
        media = 'application/pdf'
    return StreamingResponse(io.BytesIO(data), media_type=media,
        headers={'Content-Disposition': f'attachment; filename="{safe_filename}"'})


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
        monthly = conn.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE deleted_at IS NULL AND entry_type = 'debit' AND substr(spent_on, 1, 7) = ?", (month,)).fetchone()['total']
        categories = [dict(row) for row in conn.execute('''SELECT category, ROUND(SUM(amount), 2) AS total FROM expenses
           WHERE deleted_at IS NULL AND entry_type = 'debit' AND substr(spent_on, 1, 7) = ? GROUP BY category ORDER BY total DESC''', (month,)).fetchall()]
        budget = conn.execute('SELECT amount FROM budgets WHERE month = ?', (month,)).fetchone()
        upcoming_reminders = [dict(row) for row in conn.execute('''SELECT * FROM reminders WHERE acknowledged_at IS NULL
           ORDER BY remind_at LIMIT 4''').fetchall()]
        recent_expenses = [dict(row) for row in conn.execute('''SELECT * FROM expenses WHERE deleted_at IS NULL AND substr(spent_on, 1, 7) = ?
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