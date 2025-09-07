"""
Database configuration and session management.

This module provides SQLAlchemy engine and session management
for the HiLabs Roster Processing application.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .config import settings
from .models import Base

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    echo=settings.dev_show_sql,
    # For development, use in-memory SQLite if needed
    # poolclass=StaticPool if "sqlite" in settings.database_url else None,
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance and compatibility."""
    if "sqlite" in settings.database_url:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def create_tables():
    """
    Create all database tables.
    
    This function creates all tables defined in the models module.
    It's safe to call multiple times.
    """
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


def drop_tables():
    """
    Drop all database tables.
    
    WARNING: This will delete all data!
    Only use in development or testing.
    """
    if settings.app_env == "prod":
        raise RuntimeError("Cannot drop tables in production environment!")
    
    try:
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Get a database session with automatic cleanup.
    
    This is a context manager that provides a database session
    and ensures it's properly closed after use.
    
    Usage:
        with get_db_session() as session:
            # Use session here
            pass
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database sessions.
    
    This function is used as a FastAPI dependency to provide
    database sessions to route handlers.
    """
    with get_db_session() as session:
        yield session


def check_database_connection() -> bool:
    """
    Check if the database connection is working.
    
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        from sqlalchemy import text
        with get_db_session() as session:
            # Simple query to test connection
            session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def get_database_info() -> dict:
    """
    Get information about the database connection.
    
    Returns:
        Dictionary with database information
    """
    try:
        with get_db_session() as session:
            # Get database version
            if "postgresql" in settings.database_url:
                result = session.execute(text("SELECT version()"))
                version = result.scalar()
            elif "sqlite" in settings.database_url:
                result = session.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
            else:
                version = "Unknown"
            
            return {
                "connected": True,
                "url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "local",
                "version": version,
                "pool_size": engine.pool.size(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
            }
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


# Initialize database on module import
def init_database():
    """
    Initialize the database.
    
    This function should be called during application startup
    to ensure the database is properly set up.
    """
    logger.info("Initializing database...")
    
    # Check connection
    if not check_database_connection():
        logger.error("Database connection failed!")
        raise RuntimeError("Cannot connect to database")
    
    # Create tables
    create_tables()
    
    logger.info("Database initialization complete")


# Auto-initialize if not in testing mode
if not settings.app_env == "test":
    try:
        init_database()
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.warning("Application will continue but database features may not work")
