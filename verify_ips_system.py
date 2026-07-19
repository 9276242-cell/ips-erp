import os
import sys
import sqlite3
from datetime import datetime, timedelta

# Ensure backend folder is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from ips_app.db import init_db, get_db_connection
from ips_app.accounting import create_voucher, VoucherCreateSchema, VoucherLineSchema
from ips_app.inventory import pos_sale, POSSaleSchema, SaleLineSchema
from ips_app.library import issue_book, IssueBookSchema, return_book
from ips_app.payroll import process_payroll, PayrunSchema
from ips_app.assets import run_depreciation, create_asset, AssetCreateSchema

def run_tests():
    print("Initializing fresh test database...")
    init_db()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Define User context for audit logs
    user_context = {"sub": "test_operator", "role": "Admin"}

    # =========================================================================
    # Test Case 1: Donation Entry (Double entry validation)
    # =========================================================================
    print("\n--- Test Case 1: Donation Entry ---")
    # Fetch account IDs: Cash (Code 1001), General Donations (Code 4001)
    cursor.execute("SELECT id, balance FROM accounts WHERE code = '1001'")
    cash_acc = cursor.fetchone()
    cursor.execute("SELECT id, balance FROM accounts WHERE code = '4001'")
    donation_acc = cursor.fetchone()
    
    # We will receive a receipt voucher (RV) of 50,000 PKR
    voucher_data = VoucherCreateSchema(
        date=datetime.now().strftime("%Y-%m-%d"),
        type="Receipt",
        narration="Test General Donation",
        lines=[
            VoucherLineSchema(account_id=cash_acc["id"], debit=50000.0, credit=0.0, description="General Donation received"),
            VoucherLineSchema(account_id=donation_acc["id"], debit=0.0, credit=50000.0, description="General Donation revenue")
        ]
    )
    
    res = create_voucher(voucher_data, user=user_context)
    print("Voucher posted:", res["voucher_no"])
    
    # Verify account balances
    cursor.execute("SELECT balance FROM accounts WHERE code = '1001'")
    new_cash = cursor.fetchone()["balance"]
    cursor.execute("SELECT balance FROM accounts WHERE code = '4001'")
    new_don = cursor.fetchone()["balance"]
    
    print(f"Cash Balance: {cash_acc['balance']} -> {new_cash} PKR (change: {new_cash - cash_acc['balance']})")
    print(f"Donation Account Balance: {donation_acc['balance']} -> {new_don} PKR (change: {new_don - donation_acc['balance']})")
    
    assert abs(new_cash - cash_acc["balance"] - 50000.0) < 0.001, "Cash balance mismatch!"
    assert abs(new_don - donation_acc["balance"] - (-50000.0)) < 0.001, "Donation credit balance mismatch!"
    print("Test Case 1: SUCCESS [OK]")

    # =========================================================================
    # Test Case 2: Book POS Sale (FIFO Inventory stock depletion)
    # =========================================================================
    print("\n--- Test Case 2: POS Book Sale (FIFO) ---")
    # Check item 1 (CPEC Report) quantity and prices
    cursor.execute("SELECT id, name, stock_quantity, sale_price FROM items WHERE sku = 'PUB-CPEC'")
    item = cursor.fetchone()
    print(f"Current Stock of {item['name']}: {item['stock_quantity']} units @ {item['sale_price']} PKR")
    
    # Sale of 2 units
    sale_data = POSSaleSchema(
        customer_name="Walk-in Scholar",
        payment_method="Cash",
        lines=[
            SaleLineSchema(item_id=item["id"], quantity=2, price=item["sale_price"])
        ]
    )
    
    res = pos_sale(sale_data, user=user_context)
    print("POS Invoice Sale posted:", res["voucher_no"], "Total Amount:", res["total"])
    
    # Verify stock reduction
    cursor.execute("SELECT stock_quantity FROM items WHERE id = ?", (item["id"],))
    new_qty = cursor.fetchone()["stock_quantity"]
    print(f"New Stock Quantity: {item['stock_quantity']} -> {new_qty} (change: {new_qty - item['stock_quantity']})")
    
    assert item["stock_quantity"] - new_qty == 2, "Stock deduction failed!"
    print("Test Case 2: SUCCESS [OK]")

    # =========================================================================
    # Test Case 3: Book Issue (Library Module)
    # =========================================================================
    print("\n--- Test Case 3: Book Issue & Return ---")
    # Fetch first available book (ACC-101)
    cursor.execute("SELECT id, title, status FROM books WHERE accession_no = 'ACC-101'")
    book = cursor.fetchone()
    print(f"Book '{book['title']}' Status: {book['status']}")
    
    # Issue to member ID 1
    issue_data = IssueBookSchema(book_id=book["id"], member_id=1, duration_days=14)
    res = issue_book(issue_data, user=user_context)
    print(f"Book issued. Issue ID: {res['issue_id']}, Due Date: {res['due_date']}")
    
    # Verify Book Status is Borrowed
    cursor.execute("SELECT status FROM books WHERE id = ?", (book["id"],))
    borrowed_status = cursor.fetchone()["status"]
    print("New Book Status:", borrowed_status)
    assert borrowed_status == "Borrowed", "Book status did not update to Borrowed!"
    
    # Return book
    res_return = return_book(res["issue_id"], user=user_context)
    print(f"Book returned. Overdue fine: {res_return['fine_amount']} PKR")
    
    # Verify Book Status is Available again
    cursor.execute("SELECT status FROM books WHERE id = ?", (book["id"],))
    returned_status = cursor.fetchone()["status"]
    print("Returned Book Status:", returned_status)
    assert returned_status == "Available", "Book status did not revert to Available!"
    print("Test Case 3: SUCCESS [OK]")

    # =========================================================================
    # Test Case 4: Salary Payment (Payroll)
    # =========================================================================
    print("\n--- Test Case 4: Salary Payroll Run ---")
    # Salaries Expense (5001) and Cash (1001)
    cursor.execute("SELECT balance FROM accounts WHERE code = '1001'")
    cash_bal = cursor.fetchone()["balance"]
    cursor.execute("SELECT balance FROM accounts WHERE code = '5001'")
    salary_bal = cursor.fetchone()["balance"]
    
    pay_data = PayrunSchema(
        staff_name="Zubair Ansari",
        month_year="July 2026",
        basic_salary=45000.0,
        allowance=5000.0,
        deductions=2000.0
    )
    # Net salary = 45000 + 5000 - 2000 = 48,000 PKR
    res = process_payroll(pay_data, user=user_context)
    print("Payroll payment posted:", res["voucher_no"], "Net Salary Paid:", res["net_salary"])
    
    cursor.execute("SELECT balance FROM accounts WHERE code = '1001'")
    new_cash = cursor.fetchone()["balance"]
    cursor.execute("SELECT balance FROM accounts WHERE code = '5001'")
    new_sal = cursor.fetchone()["balance"]
    
    print(f"Cash Balance: {cash_bal} -> {new_cash} PKR (change: {new_cash - cash_bal})")
    print(f"Salary Expense Balance: {salary_bal} -> {new_sal} PKR (change: {new_sal - salary_bal})")
    
    assert abs(new_cash - cash_bal - (-48000.0)) < 0.001, "Cash balance mismatch after payroll!"
    assert abs(new_sal - salary_bal - 48000.0) < 0.001, "Salary expense mismatch after payroll!"
    print("Test Case 4: SUCCESS [OK]")

    # =========================================================================
    # Test Case 5: Asset Depreciation
    # =========================================================================
    print("\n--- Test Case 5: Fixed Asset depreciation ---")
    # Fetch Fixed Asset Account (1005) and Depr Expense Account (5002)
    cursor.execute("SELECT balance FROM accounts WHERE code = '1005'")
    asset_bal = cursor.fetchone()["balance"]
    cursor.execute("SELECT balance FROM accounts WHERE code = '5002'")
    depr_bal = cursor.fetchone()["balance"]
    
    # Capitalize a new asset: Cost 100,000, 10% rate, StraightLine
    asset_data = AssetCreateSchema(
        name="Conference LED Screen",
        category="IT Hardware",
        purchase_date="2026-01-01",
        cost=100000.0,
        depreciation_rate=10.0
    )
    res_capital = create_asset(asset_data, user=user_context)
    print("Asset capitalized. ID:", res_capital["id"], "JV:", res_capital["voucher_no"])
    
    # Run depreciation
    res_depr = run_depreciation(user=user_context)
    print("Depreciation run completed. JV:", res_depr["voucher_no"], "Total charge:", res_depr["total_depreciation"])
    
    cursor.execute("SELECT balance FROM accounts WHERE code = '1005'")
    new_asset_bal = cursor.fetchone()["balance"]
    cursor.execute("SELECT balance FROM accounts WHERE code = '5002'")
    new_depr_bal = cursor.fetchone()["balance"]
    
    # Calculated depreciation:
    # Asset 1 (seedeed): Cost 250k @ 20% = 50,000 PKR
    # Asset 2 (seeded): Cost 120k @ 10% = 12,000 PKR
    # Asset 3 (new): Cost 100k @ 10% = 10,000 PKR
    # Total annual depreciation = 72,000 PKR
    print(f"Fixed Assets Ledger Balance: {asset_bal} -> {new_asset_bal} PKR (change: {new_asset_bal - asset_bal})")
    print(f"Depreciation Expense Balance: {depr_bal} -> {new_depr_bal} PKR (change: {new_depr_bal - depr_bal})")
    
    # Net change should be: capitalized +100,000 and depreciated -72,000 = +28,000 PKR
    assert abs(new_asset_bal - asset_bal - 28000.0) < 0.001, "Fixed Asset ledger balance mismatch!"
    assert abs(new_depr_bal - depr_bal - 72000.0) < 0.001, "Depreciation expense ledger balance mismatch!"
    print("Test Case 5: SUCCESS [OK]")

    conn.close()
    print("\nALL 5 MANDATORY TEST CASES COMPLETED SUCCESSFULLY! [OK]")

if __name__ == "__main__":
    run_tests()
