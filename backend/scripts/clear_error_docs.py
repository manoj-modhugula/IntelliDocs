#!/usr/bin/env python3
"""Delete known error docs by name and/or all documents in ERROR status from the DB."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.database import async_session
from app.models import Document

# Known error doc names that keep reappearing in the UI
KNOWN_ERROR_NAMES = {"intellidocs-upload.txt", "anon-upload.txt"}


async def clear_error_docs(delete_all_error_status: bool = False):
    async with async_session() as db:
        if delete_all_error_status:
            # Delete all documents with status=ERROR (clears any error docs)
            result = await db.execute(select(Document).where(Document.status == "error"))
        else:
            # Only delete the two known error doc names
            result = await db.execute(select(Document).where(Document.name.in_(KNOWN_ERROR_NAMES)))
        docs = result.scalars().all()
        for doc in docs:
            await db.delete(doc)
            print(f"Deleted: {doc.name} (id={doc.id}, status={doc.status})")
        await db.commit()
    print(f"Done. Removed {len(docs)} document(s).")


if __name__ == "__main__":
    # Pass --all-error to remove every document in ERROR status (not just the two known names)
    delete_all = "--all-error" in sys.argv
    if delete_all:
        print("Removing all documents with status=ERROR ...")
    asyncio.run(clear_error_docs(delete_all_error_status=delete_all))
