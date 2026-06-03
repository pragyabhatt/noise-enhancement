import sys, os
# Add backend directory to PYTHONPATH so 'app' package is discoverable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import asyncio
import os
from getpass import getpass

import argparse
from app.db.database import engine, Base, async_session
from app.db import crud
from app.security.hashing import get_password_hash

# Ensure DB tables exist
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_admin():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="pragya", help="User login name")
    parser.add_argument("--password", default="deal@123", help="Plain‑text password")
    parser.add_argument("--role", default="admin", help="User role (admin/operator) – default admin")
    args = parser.parse_args()
    
    username = os.getenv("ADMIN_USERNAME", args.username)
    password = os.getenv("ADMIN_PASSWORD", args.password)
    role = args.role

    password_hash = get_password_hash(password)
    async with async_session() as session:
        # Check if user already exists
        existing = await crud.get_user_by_username(session, username)
        if existing:
            print(f"User '{username}' already exists. No action taken.")
            return
        await crud.create_user(session, username=username, password_hash=password_hash, role=role)
        print(f"Admin user '{username}' created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
    asyncio.run(create_admin())
