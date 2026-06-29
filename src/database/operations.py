from database.connection import get_connection
from config.settings import logger
import calendar

def save_leave_application(
    employee_id: str,
    start_date: str,
    end_date: str,
    total_days: int,
    paid_days: int,
    unpaid_days: int,
    medical_days: int = 0,
    reason: str = "",
    status: str = "Approved",
) -> dict:
    """Save the approved leave application into SQLite."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO leave_applications "
            "(employee_id, start_date, end_date, total_days, paid_days, unpaid_days, medical_days, reason, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (employee_id, start_date, end_date, total_days, paid_days, unpaid_days, medical_days, reason, status),
        )
        
        if status == "Approved" and paid_days > 0:
            cursor.execute(
                "UPDATE employees SET leave_balance = leave_balance - ? WHERE employee_id = ?",
                (paid_days, employee_id),
            )
            
        if status == "Approved" and medical_days > 0:
            cursor.execute(
                "UPDATE employees SET medical_leave_balance = medical_leave_balance - ? WHERE employee_id = ?",
                (medical_days, employee_id),
            )

        conn.commit()
        msg = f"Leave approved and saved. Deducted {paid_days} paid days and {medical_days} medical days from {employee_id}."
        if status == "Pending HR Approval":
            msg = "Request sent to HR for review. Please wait for approval, you will get a notification once reviewed."

        return {
            "status": "SUCCESS",
            "message": msg,
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving leave application for {employee_id}: {str(e)}", exc_info=True)
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
            e.medical_leave_balance,
            e.max_annual_leaves,
            e.country,
            COALESCE(SUM(CASE WHEN strftime('%Y-%m', la.start_date) = strftime('%Y-%m', 'now') THEN la.total_days ELSE 0 END), 0) as leaves_taken_this_month,
            COALESCE(SUM(CASE WHEN strftime('%Y', la.start_date) = strftime('%Y', 'now') AND strftime('%m', la.start_date) <= strftime('%m', 'now') THEN la.total_days ELSE 0 END), 0) as leaves_taken_this_year,
            COALESCE(SUM(CASE WHEN strftime('%Y', la.start_date) = strftime('%Y', 'now') AND strftime('%m', la.start_date) <= strftime('%m', 'now') THEN la.paid_days ELSE 0 END), 0) as paid_leaves_taken_this_year,
            COALESCE(SUM(CASE WHEN strftime('%Y', la.start_date) = strftime('%Y', 'now') AND strftime('%m', la.start_date) <= strftime('%m', 'now') THEN la.unpaid_days ELSE 0 END), 0) as unpaid_leaves_taken_this_year
        FROM employees e
        LEFT JOIN leave_applications la ON e.employee_id = la.employee_id AND la.status = 'Approved'
        WHERE e.employee_id = ?
        GROUP BY e.employee_id
    """, (employee_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"error": "Employee not found"}
    
    leaves_taken_this_month = row[9]
    leaves_taken_this_year = row[10]
    paid_leaves_taken = row[11]
    unpaid_leaves_taken = row[12]
    
    # Get monthly breakdown for current year
    cursor.execute("""
        SELECT strftime('%m', start_date) as month, SUM(total_days)
        FROM leave_applications
        WHERE employee_id = ? 
          AND status = 'Approved' 
          AND strftime('%Y', start_date) = strftime('%Y', 'now')
        GROUP BY month
    """, (employee_id,))
    monthly_rows = cursor.fetchall()
    
    monthly_leaves = {}
    for m in range(1, 13):
        month_name = calendar.month_abbr[m]
        monthly_leaves[month_name] = 0
        
    for month_str, total in monthly_rows:
        if month_str:
            month_idx = int(month_str)
            month_name = calendar.month_abbr[month_idx]
            monthly_leaves[month_name] = total
        
    conn.close()

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "department": row[3],
        "leave_balance": row[4],
        "salary": row[5],
        "medical_leave_balance": row[6],
        "max_annual_leaves": row[7],
        "country": row[8],
        "leaves_taken_this_month": leaves_taken_this_month,
        "leaves_taken_this_year": leaves_taken_this_year,
        "paid_leaves_taken_this_year": paid_leaves_taken,
        "unpaid_leaves_taken_this_year": unpaid_leaves_taken,
        "Monthly Leaves Taken This Year:": monthly_leaves
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

def get_total_holidays_for_year(year: str) -> int:
    """Retrieve the total number of holidays defined for a specific year."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM holidays WHERE strftime('%Y', date) = ?",
        (year,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def check_leave_overlap(employee_id: str, start_date: str, end_date: str) -> bool:
    """Check if the requested dates overlap with an already approved leave."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM leave_applications
        WHERE employee_id = ?
        AND status = 'Approved'
        AND start_date <= ?
        AND end_date >= ?
        LIMIT 1
        """,
        (employee_id, end_date, start_date),
    )
    row = cursor.fetchone()
    conn.close()
    
    return row is not None

def revoke_leave(employee_id: str, target_date: str, current_date: str) -> dict:
    """Revoke an approved leave that encompasses the target date if it hasn't ended yet."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Find the leave
        cursor.execute(
            """
            SELECT rowid, paid_days, unpaid_days, end_date FROM leave_applications
            WHERE employee_id = ?
            AND status = 'Approved'
            AND start_date <= ?
            AND end_date >= ?
            LIMIT 1
            """,
            (employee_id, target_date, target_date),
        )
        row = cursor.fetchone()
        
        if not row:
            return {"status": "ERROR", "message": f"No approved leave found for {employee_id} on {target_date}."}
            
        leave_id = row[0]
        paid_days = row[1]
        unpaid_days = row[2]
        end_date = row[3]
        
        # Check if the leave is completely in the past
        if end_date < current_date:
            return {"status": "ERROR", "message": f"Cannot revoke leave ending on {end_date} because it is in the past."}
            
        # Revoke the leave
        cursor.execute(
            "UPDATE leave_applications SET status = 'Revoked' WHERE rowid = ?",
            (leave_id,)
        )
        
        # Refund the balance
        if paid_days > 0:
            cursor.execute(
                "UPDATE employees SET leave_balance = leave_balance + ? WHERE employee_id = ?",
                (paid_days, employee_id)
            )
            
        conn.commit()
        return {"status": "SUCCESS", "message": f"Leave revoked successfully. Refunded {paid_days} paid days to your balance. Unpaid leaves regained: {unpaid_days}."}
    except Exception as e:
        conn.rollback()
        logger.error(f"Error revoking leave for {employee_id}: {str(e)}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}
    finally:
        conn.close()

def process_hr_approval(hr_emp_id: str, target_emp_id: str, action: str) -> dict:
    """Process HR approval or rejection of a pending leave request."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Verify HR
    cursor.execute("SELECT role FROM hr_admins WHERE hr_id = ?", (hr_emp_id,))
    hr_row = cursor.fetchone()
    if not hr_row:
        conn.close()
        return {"error": f"{hr_emp_id} is not an authorized HR administrator."}
        
    # Get target employee email
    cursor.execute("SELECT email, name FROM employees WHERE employee_id = ?", (target_emp_id,))
    emp_row = cursor.fetchone()
    if not emp_row:
        conn.close()
        return {"error": f"Target employee {target_emp_id} not found."}
    
    target_email = emp_row[0]
    target_name = emp_row[1]
    
    # Check pending leave
    cursor.execute("SELECT id, paid_days, medical_days FROM leave_applications WHERE employee_id = ? AND status = 'Pending HR Approval'", (target_emp_id,))
    leave_row = cursor.fetchone()
    if not leave_row:
        conn.close()
        return {"error": f"No pending leave requests found for {target_emp_id}."}
        
    leave_id = leave_row[0]
    paid_days = leave_row[1]
    medical_days = leave_row[2]
    new_status = 'Approved' if action.lower() == 'approve' else 'Rejected'
    
    cursor.execute("UPDATE leave_applications SET status = ? WHERE id = ?", (new_status, leave_id))
    
    if new_status == 'Approved':
        if paid_days > 0:
            cursor.execute("UPDATE employees SET leave_balance = leave_balance - ? WHERE employee_id = ?", (paid_days, target_emp_id))
        if medical_days > 0:
            cursor.execute("UPDATE employees SET medical_leave_balance = medical_leave_balance - ? WHERE employee_id = ?", (medical_days, target_emp_id))
            
    conn.commit()
    conn.close()
    
    return {
        "success": True, 
        "email": target_email,
        "name": target_name,
        "new_status": new_status
    }
