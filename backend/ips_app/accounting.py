from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ips_app.db import get_db_connection
from ips_app.auth import get_current_user, RoleChecker

router = APIRouter(prefix="/accounting", tags=["Accounting"])

class VoucherLineSchema(BaseModel):
    account_id: int
    debit: float
    credit: float
    description: Optional[str] = ""
    donor_id: Optional[int] = None

class VoucherCreateSchema(BaseModel):
    date: str
    type: str  # Payment, Receipt, Journal, Contra, Sales, Purchase
    narration: Optional[str] = ""
    lines: List[VoucherLineSchema]

def log_audit(cursor, table_name, action, record_id, changed_by, details):
    cursor.execute(
        "INSERT INTO audit_trail (table_name, action, record_id, changed_by, timestamp, details) VALUES (?, ?, ?, ?, ?, ?)",
        (table_name, action, record_id, changed_by, datetime.now().isoformat(), details)
    )

# 1. Fetch Chart of Accounts
@router.get("/accounts")
def get_accounts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY code ASC")
    accounts = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return accounts

# 2. Add New Account
class AccountCreate(BaseModel):
    code: str
    name: str
    parent_id: Optional[int] = None
    type: str
    fund_type: Optional[str] = "None"

@router.post("/accounts", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def create_account(data: AccountCreate, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accounts (code, name, parent_id, type, fund_type) VALUES (?, ?, ?, ?, ?)",
            (data.code, data.name, data.parent_id, data.type, data.fund_type)
        )
        acc_id = cursor.lastrowid
        log_audit(cursor, "accounts", "INSERT", acc_id, user["sub"], f"Created account {data.code} - {data.name}")
        conn.commit()
        return {"success": True, "id": acc_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 3. Create Voucher (Double-entry guard enforced)
@router.post("/vouchers", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def create_voucher(data: VoucherCreateSchema, user: dict = Depends(get_current_user)):
    # 1. Enforce Double-entry validation
    total_debit = sum(line.debit for line in data.lines)
    total_credit = sum(line.credit for line in data.lines)
    
    if abs(total_debit - total_credit) > 0.001:
        raise HTTPException(status_code=400, detail=f"Double-entry violation: Total debits ({total_debit}) must equal total credits ({total_credit})")
    
    if len(data.lines) < 2:
        raise HTTPException(status_code=400, detail="Voucher must contain at least two transaction lines")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate voucher number automatically if needed
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = ?", (data.type,))
        count = cursor.fetchone()[0] + 1
        prefix = {"Payment": "PV", "Receipt": "RV", "Journal": "JV", "Contra": "CV", "Sales": "SV", "Purchase": "JV"}.get(data.type, "VO")
        voucher_no = f"{prefix}-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, ?, ?, ?, 'Approved')",
            (voucher_no, data.date, data.type, data.narration, user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        # Post lines and update Chart of Account balances
        for line in data.lines:
            cursor.execute(
                "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description, donor_id) VALUES (?, ?, ?, ?, ?, ?)",
                (voucher_id, line.account_id, line.debit, line.credit, line.description, line.donor_id)
            )
            # Update running balance
            balance_change = line.debit - line.credit
            cursor.execute(
                "UPDATE accounts SET balance = balance + ? WHERE id = ?",
                (balance_change, line.account_id)
            )
            
        log_audit(cursor, "vouchers", "INSERT", voucher_id, user["sub"], f"Posted voucher {voucher_no}")
        conn.commit()
        return {"success": True, "voucher_no": voucher_no}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 4. Fetch Vouchers List
@router.get("/vouchers")
def get_vouchers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, 
               (SELECT sum(debit) FROM voucher_lines WHERE voucher_id = v.id) as amount
        FROM vouchers v ORDER BY v.date DESC, v.id DESC
    """)
    vouchers = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return vouchers

# 5. Voucher Detail View
@router.get("/vouchers/{voucher_id}")
def get_voucher_detail(voucher_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vouchers WHERE id = ?", (voucher_id,))
    voucher = cursor.fetchone()
    if not voucher:
        conn.close()
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    cursor.execute("""
        SELECT vl.*, a.code as account_code, a.name as account_name, d.name as donor_name 
        FROM voucher_lines vl
        JOIN accounts a ON vl.account_id = a.id
        LEFT JOIN donors d ON vl.donor_id = d.id
        WHERE vl.voucher_id = ?
    """, (voucher_id,))
    lines = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return {
        "voucher": dict(voucher),
        "lines": lines
    }

# 6. Trial Balance Report
@router.get("/reports/trial-balance")
def get_trial_balance():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, name, type, balance
        FROM accounts
        WHERE balance != 0
        ORDER BY code ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    total_debit = 0.0
    total_credit = 0.0
    records = []
    
    for row in rows:
        bal = row["balance"]
        # Normal debit balance for Asset & Expense, credit balance for Liability, Equity, Income, Fund
        is_debit_nature = row["type"] in ("Asset", "Expense")
        debit = bal if is_debit_nature else 0.0
        credit = -bal if not is_debit_nature else 0.0
        
        # Keep positive representation
        if debit < 0:
            credit = abs(debit)
            debit = 0.0
        if credit < 0:
            debit = abs(credit)
            credit = 0.0
            
        total_debit += debit
        total_credit += credit
        
        records.append({
            "code": row["code"],
            "name": row["name"],
            "type": row["type"],
            "debit": debit,
            "credit": credit
        })
        
    return {
        "records": records,
        "total_debit": total_debit,
        "total_credit": total_credit
    }

# 7. Income & Expense Statement (NGO Fund Accounting Mode)
@router.get("/reports/income-expense")
def get_income_expense(fund_type: Optional[str] = "All"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Base query for transaction lines belonging to Income (4xxx) or Expense (5xxx)
    query = """
        SELECT a.code, a.name, a.type, a.fund_type, vl.debit, vl.credit
        FROM voucher_lines vl
        JOIN accounts a ON vl.account_id = a.id
        WHERE a.type IN ('Income', 'Expense')
    """
    params = []
    if fund_type != "All":
        query += " AND a.fund_type = ?"
        params.append(fund_type)
        
    cursor.execute(query, params)
    lines = cursor.fetchall()
    conn.close()
    
    incomes = {}
    expenses = {}
    
    for line in lines:
        amount = line["credit"] - line["debit"] if line["type"] == "Income" else line["debit"] - line["credit"]
        target = incomes if line["type"] == "Income" else expenses
        code = line["code"]
        if code not in target:
            target[code] = {"name": line["name"], "amount": 0.0, "fund_type": line["fund_type"]}
        target[code]["amount"] += amount

    total_income = sum(i["amount"] for i in incomes.values())
    total_expense = sum(e["amount"] for e in expenses.values())
    
    return {
        "incomes": [{"code": c, **v} for c, v in incomes.items()],
        "expenses": [{"code": c, **v} for c, v in expenses.items()],
        "total_income": total_income,
        "total_expense": total_expense,
        "surplus": total_income - total_expense
    }

# 8. Balance Sheet
@router.get("/reports/balance-sheet")
def get_balance_sheet():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, name, type, balance
        FROM accounts
        WHERE type IN ('Asset', 'Liability', 'Equity', 'Fund')
        ORDER BY code ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    assets = []
    liabilities = []
    equity_funds = []
    
    total_assets = 0.0
    total_liabilities = 0.0
    total_equity_funds = 0.0
    
    for row in rows:
        bal = row["balance"]
        if row["type"] == "Asset":
            assets.append({"code": row["code"], "name": row["name"], "amount": bal})
            total_assets += bal
        elif row["type"] == "Liability":
            liabilities.append({"code": row["code"], "name": row["name"], "amount": -bal})
            total_liabilities += -bal
        else: # Equity or Fund
            equity_funds.append({"code": row["code"], "name": row["name"], "amount": -bal})
            total_equity_funds += -bal
            
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity_funds": equity_funds,
        "total_assets": total_assets,
        "total_liabilities_and_funds": total_liabilities + total_equity_funds
    }

# 9. Donors Ledger & Receipts Tracker
@router.get("/donors")
def get_donors():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors")
    donors = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return donors

@router.post("/donors", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def create_donor(name: str, email: Optional[str] = "", phone: Optional[str] = "", tax_id: Optional[str] = "", user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO donors (name, email, phone, tax_id) VALUES (?, ?, ?, ?)", (name, email, phone, tax_id))
    donor_id = cursor.lastrowid
    log_audit(cursor, "donors", "INSERT", donor_id, user["sub"], f"Registered donor {name}")
    conn.commit()
    conn.close()
    return {"success": True, "id": donor_id}

# 10. Fetch Audit Logs
@router.get("/reports/audit")
def get_audit_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_trail ORDER BY id DESC LIMIT 100")
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs

# 11. General Ledger / Statement of Account (SOA) Report
@router.get("/reports/general-ledger")
def get_general_ledger(account_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch account info
    cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    account = cursor.fetchone()
    if not account:
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")
        
    is_debit_nature = account["type"] in ("Asset", "Expense")
    
    # Calculate opening balance by summing all prior transactions
    opening_balance = 0.0
    if start_date:
        cursor.execute("""
            SELECT sum(vl.debit - vl.credit) as prior_balance
            FROM voucher_lines vl
            JOIN vouchers v ON vl.voucher_id = v.id
            WHERE vl.account_id = ? AND v.date < ?
        """, (account_id, start_date))
        prior_val = cursor.fetchone()["prior_balance"] or 0.0
        opening_balance = prior_val if is_debit_nature else -prior_val
    else:
        # Default opening balance starts at 0, or we could fetch seeded defaults
        pass
        
    # Query voucher lines within range
    query = """
        SELECT vl.id, v.voucher_no, v.date, v.type as voucher_type, v.narration as voucher_narration, 
               vl.debit, vl.credit, vl.description as line_description, v.created_by
        FROM voucher_lines vl
        JOIN vouchers v ON vl.voucher_id = v.id
        WHERE vl.account_id = ?
    """
    params = [account_id]
    if start_date:
        query += " AND v.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND v.date <= ?"
        params.append(end_date)
        
    query += " ORDER BY v.date ASC, v.id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Build ledger lines with running balance
    ledger_lines = []
    running_balance = opening_balance
    
    for row in rows:
        line_net = row["debit"] - row["credit"]
        net_impact = line_net if is_debit_nature else -line_net
        running_balance += net_impact
        
        ledger_lines.append({
            "id": row["id"],
            "voucher_no": row["voucher_no"],
            "date": row["date"],
            "voucher_type": row["voucher_type"],
            "voucher_narration": row["voucher_narration"],
            "debit": row["debit"],
            "credit": row["credit"],
            "description": row["line_description"] or row["voucher_narration"],
            "created_by": row["created_by"],
            "running_balance": running_balance
        })
        
    return {
        "account": dict(account),
        "opening_balance": opening_balance,
        "lines": ledger_lines,
        "closing_balance": running_balance
    }
