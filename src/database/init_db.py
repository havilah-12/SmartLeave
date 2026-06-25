import sqlite3
import sys
import os
from pathlib import Path

# Add src to python path so 'database.connection' can be resolved
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.connection import DB_PATH

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop tables if they exist for clean initialization
    cursor.execute("DROP TABLE IF EXISTS employees")
    cursor.execute("DROP TABLE IF EXISTS holidays")
    cursor.execute("DROP TABLE IF EXISTS leave_applications")

    # Create employees table
    cursor.execute('''
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            leave_balance INTEGER NOT NULL,
            salary INTEGER NOT NULL
        )
    ''')

    # Create holidays table
    cursor.execute('''
        CREATE TABLE holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')

    # Create leave_applications table
    cursor.execute('''
        CREATE TABLE leave_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            total_days INTEGER NOT NULL,
            paid_days INTEGER NOT NULL,
            unpaid_days INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
        )
    ''')

    # Insert mock data for employees
    employees_data = [
        ('EMP001', 'Alice Smith', 'alice@example.com', 'Engineering', 15, 120000),
        ('EMP002', 'Bob Jones', 'bob@example.com', 'Human Resources', 20, 85000),
        ('EMP003', 'Charlie Brown', 'charlie@example.com', 'Sales', 5, 95000),
        ('EMP004', 'Diana Prince', 'diana@example.com', 'Marketing', 12, 105000),
        ('EMP005', 'Evan Wright', 'evan@example.com', 'Finance', 8, 110000)
    ]
    
    # Programmatically generate EMP006 to EMP030
    for i in range(6, 31):
        emp_id = f"EMP{i:03d}"
        name = f"Test Employee {i}"
        email = f"employee{i}@example.com"
        dept = "Operations"
        balance = 10 + (i % 5)  # Assign varying balances between 10 and 14
        salary = 60000 + (i * 1500) # Varying mock salaries
        employees_data.append((emp_id, name, email, dept, balance, salary))

    cursor.executemany("INSERT INTO employees (employee_id, name, email, department, leave_balance, salary) VALUES (?, ?, ?, ?, ?, ?)", employees_data)

    # Insert mock data for holidays (YYYY-MM-DD format)
    holidays_data = [
        ('2026-01-01', 'New Year\'s Day'),
        ('2026-01-19', 'Martin Luther King Jr. Day (US)'),
        ('2026-01-26', 'Republic Day (India)'),
        ('2026-03-03', 'Holi (India)'),
        ('2026-05-25', 'Memorial Day (US)'),
        ('2026-07-04', 'Independence Day (US)'),
        ('2026-08-15', 'Independence Day (India)'),
        ('2026-09-07', 'Labor Day (US)'),
        ('2026-10-02', 'Mahatma Gandhi Jayanti (India)'),
        ('2026-11-08', 'Diwali (India)'),
        ('2026-11-26', 'Thanksgiving Day (US)'),
        ('2026-12-25', 'Christmas Day')
    ]
    cursor.executemany("INSERT INTO holidays (date, name) VALUES (?, ?)", holidays_data)

    # Insert mock leave applications for EMP001 and EMP002 in the current month to test limits
    from datetime import datetime
    current_year_month = datetime.now().strftime("%Y-%m")
    mock_leaves = [
        # EMP001 already took 3 days this month (maxed out)
        ('EMP001', f'{current_year_month}-02', f'{current_year_month}-04', 3, 3, 0, 'Personal Vacation', 'Approved'),
        # EMP002 already took 2 days this month (1 day remaining before limit)
        ('EMP002', f'{current_year_month}-10', f'{current_year_month}-11', 2, 2, 0, 'Family Event', 'Approved')
    ]
    cursor.executemany("INSERT INTO leave_applications (employee_id, start_date, end_date, total_days, paid_days, unpaid_days, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", mock_leaves)

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {DB_PATH}")

if __name__ == '__main__':
    init_db()
