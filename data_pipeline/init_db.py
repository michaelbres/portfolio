"""
Run once to create all database tables.
Usage: python data_pipeline/init_db.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import engine, Base
import models  # noqa: F401 — registers all models with Base

Base.metadata.create_all(bind=engine)
print("Database tables created successfully.")
