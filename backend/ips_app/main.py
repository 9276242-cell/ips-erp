import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import hashlib

from ips_app.db import init_db, get_db_connection
from ips_app.auth import create_access_token, get_current_user
from ips_app.accounting import router as accounting_router
from ips_app.inventory import router as inventory_router
from ips_app.library import router as library_router
from ips_app.assets import router as assets_router
from ips_app.payroll import router as payroll_router

# Initialize Database Schema & Seed Data
init_db()

app = FastAPI(
    title="IPS ERP API Gateway",
    description="Turn-key Accounting, Inventory, and Library system for Institute of Policy Studies (IPS)",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular Routers
app.include_router(accounting_router)
app.include_router(inventory_router)
app.include_router(library_router)
app.include_router(assets_router)
app.include_router(payroll_router)

class LoginSchema(BaseModel):
    username: str
    password: str

# Authentication Endpoints
@app.post("/auth/login")
def login(data: LoginSchema):
    conn = get_db_connection()
    cursor = conn.cursor()
    pw_hash = hashlib.sha256(data.password.encode()).hexdigest()
    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (data.username, pw_hash)
    )
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password credentials")
        
    token = create_access_token(user["username"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"]
    }

@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# Mount compiled static React files (dist) if they exist
# Otherwise serve API index info page
static_dir = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse)
    def index():
        return """<!DOCTYPE html>
<html>
<head>
    <title>IPS ERP API Gateway</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f7f9; color: #2b354e; text-align: center; padding-top: 100px; }
        .card { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #0d9488; }
        p { color: #64748b; line-height: 1.6; }
        .btn { display: inline-block; padding: 10px 20px; background-color: #0d9488; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>IPS ERP - API Gateway Online</h1>
        <p>The FastAPI backend server is running successfully on localhost! The SQLite database has been initialized and seeded with Chart of Accounts, sample books, and default users.</p>
        <p>To access the documentation and verify endpoints directly, visit the Swagger UI docs page.</p>
        <a href="/docs" class="btn">View Swagger REST Docs</a>
    </div>
</body>
</html>"""

