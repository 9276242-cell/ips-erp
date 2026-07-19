from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ips_app.db import get_db_connection
from ips_app.auth import get_current_user, RoleChecker
from ips_app.accounting import log_audit

router = APIRouter(prefix="/payroll", tags=["HR & Payroll"])

class PayrunSchema(BaseModel):
    staff_name: str
    month_year: str  # e.g., "July 2026"
    basic_salary: float
    allowance: Optional[float] = 0.0
    deductions: Optional[float] = 0.0

# 1. Fetch Payroll History
@router.get("/")
def get_payroll():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payroll ORDER BY id DESC")
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return records

# 2. Process Staff Salary (Double entry payment voucher generated)
@router.post("/process", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def process_payroll(data: PayrunSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        net_salary = data.basic_salary + data.allowance - data.deductions
        if net_salary <= 0:
            raise HTTPException(status_code=400, detail="Net salary must be greater than 0")

        # Save payroll log
        cursor.execute(
            "INSERT INTO payroll (staff_name, month_year, basic_salary, allowance, deductions, net_salary, status) VALUES (?, ?, ?, ?, ?, ?, 'Paid')",
            (data.staff_name, data.month_year, data.basic_salary, data.allowance, data.deductions, net_salary)
        )
        payroll_id = cursor.lastrowid
        
        # Create Accounting Voucher (Payment Entry)
        # Debit: Staff Salaries Expense (ID 17 / Code 5001)
        # Credit: Cash at Hand (ID 2 / Code 1001)
        date_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = 'Payment'")
        count = cursor.fetchone()[0] + 1
        voucher_no = f"PV-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, 'Payment', ?, ?, 'Approved')",
            (voucher_no, date_str, f"Salary Payout: {data.staff_name} - Month: {data.month_year}", user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        debit_acc_id = 17  # Staff Salaries Expense
        credit_acc_id = 2  # Cash at Hand
        
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, ?, 0.0, ?)",
            (voucher_id, debit_acc_id, net_salary, f"Net salary payment to {data.staff_name} ({data.month_year})")
        )
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, 0.0, ?, ?)",
            (voucher_id, credit_acc_id, net_salary, f"Salary disbursement to {data.staff_name}")
        )
        
        # Update COA balances
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (net_salary, debit_acc_id))
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (net_salary, credit_acc_id))
        
        log_audit(cursor, "payroll", "INSERT", payroll_id, user["sub"], f"Paid salary to {data.staff_name} for {data.month_year}")
        conn.commit()
        return {"success": True, "voucher_no": voucher_no, "net_salary": net_salary}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
