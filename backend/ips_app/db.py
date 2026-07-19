import sqlite3
import os
import hashlib
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "ips.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT CHECK(role IN ('Admin', 'Accountant', 'Librarian', 'Salesperson')) NOT NULL,
        created_at TEXT NOT NULL
    )""")

    # 2. Chart of Accounts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        type TEXT CHECK(type IN ('Asset', 'Liability', 'Equity', 'Income', 'Expense', 'Fund')) NOT NULL,
        fund_type TEXT CHECK(fund_type IN ('Restricted', 'Unrestricted', 'None')) NOT NULL DEFAULT 'None',
        balance REAL DEFAULT 0.0,
        FOREIGN KEY (parent_id) REFERENCES accounts (id)
    )""")

    # 3. Donors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        tax_id TEXT
    )""")

    # 4. Vouchers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voucher_no TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        type TEXT CHECK(type IN ('Payment', 'Receipt', 'Journal', 'Contra', 'Sales', 'Purchase')) NOT NULL,
        narration TEXT,
        created_by TEXT,
        approved_by TEXT,
        status TEXT CHECK(status IN ('Draft', 'Approved')) DEFAULT 'Draft'
    )""")

    # 5. Voucher Lines Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voucher_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voucher_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        debit REAL DEFAULT 0.0,
        credit REAL DEFAULT 0.0,
        description TEXT,
        donor_id INTEGER,
        FOREIGN KEY (voucher_id) REFERENCES vouchers (id) ON DELETE CASCADE,
        FOREIGN KEY (account_id) REFERENCES accounts (id),
        FOREIGN KEY (donor_id) REFERENCES donors (id)
    )""")

    # 6. Items Table (Inventory)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT CHECK(category IN ('Book', 'Report', 'CD', 'Journal')) NOT NULL,
        cost_price REAL DEFAULT 0.0,
        sale_price REAL DEFAULT 0.0,
        stock_quantity INTEGER DEFAULT 0,
        low_stock_threshold INTEGER DEFAULT 5
    )""")

    # 7. Stock Ledger Table (FIFO)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        type TEXT CHECK(type IN ('IN_PURCHASE', 'OUT_SALE', 'OUT_EXPENSE', 'IN_RETURN')) NOT NULL,
        date TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_cost REAL NOT NULL,
        reference_id INTEGER,
        FOREIGN KEY (item_id) REFERENCES items (id)
    )""")

    # 8. Books Table (Library)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        accession_no TEXT UNIQUE NOT NULL,
        isbn TEXT,
        title TEXT NOT NULL,
        author TEXT,
        publisher TEXT,
        category TEXT,
        cost REAL DEFAULT 0.0,
        status TEXT CHECK(status IN ('Available', 'Borrowed', 'Reference')) DEFAULT 'Available'
    )""")

    # 9. Members Table (Library)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        member_type TEXT CHECK(member_type IN ('Staff', 'External', 'Student')) NOT NULL,
        email TEXT,
        phone TEXT,
        membership_date TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        status TEXT CHECK(status IN ('Active', 'Suspended')) DEFAULT 'Active'
    )""")

    # 10. Book Issues Table (Library)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS book_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        return_date TEXT,
        fine_amount REAL DEFAULT 0.0,
        status TEXT CHECK(status IN ('Issued', 'Returned', 'Overdue')) DEFAULT 'Issued',
        FOREIGN KEY (book_id) REFERENCES books (id),
        FOREIGN KEY (member_id) REFERENCES members (id)
    )""")

    # 11. Fixed Assets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        purchase_date TEXT NOT NULL,
        cost REAL NOT NULL,
        depreciation_rate REAL NOT NULL,
        depreciation_method TEXT CHECK(depreciation_method IN ('StraightLine', 'ReducingBalance')) DEFAULT 'StraightLine',
        current_value REAL NOT NULL
    )""")

    # 12. Payroll Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payroll (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_name TEXT NOT NULL,
        month_year TEXT NOT NULL,
        basic_salary REAL NOT NULL,
        allowance REAL DEFAULT 0.0,
        deductions REAL DEFAULT 0.0,
        net_salary REAL NOT NULL,
        status TEXT CHECK(status IN ('Draft', 'Paid')) DEFAULT 'Draft'
    )""")

    # 13. Audit Trail Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        action TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        changed_by TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        details TEXT
    )""")

    conn.commit()
    seed_data(conn)
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()

    # Seed Default Users
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
                       ("admin", pw_hash, "admin@ips.org.pk", "Admin", datetime.now().isoformat()))
        cursor.execute("INSERT INTO users (username, password_hash, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
                       ("accountant", pw_hash, "accountant@ips.org.pk", "Accountant", datetime.now().isoformat()))
        cursor.execute("INSERT INTO users (username, password_hash, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
                       ("librarian", pw_hash, "librarian@ips.org.pk", "Librarian", datetime.now().isoformat()))

    # Seed Default Chart of Accounts (NGO Style)
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        # Assets (1xxx)
        cursor.execute("INSERT INTO accounts (code, name, type, fund_type) VALUES ('1000', 'Assets', 'Asset', 'None')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('1001', 'Cash at Hand', 1, 'Asset')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('1002', 'Faisal Bank Account', 1, 'Asset')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('1003', 'Accounts Receivable (Debtors)', 1, 'Asset')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('1004', 'Library Book Assets', 1, 'Asset')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('1005', 'Fixed Assets (Computers/Furniture)', 1, 'Asset')")
        
        # Liabilities (2xxx)
        cursor.execute("INSERT INTO accounts (code, name, type) VALUES ('2000', 'Liabilities', 'Liability')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('2001', 'Accounts Payable (Creditors)', 7, 'Liability')")
        
        # Funds / Equity (3xxx)
        cursor.execute("INSERT INTO accounts (code, name, type, fund_type) VALUES ('3000', 'General Fund (Unrestricted)', 'Fund', 'Unrestricted')")
        cursor.execute("INSERT INTO accounts (code, name, type, fund_type) VALUES ('3100', 'Research Fund (Restricted)', 'Fund', 'Restricted')")
        
        # Income (4xxx)
        cursor.execute("INSERT INTO accounts (code, name, type) VALUES ('4000', 'Revenue', 'Income')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('4001', 'General Donations', 11, 'Income')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('4002', 'Zakat Fund Donations', 11, 'Income')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('4003', 'Book & Publications Sales', 11, 'Income')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('4004', 'Library Membership Fees & Fines', 11, 'Income')")
        
        # Expenses (5xxx)
        cursor.execute("INSERT INTO accounts (code, name, type) VALUES ('5000', 'Expenses', 'Expense')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('5001', 'Staff Salaries', 16, 'Expense')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('5002', 'Depreciation Expense', 16, 'Expense')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('5003', 'Office Operations & Rent', 16, 'Expense')")
        cursor.execute("INSERT INTO accounts (code, name, parent_id, type) VALUES ('5004', 'Printing & Publishing Costs', 16, 'Expense')")

    # Seed Default Donors
    cursor.execute("SELECT COUNT(*) FROM donors")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO donors (name, email, phone, tax_id) VALUES ('Ameen Mahmood', 'ameen@khanwco.net', '+92 300 1234567', 'TAX-98273-A')")
        cursor.execute("INSERT INTO donors (name, email, phone, tax_id) VALUES ('Higher Education Commission (HEC)', 'grants@hec.gov.pk', '+92 51 9040000', 'HEC-GOV-901')")
        cursor.execute("INSERT INTO donors (name, email, phone, tax_id) VALUES ('Al-Khidmat Foundation', 'donations@alkhidmat.org', '+92 42 111 503 504', 'AKF-10293')")

    # Seed Default Books (Library Module)
    cursor.execute("SELECT COUNT(*) FROM books")
    if cursor.fetchone()[0] == 0:
        books_data = [
            ("ACC-101", "978-0199407330", "Pakistan: Beyond the Crisis State", "Maleeha Lodhi", "Oxford University Press", "Pakistan Affairs", 1200.0),
            ("ACC-102", "978-0195475586", "The Struggle for Pakistan", "Ayesha Jalal", "Harvard University Press", "History", 1500.0),
            ("ACC-103", "978-0231175685", "Faith and Society in Central Asia", "IPS Scholars", "IPS Publications", "Faith & Society", 800.0),
            ("ACC-104", "978-9694481123", "Kashmir: Path to Peace", "Khalid Rahman", "IPS Publications", "International Relations", 600.0),
            ("ACC-105", "978-9694481130", "Secularism & the Islamic World", "Prof. Khurshid Ahmad", "IPS Publications", "Political Science", 950.0),
            ("ACC-106", "978-0521016629", "Islamic Finance: Principles & Practice", "M. Taqi Usmani", "Brill", "Economy", 1800.0),
            ("ACC-107", "978-9694481147", "China-Pakistan Economic Corridor (CPEC)", "IPS Task Force", "IPS Publications", "Economy", 1100.0),
            ("ACC-108", "978-0190701390", "Military and Politics in Pakistan", "Hasan Askari Rizvi", "Sang-e-Meel", "Political Science", 1300.0),
            ("ACC-109", "978-9694481154", "Afghan Peace Process & Future Roadmap", "Khalid Rahman", "IPS Publications", "International Relations", 750.0),
            ("ACC-110", "978-0190062402", "Constitutional History of Pakistan", "Hamid Khan", "Oxford University Press", "Law", 2200.0)
        ]
        for b in books_data:
            cursor.execute("INSERT INTO books (accession_no, isbn, title, author, publisher, category, cost, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'Available')", b)

    # Seed Default Members (Library Module)
    cursor.execute("SELECT COUNT(*) FROM members")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO members (name, member_type, email, phone, membership_date, expiry_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("Dr. Anis Ahmad", "External", "anis@riphah.edu.pk", "+92 321 9988776", "2026-01-01", "2027-01-01", "Active"))
        cursor.execute("INSERT INTO members (name, member_type, email, phone, membership_date, expiry_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("Prof. Khalid Rahman", "Staff", "khalid@ips.org.pk", "+92 300 8554422", "2026-01-01", "2028-01-01", "Active"))
        cursor.execute("INSERT INTO members (name, member_type, email, phone, membership_date, expiry_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("Sarah Khan", "Student", "sarah@qau.edu.pk", "+92 333 5554433", "2026-06-01", "2026-12-01", "Active"))

    # Seed Default Items (Sales/Inventory Module)
    cursor.execute("SELECT COUNT(*) FROM items")
    if cursor.fetchone()[0] == 0:
        # Link items corresponding to the books published by IPS
        cursor.execute("INSERT INTO items (sku, name, category, cost_price, sale_price, stock_quantity, low_stock_threshold) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("PUB-CPEC", "China-Pakistan Economic Corridor (CPEC) Report", "Book", 400.0, 1100.0, 15, 5))
        cursor.execute("INSERT INTO items (sku, name, category, cost_price, sale_price, stock_quantity, low_stock_threshold) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("PUB-KASHMIR", "Kashmir: Path to Peace", "Book", 200.0, 600.0, 8, 3))
        cursor.execute("INSERT INTO items (sku, name, category, cost_price, sale_price, stock_quantity, low_stock_threshold) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("PUB-SECULAR", "Secularism & the Islamic World", "Book", 300.0, 950.0, 2, 5))

        # Seed initial stock entries (FIFO Stock ledger)
        cursor.execute("INSERT INTO stock_ledger (item_id, type, date, quantity, unit_cost, reference_id) VALUES (1, 'IN_PURCHASE', '2026-07-01', 15, 400.0, 0)")
        cursor.execute("INSERT INTO stock_ledger (item_id, type, date, quantity, unit_cost, reference_id) VALUES (2, 'IN_PURCHASE', '2026-07-02', 8, 200.0, 0)")
        cursor.execute("INSERT INTO stock_ledger (item_id, type, date, quantity, unit_cost, reference_id) VALUES (3, 'IN_PURCHASE', '2026-07-03', 2, 300.0, 0)")

    # Seed Default Assets (Fixed Assets)
    cursor.execute("SELECT COUNT(*) FROM assets")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO assets (name, category, purchase_date, cost, depreciation_rate, depreciation_method, current_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("Office Computers (Dell Core i7)", "IT Hardware", "2026-01-01", 250000.0, 20.0, "StraightLine", 250000.0))
        cursor.execute("INSERT INTO assets (name, category, purchase_date, cost, depreciation_rate, depreciation_method, current_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("Conference Table & Chairs", "Furniture", "2026-03-01", 120000.0, 10.0, "StraightLine", 120000.0))

    # Seed Default Staff (Payroll)
    cursor.execute("SELECT COUNT(*) FROM payroll")
    if cursor.fetchone()[0] == 0:
        # We write payroll runs on-the-fly, but we can pre-populate staff database internally via endpoints
        pass

    conn.commit()
