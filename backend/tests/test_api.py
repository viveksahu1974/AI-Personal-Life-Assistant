"""Run: python -m pytest -q (from backend/)."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

_test_dir = tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH'] = str(Path(_test_dir.name) / 'test.db')
from app.main import app  # noqa: E402


class LifePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        _test_dir.cleanup()

    def test_health_and_dashboard(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard?month=2026-11').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard?month=2026-99').status_code, 422)

    def test_task_crud(self):
        r = self.client.post('/api/tasks', json={'title': 'Finish assignment', 'category': 'College', 'priority': 'High'})
        self.assertEqual(r.status_code, 201, r.text)
        task_id = r.json()['id']
        self.assertEqual(self.client.patch(f'/api/tasks/{task_id}', json={'completed': True}).json()['completed'], 1)
        self.assertEqual(self.client.get('/api/tasks?status=done').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/tasks/{task_id}').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/tasks/{task_id}').status_code, 404)

    def test_reminder_crud(self):
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        r = self.client.post('/api/reminders', json={'title': 'Drink water', 'remind_at': past})
        self.assertEqual(r.status_code, 201, r.text)
        rem_id = r.json()['id']
        self.assertTrue(any(x['id'] == rem_id for x in self.client.get('/api/reminders/due').json()))
        self.client.patch(f'/api/reminders/{rem_id}/acknowledge')
        self.assertFalse(any(x['id'] == rem_id for x in self.client.get('/api/reminders/due').json()))
        self.assertEqual(self.client.delete(f'/api/reminders/{rem_id}').status_code, 200)

    def test_expense_budget_assistant(self):
        month = '2026-11'
        expense = self.client.post('/api/expenses', json={'title': 'Groceries', 'amount': 125.75, 'category': 'Food', 'spent_on': '2026-11-12'})
        self.assertEqual(expense.status_code, 201, expense.text)
        self.assertEqual(self.client.put(f'/api/budgets/{month}', json={'amount': 1000}).status_code, 200)
        d = self.client.get(f'/api/dashboard?month={month}').json()
        self.assertGreaterEqual(d['spending'], 125.75)
        self.assertEqual(d['budget'], 1000)
        self.assertEqual(self.client.post('/api/assistant', json={'message': 'Plan my day'}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/expenses/{expense.json()['id']}").status_code, 200)

    def test_validation(self):
        self.assertEqual(self.client.post('/api/tasks', json={'title': '  '}).status_code, 422)
        self.assertEqual(self.client.post('/api/reminders', json={'title': 'Test', 'remind_at': '2026-11-12T10:00:00'}).status_code, 422)
        self.assertEqual(self.client.post('/api/expenses', json={'title': 'Negative', 'amount': -5}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
