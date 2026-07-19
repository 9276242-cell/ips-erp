from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from ips_app.db import get_db_connection
from ips_app.auth import get_current_user, RoleChecker
from ips_app.accounting import log_audit

router = APIRouter(prefix="/library", tags=["Library Management"])

class BookCreateSchema(BaseModel):
    accession_no: str
    isbn: Optional[str] = ""
    title: str
    author: Optional[str] = ""
    publisher: Optional[str] = ""
    category: Optional[str] = ""
    cost: Optional[float] = 0.0

class MemberCreateSchema(BaseModel):
    name: str
    member_type: str  # Staff, External, Student
    email: Optional[str] = ""
    phone: Optional[str] = ""
    duration_days: Optional[int] = 365

class IssueBookSchema(BaseModel):
    book_id: int
    member_id: int
    duration_days: Optional[int] = 14

# 1. Fetch Books Catalog
@router.get("/books")
def get_books():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books")
    books = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return books

# 2. Add New Book to Catalog
@router.post("/books", dependencies=[Depends(RoleChecker(["Admin", "Librarian"]))])
def create_book(data: BookCreateSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO books (accession_no, isbn, title, author, publisher, category, cost) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data.accession_no, data.isbn, data.title, data.author, data.publisher, data.category, data.cost)
        )
        book_id = cursor.lastrowid
        
        # Optionally post double-entry voucher capitalizing the book as asset if necessary
        # For simplicity, we register it in the ledger database and log audit
        log_audit(cursor, "books", "INSERT", book_id, user["sub"], f"Cataloged book {data.accession_no} - {data.title}")
        conn.commit()
        return {"success": True, "id": book_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 3. Fetch Library Members
@router.get("/members")
def get_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members")
    members = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return members

# 4. Register Library Member
@router.post("/members", dependencies=[Depends(RoleChecker(["Admin", "Librarian"]))])
def create_member(data: MemberCreateSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        start_date = datetime.now().strftime("%Y-%m-%d")
        expiry_date = (datetime.now() + timedelta(days=data.duration_days)).strftime("%Y-%m-%d")
        
        cursor.execute(
            "INSERT INTO members (name, member_type, email, phone, membership_date, expiry_date, status) VALUES (?, ?, ?, ?, ?, ?, 'Active')",
            (data.name, data.member_type, data.email, data.phone, start_date, expiry_date)
        )
        member_id = cursor.lastrowid
        log_audit(cursor, "members", "INSERT", member_id, user["sub"], f"Registered member {data.name}")
        conn.commit()
        return {"success": True, "id": member_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 5. Issue Book (Mark Book as Borrowed)
@router.post("/issue", dependencies=[Depends(RoleChecker(["Admin", "Librarian"]))])
def issue_book(data: IssueBookSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check Book Availability
        cursor.execute("SELECT * FROM books WHERE id = ?", (data.book_id,))
        book = cursor.fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        if book["status"] != "Available":
            raise HTTPException(status_code=400, detail=f"Book is currently {book['status']}")

        # Check Member Status
        cursor.execute("SELECT * FROM members WHERE id = ?", (data.member_id,))
        member = cursor.fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if member["status"] != "Active":
            raise HTTPException(status_code=400, detail="Member membership is not active")

        # Issue book
        issue_date = datetime.now().strftime("%Y-%m-%d")
        due_date = (datetime.now() + timedelta(days=data.duration_days)).strftime("%Y-%m-%d")
        
        cursor.execute(
            "INSERT INTO book_issues (book_id, member_id, issue_date, due_date, status) VALUES (?, ?, ?, ?, 'Issued')",
            (data.book_id, data.member_id, issue_date, due_date)
        )
        issue_id = cursor.lastrowid
        
        # Mark book as borrowed
        cursor.execute("UPDATE books SET status = 'Borrowed' WHERE id = ?", (data.book_id,))
        
        log_audit(cursor, "book_issues", "INSERT", issue_id, user["sub"], f"Issued book {book['title']} to {member['name']}")
        conn.commit()
        return {"success": True, "issue_id": issue_id, "due_date": due_date}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 6. Return Book (Calculate Fines)
@router.post("/return/{issue_id}", dependencies=[Depends(RoleChecker(["Admin", "Librarian"]))])
def return_book(issue_id: int, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM book_issues WHERE id = ?", (issue_id,))
        issue = cursor.fetchone()
        if not issue:
            raise HTTPException(status_code=404, detail="Issue record not found")
        if issue["status"] == "Returned":
            raise HTTPException(status_code=400, detail="Book already returned")

        return_date = datetime.now().strftime("%Y-%m-%d")
        due_date = datetime.strptime(issue["due_date"], "%Y-%m-%d")
        today = datetime.now()
        
        # Calculate Fine: 10 PKR per day overdue
        fine = 0.0
        if today > due_date:
            days_overdue = (today - due_date).days
            fine = float(days_overdue * 10) # 10 PKR per day

        status = "Returned"
        
        # Update Issue Record
        cursor.execute(
            "UPDATE book_issues SET return_date = ?, fine_amount = ?, status = ? WHERE id = ?",
            (return_date, fine, status, issue_id)
        )
        
        # Mark Book as Available
        cursor.execute("UPDATE books SET status = 'Available' WHERE id = ?", (issue["book_id"],))
        
        log_audit(cursor, "book_issues", "UPDATE", issue_id, user["sub"], f"Returned book ID {issue['book_id']} with fine {fine} PKR")
        conn.commit()
        return {"success": True, "fine_amount": fine}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 7. Collect Fine Payment (Post Accounting Voucher Entry)
class PayFineSchema(BaseModel):
    issue_id: int
    amount: float

@router.post("/pay-fine", dependencies=[Depends(RoleChecker(["Admin", "Librarian", "Accountant"]))])
def pay_fine(data: PayFineSchema, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT bi.*, m.name as member_name, b.title as book_title
            FROM book_issues bi
            JOIN members m ON bi.member_id = m.id
            JOIN books b ON bi.book_id = b.id
            WHERE bi.id = ?
        """, (data.issue_id,))
        issue = cursor.fetchone()
        if not issue:
            raise HTTPException(status_code=404, detail="Issue record not found")
            
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Create Accounting Voucher (Receipt Entry)
        # Debit: Cash at Hand (ID 2 / Code 1001)
        # Credit: Library Fines Income (ID 15 / Code 4004)
        cursor.execute("SELECT COUNT(*) FROM vouchers WHERE type = 'Receipt'")
        count = cursor.fetchone()[0] + 1
        voucher_no = f"RV-{datetime.now().year}-{count:04d}"
        
        cursor.execute(
            "INSERT INTO vouchers (voucher_no, date, type, narration, created_by, status) VALUES (?, ?, 'Receipt', ?, ?, 'Approved')",
            (voucher_no, date_str, f"Fine Payment: {issue['member_name']} - Book: {issue['book_title']}", user["sub"])
        )
        voucher_id = cursor.lastrowid
        
        debit_acc_id = 2   # Cash at Hand
        credit_acc_id = 15 # Library Fines Income
        
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, ?, 0.0, 'Collected library fine')",
            (voucher_id, debit_acc_id, data.amount)
        )
        cursor.execute(
            "INSERT INTO voucher_lines (voucher_id, account_id, debit, credit, description) VALUES (?, ?, 0.0, ?, 'Library fine revenue')",
            (voucher_id, credit_acc_id, data.amount)
        )
        
        # Update COA balances
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (data.amount, debit_acc_id))
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (data.amount, credit_acc_id))
        
        # Clear fine amount on issue record
        cursor.execute("UPDATE book_issues SET fine_amount = 0.0 WHERE id = ?", (data.issue_id,))
        
        log_audit(cursor, "book_issues", "UPDATE", data.issue_id, user["sub"], f"Paid fine {data.amount} PKR for issue ID {data.issue_id}")
        conn.commit()
        return {"success": True, "voucher_no": voucher_no}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# 8. Library Activity Report
@router.get("/reports/loans")
def get_library_loans():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT bi.*, b.title as book_title, b.accession_no, m.name as member_name, m.member_type
        FROM book_issues bi
        JOIN books b ON bi.book_id = b.id
        JOIN members m ON bi.member_id = m.id
        ORDER BY bi.issue_date DESC
    """)
    loans = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return loans
