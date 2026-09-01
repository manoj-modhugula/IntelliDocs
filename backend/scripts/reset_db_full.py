#!/usr/bin/env python3
"""Reset database completely: remove all users, workspaces, documents, and chunks. Fresh start."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def reset_db_full():
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET default_workspace_id = NULL"))
        await conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
        await conn.execute(text("TRUNCATE TABLE documents CASCADE"))
        await conn.execute(text("TRUNCATE TABLE workspaces CASCADE"))
        await conn.execute(text("TRUNCATE TABLE users CASCADE"))
    print("Database reset: all users, workspaces, documents, and chunks removed. Fresh start.")


if __name__ == "__main__":
    asyncio.run(reset_db_full())
