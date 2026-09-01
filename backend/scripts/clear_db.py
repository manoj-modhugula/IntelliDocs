#!/usr/bin/env python3
"""Clear documents and chunks from the database. Keeps users and workspaces."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def clear_db():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE chunks CASCADE"))
        await conn.execute(text("TRUNCATE TABLE documents CASCADE"))
        await conn.execute(text("UPDATE workspaces SET updated_at = NOW()"))
    print("Database cleared: chunks and documents truncated")


if __name__ == "__main__":
    asyncio.run(clear_db())
