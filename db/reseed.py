"""
Reseed Firestore — deletes all existing data and re-seeds with fresh dates.
Run: python -m db.reseed
Use before demos or deployment to ensure current dates in all data.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from db.firestore_client import get_client

db = get_client()

COLLECTIONS = [
    "tasks",
    "shifts",
    "maintenance_windows",
    "technicians",
    "alerts",
    "documents",
    "audit_log",
]


def delete_collection(name):
    """Delete all documents in a collection."""
    col = db.collection(name)
    docs = col.stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    print(f"  Deleted {count} documents from '{name}'")


def main():
    print("Clearing all Firestore collections...")
    for name in COLLECTIONS:
        delete_collection(name)

    print("\nRe-seeding with fresh data...")
    from db.seed_data import main as seed_main
    seed_main()

    print("\nReseed complete. All dates are relative to today.")


if __name__ == "__main__":
    main()