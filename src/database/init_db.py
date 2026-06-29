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
            salary INTEGER NOT NULL,
            medical_leave_balance INTEGER NOT NULL DEFAULT 10,
            max_annual_leaves INTEGER NOT NULL DEFAULT 25,
            country TEXT NOT NULL DEFAULT 'India'
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
            medical_days INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
        )
    ''')

    # Create hr_admins table
    cursor.execute('''
        CREATE TABLE hr_admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hr_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'HR Administrator'
        )
    ''')

    # Insert mock data for HR Admins
    hr_data = [
        ('HR001', 'Admin Sarah', 'sarah.admin@example.com', 'HR Director'),
        ('HR002', 'Admin Mike', 'mike.admin@example.com', 'HR Manager')
    ]
    cursor.executemany("INSERT INTO hr_admins (hr_id, name, email, role) VALUES (?, ?, ?, ?)", hr_data)

    # Insert mock data for employees
    employees_data = [
        ('EMP001', 'Alice Smith', 'alice@example.com', 'Engineering', 15, 120000, 10),
        ('EMP002', 'Bob Jones', 'bob@example.com', 'Human Resources', 20, 85000, 10),
        ('EMP003', 'Charlie Brown', 'charlie@example.com', 'Sales', 5, 95000, 10),
        ('EMP004', 'Diana Prince', 'diana@example.com', 'Marketing', 12, 105000, 10),
        ('EMP005', 'Evan Wright', 'evan@example.com', 'Finance', 8, 110000, 10)
    ]
    
    # Programmatically generate EMP006 to EMP030 with real names
    indian_names = [
        "Aarav Patel", "Anya Sharma", "Vihaan Singh", "Aditi Gupta", "Rohan Kumar", 
        "Neha Reddy", "Kabir Das", "Priya Joshi", "Dev Malhotra", "Riya Verma", 
        "Ishaan Nair", "Ananya Rao", "Karan Desai", "Meera Iyer", "Arjun Banerjee", 
        "Pooja Mehta", "Yash Chawla", "Kavya Menon", "Dhruv Bhat", "Sneha Kapoor", 
        "Aryan Pillai", "Sanya Ahuja", "Samir Gokhale", "Tara Chaudhry", "Vikram Sen"
    ]
    
    for i, name in enumerate(indian_names, start=6):
        emp_id = f"EMP{i:03d}"
        email = f"{name.split()[0].lower()}@example.com"
        dept = "Operations"
        balance = 25  # Give them their full max balance since they haven't taken leaves
        salary = 60000 + (i * 1500) # Varying mock salaries
        employees_data.append((emp_id, name, email, dept, balance, salary, 10))

    cursor.executemany("INSERT INTO employees (employee_id, name, email, department, leave_balance, salary, medical_leave_balance) VALUES (?, ?, ?, ?, ?, ?, ?)", employees_data)

    # Insert mock data for holidays (YYYY-MM-DD format) - Indian Public Holidays Only
    holidays_data = [
        ('2026-01-26', 'Republic Day'),
        ('2026-03-03', 'Holi'),
        ('2026-03-20', 'Eid ul-Fitr'),
        ('2026-05-01', 'Labour Day'),
        ('2026-08-15', 'Independence Day'),
        ('2026-10-02', 'Mahatma Gandhi Jayanti'),
        ('2026-10-19', 'Dussehra'),
        ('2026-11-08', 'Diwali'),
        ('2026-12-25', 'Christmas Day')
    ]
    cursor.executemany("INSERT INTO holidays (date, name) VALUES (?, ?)", holidays_data)

    # Insert mock leave applications for EMP001 and EMP002 in the current month to test limits
    from datetime import datetime
    current_year_month = datetime.now().strftime("%Y-%m")
    mock_leaves = [
        # EMP001 already took 3 days this month (maxed out)
        ('EMP001', f'{current_year_month}-02', f'{current_year_month}-04', 3, 3, 0, 0, 'Personal Vacation', 'Approved'),
        # EMP002 already took 2 days this month (1 day remaining before limit)
        ('EMP002', f'{current_year_month}-10', f'{current_year_month}-11', 2, 2, 0, 0, 'Family Event', 'Approved')
    ]
    cursor.executemany("INSERT INTO leave_applications (employee_id, start_date, end_date, total_days, paid_days, unpaid_days, medical_days, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", mock_leaves)

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {DB_PATH}")

if __name__ == '__main__':
    init_db()
