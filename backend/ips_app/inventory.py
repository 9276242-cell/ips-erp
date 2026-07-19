from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ips_app.db import get_db_connection
from ips_app.auth import get_current_user, RoleChecker
from ips_app.accounting import log_audit

router = APIRouter(prefix="/inventory", tags=["Inventory & POS"])

class ItemCreateSchema(BaseModel):
    sku: str
    name: str
    category: str  # Book, Report, CD, Journal
    cost_price: float
    sale_price: float
    low_stock_threshold: Optional[int] = 5
    is_expensed_asset: Optional[bool] = False

class SaleLineSchema(BaseModel):
    item_id: int
    quantity: int
    price: float

class POSSaleSchema(BaseModel):
    customer_name: Optional[str] = "Walk-in Customer"
    payment_method: str  # Cash, Credit
    lines: List[SaleLineSchema]

# 1. Fetch Item Catalog
@router.get("/items")
def get_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items")
    items = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return items

# 2. Add Item Master record
@router.post("/items", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def create_item(data: ItemCreateSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if column is_expensed_asset exists, SQLite may not have it yet if created before
        cursor.execute("PRAGMA table_info(items)")
        cols = [c[1] for c in cursor.fetchall()]
        if "is_expensed_asset" not in cols:
            cursor.execute("ALTER TABLE items ADD COLUMN is_expensed_asset INTEGER DEFAULT 0")
            
        cursor.execute(
            "INSERT INTO items (sku, name, category, cost_price, sale_price, low_stock_threshold, is_expensed_asset) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data.sku, data.name, data.category, data.cost_price, data.sale_price, data.low_stock_threshold, 1 if data.is_expensed_asset else 0)
        )
        item_id = cursor.lastrowid
        log_audit(cursor, "items", "INSERT", item_id, user["sub"], f"Added inventory item {data.sku} - {data.name}")
        conn.commit()
        return {"success": True, "id": item_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 3. Restock Item (GRN - Goods Receipt Note)
class RestockSchema(BaseModel):
    item_id: int
    quantity: int
    unit_cost: float
    vendor_id: Optional[int] = None

@router.post("/restock", dependencies=[Depends(RoleChecker(["Admin", "Accountant"]))])
def restock_item(data: RestockSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get Item Info
        cursor.execute("SELECT * FROM items WHERE id = ?", (data.item_id,))
        item = cursor.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Log to Stock Ledger (IN_PURCHASE)
        cursor.execute(
            "INSERT INTO stock_ledger (item_id, type, date, quantity, unit_cost) VALUES (?, 'IN_PURCHASE', ?, ?, ?)",
            (data.item_id, date_str, data.quantity, data.unit_cost)
        )
        ledger_id = cursor.lastrowid
        
        # Update current stock quantity
        cursor.execute("UPDATE items SET stock_quantity = stock_quantity + ? WHERE id = ?", (data.quantity, data.item_id))
        
        # Create Accounting Voucher (Purchase Entry)
        # Debit: Inventory Asset / Printing Publications Cost
        # Credit: Accounts Payable (Creditors) or Cash
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = 'Purchase'")
        count = cursor.fetchone()[0] + 1
        voucher_no = f"JV-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, 'Purchase', ?, ?, 'Approved')",
            (voucher_no, date_str, f"GRN Restock: {item['name']} x {data.quantity}", user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        # Account mappings
        # Debit Printing/Publications Expense (Account ID 19 / Code 5004) if expensed, or Assets (Code 1000)
        # For this turn-key, we debit Printing/Publishing Cost (ID 19 / Code 5004) and credit Payables (ID 8 / Code 2001) or Cash (ID 2 / Code 1001)
        debit_acc_id = 19  # Printing & Publications Expense
        credit_acc_id = 8 if data.vendor_id else 2  # Accounts Payable or Cash at Hand
        
        total_amount = data.quantity * data.unit_cost
        
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, ?, 0.0, ?)",
            (voucher_id, debit_acc_id, total_amount, f"Purchase of {item['name']} stock")
        )
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, 0.0, ?, ?)",
            (voucher_id, credit_acc_id, total_amount, f"Payment/Liability for {item['name']} restock")
        )
        
        # Update COA balances
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (total_amount, debit_acc_id))
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (total_amount, credit_acc_id))
        
        log_audit(cursor, "stock_ledger", "INSERT", ledger_id, user["sub"], f"Restocked {item['name']} x {data.quantity}")
        conn.commit()
        return {"success": True, "voucher_no": voucher_no}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 4. POS Invoice Sale (FIFO Stock Reduction + Scrap Sale Logic)
@router.post("/pos-sale", dependencies=[Depends(RoleChecker(["Admin", "Accountant", "Salesperson", "Visitor"]))])
def pos_sale(data: POSSaleSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check column existence just in case
    cursor.execute("PRAGMA table_info(items)")
    cols = [c[1] for c in cursor.fetchall()]
    if "is_expensed_asset" not in cols:
        cursor.execute("ALTER TABLE items ADD COLUMN is_expensed_asset INTEGER DEFAULT 0")

    try:
        total_sale_value = 0.0
        details_list = []
        date_str = datetime.now().strftime("%Y-%m-%d")

        for line in data.lines:
            cursor.execute("SELECT * FROM items WHERE id = ?", (line.item_id,))
            item = cursor.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail=f"Item ID {line.item_id} not found")
                
            if item["stock_quantity"] < line.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {item['name']}. Available: {item['stock_quantity']}")
                
            total_sale_value += line.quantity * line.price
            
            # FIFO Stock Reduction Logic
            qty_remaining = line.quantity
            cursor.execute(
                "SELECT * FROM stock_ledger WHERE item_id = ? AND type = 'IN_PURCHASE' AND quantity > 0 ORDER BY date ASC, id ASC",
                (line.item_id,)
            )
            batches = cursor.fetchall()
            
            for batch in batches:
                if qty_remaining <= 0:
                    break
                batch_qty = batch["quantity"]
                batch_id = batch["id"]
                
                if batch_qty >= qty_remaining:
                    # Deduct from this batch
                    cursor.execute(
                        "UPDATE stock_ledger SET quantity = quantity - ? WHERE id = ?",
                        (qty_remaining, batch_id)
                    )
                    qty_remaining = 0
                else:
                    # Drain this batch
                    cursor.execute(
                        "UPDATE stock_ledger SET quantity = 0 WHERE id = ?",
                        (batch_id,)
                    )
                    qty_remaining -= batch_qty
            
            # Log OUT_SALE in stock ledger
            cursor.execute(
                "INSERT INTO stock_ledger (item_id, type, date, quantity, unit_cost) VALUES (?, 'OUT_SALE', ?, ?, ?)",
                (line.item_id, date_str, line.quantity, item["cost_price"])
            )
            
            # Update current item stock quantity
            cursor.execute(
                "UPDATE items SET stock_quantity = stock_quantity - ? WHERE id = ?",
                (line.quantity, line.item_id)
            )
            
            # Label transaction line
            expensed_tag = " [Expensed Asset / Scrap Sale]" if ("is_expensed_asset" in item.keys() and item["is_expensed_asset"]) else ""
            details_list.append(f"{item['name']} x {line.quantity}{expensed_tag}")

        # Post Accounting Voucher
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = 'Sales'")
        count = cursor.fetchone()[0] + 1
        voucher_no = f"SV-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, 'Sales', ?, ?, 'Approved')",
            (voucher_no, date_str, f"POS Sale: {', '.join(details_list)}", user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        # Debits and Credits
        # Debit: Cash at Hand (ID 2 / Code 1001) or Accounts Receivable (ID 4 / Code 1003)
        debit_acc_id = 2 if data.payment_method == "Cash" else 4
        # Credit: Book & Publications Sales (ID 14 / Code 4003)
        credit_acc_id = 14
        
        # Post double-entry lines
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, ?, 0.0, ?)",
            (voucher_id, debit_acc_id, total_sale_value, f"POS payment received ({data.payment_method})")
        )
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, 0.0, ?, ?)",
            (voucher_id, credit_acc_id, total_sale_value, f"Sales Income: {', '.join(details_list)}")
        )
        
        # Update COA balances
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (total_sale_value, debit_acc_id))
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (total_sale_value, credit_acc_id))
        
        log_audit(cursor, "vouchers", "INSERT", voucher_id, user["sub"], f"Completed POS Sale {voucher_no}")
        conn.commit()
        return {"success": True, "voucher_no": voucher_no, "total": total_sale_value}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
