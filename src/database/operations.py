from database.connection import get_connection

def save_leave_application(
    employee_id: str,
    start_date: str,
    end_date: str,
    total_days: int,
    paid_days: int,
    unpaid_days: int,
    reason: str,
) -> dict:
    """Save the approved leave application into SQLite."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO leave_applications "
            "(employee_id, start_date, end_date, total_days, paid_days, unpaid_days, reason, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (employee_id, start_date, end_date, total_days, paid_days, unpaid_days, reason, "Approved"),
        )
        cursor.execute(
            "UPDATE employees SET leave_balance = leave_balance - ? WHERE employee_id = ?",
            (paid_days, employee_id),
        )

        conn.commit()
        return {
            "status": "SUCCESS",
            "message": (
                f"Leave approved and saved. Deducted {total_days} days "
                f"from {employee_id}."
            ),
        }
    except Exception as e:
        conn.rollback()
        return {"status": "ERROR", "message": str(e)}
    finally:
        conn.close()

def get_employee_details(employee_id: str) -> dict:
    """Retrieve employee details including leave balance and leaves taken this month."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            e.employee_id, 
            e.name, 
            e.email, 
            e.department, 
            e.leave_balance, 
            e.salary,
            COALESCE(SUM(CASE WHEN strftime('%Y-%m', la.start_date) = strftime('%Y-%m', 'now') THEN la.total_days ELSE 0 END), 0) as leaves_taken_this_month,
            COALESCE(SUM(CASE WHEN strftime('%Y', la.start_date) = strftime('%Y', 'now') AND strftime('%m', la.start_date) <= strftime('%m', 'now') THEN la.total_days ELSE 0 END), 0) as leaves_taken_this_year
        FROM employees e
        LEFT JOIN leave_applications la ON e.employee_id = la.employee_id AND la.status = 'Approved'
        WHERE e.employee_id = ?
        GROUP BY e.employee_id
    """, (employee_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"error": "Employee not found"}
    
    leaves_taken_this_month = row[6]
    leaves_taken_this_year = row[7]
        
    conn.close()

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "department": row[3],
        "leave_balance": row[4],
        "salary": row[5],
        "leaves_taken_this_month": leaves_taken_this_month,
        "leaves_taken_this_year": leaves_taken_this_year
    }

def get_holidays(start_date: str, end_date: str) -> list[dict]:
    """Retrieve public holidays within a specific date range, including their names."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, name FROM holidays WHERE date >= ? AND date <= ?",
        (start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()

    return [{"date": row[0], "name": row[1]} for row in rows]
