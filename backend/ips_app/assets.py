from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ips_app.db import get_db_connection
from ips_app.auth import get_current_user, RoleChecker
from ips_app.accounting import log_audit

router = APIRouter(prefix="/assets", tags=["Fixed Assets"])

class AssetCreateSchema(BaseModel):
    name: str
    category: str
    purchase_date: str
    cost: float
    depreciation_rate: float
    depreciation_method: Optional[str] = "StraightLine"

# 1. Fetch Assets Register
@router.get("/")
def get_assets():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets")
    assets = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return assets

# 2. Add Fixed Asset
@router.post("/", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def create_asset(data: AssetCreateSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO assets (name, category, purchase_date, cost, depreciation_rate, depreciation_method, current_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data.name, data.category, data.purchase_date, data.cost, data.depreciation_rate, data.depreciation_method, data.cost)
        )
        asset_id = cursor.lastrowid
        
        # Post double entry to capitalize the asset
        # Debit: Fixed Assets (ID 6 / Code 1005)
        # Credit: Cash at Hand (ID 2 / Code 1001) or Payables (ID 8 / Code 2001)
        date_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = 'Journal'")
        count = cursor.fetchone()[0] + 1
        voucher_no = f"JV-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, 'Journal', ?, ?, 'Approved')",
            (voucher_no, date_str, f"Capitalized Fixed Asset: {data.name}", user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        debit_acc_id = 6 # Fixed Assets Account
        credit_acc_id = 2 # Cash at Hand (assume cash purchase for default)
        
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, ?, 0.0, 'Capitalized asset cost')",
            (voucher_id, debit_acc_id, data.cost)
        )
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, 0.0, ?, 'Asset payment')",
            (voucher_id, credit_acc_id, data.cost)
        )
        
        # Update COA balances
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (data.cost, debit_acc_id))
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (data.cost, credit_acc_id))
        
        log_audit(cursor, "assets", "INSERT", asset_id, user["sub"], f"Registered & Capitalized Asset {data.name}")
        conn.commit()
        return {"success": True, "id": asset_id, "voucher_no": voucher_no}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 3. Post Depreciation Run (Straight Line / Reducing Balance)
@router.post("/run-depreciation", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def run_depreciation(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM assets WHERE current_value > 0")
        assets_list = cursor.fetchall()
        if not assets_list:
            raise HTTPException(status_code=400, detail="No active fixed assets to depreciate")
            
        date_str = datetime.now().strftime("%Y-%m-%d")
        total_depr_amount = 0.0
        details_list = []
        
        for asset in assets_list:
            # Straight Line: Rate applied on historical cost
            # Reducing Balance: Rate applied on current WDV (current_value)
            rate = asset["depreciation_rate"] / 100.0
            if asset["depreciation_method"] == "StraightLine":
                depr_amount = asset["cost"] * rate
            else:
                depr_amount = asset["current_value"] * rate
                
            # Cap depreciation at remaining book value
            depr_amount = min(depr_amount, asset["current_value"])
            if depr_amount <= 0:
                continue
                
            total_depr_amount += depr_amount
            new_value = asset["current_value"] - depr_amount
            
            # Update asset value
            cursor.execute("UPDATE assets SET current_value = ? WHERE id = ?", (new_value, asset["id"]))
            details_list.append(f"{asset['name']} (Depr: {depr_amount:.2f} PKR, WDV: {new_value:.2f} PKR)")
            
        if total_depr_amount <= 0:
             raise HTTPException(status_code=400, detail="No deprecation charge calculated for current values")

        # Post Depreciation Journal Entry
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = 'Journal'")
        count = cursor.fetchone()[0] + 1
        voucher_no = f"JV-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, 'Journal', ?, ?, 'Approved')",
            (voucher_no, date_str, f"Annual Depreciation Charge: {', '.join(details_list)}", user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        debit_acc_id = 18  # Depreciation Expense
        credit_acc_id = 6  # Fixed Assets Account (Code 1005)
        
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, ?, 0.0, 'Depreciation expense charge')",
            (voucher_id, debit_acc_id, total_depr_amount)
        )
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, 0.0, ?, 'Accumulated asset reduction')",
            (voucher_id, credit_acc_id, total_depr_amount)
        )
        
        # Update COA balances
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (total_depr_amount, debit_acc_id))
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (total_depr_amount, credit_acc_id))
        
        log_audit(cursor, "assets", "UPDATE", voucher_id, user["sub"], f"Executed depreciation run: {voucher_no}")
        conn.commit()
        return {"success": True, "voucher_no": voucher_no, "total_depreciation": total_depr_amount}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
