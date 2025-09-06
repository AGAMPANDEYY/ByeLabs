-- HiLabs Roster Processing - Database Initialization
-- This script sets up the initial database schema and extensions

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create initial database schema will be handled by SQLAlchemy migrations
-- This file is here for any custom initialization needed

-- Set up proper permissions
GRANT ALL PRIVILEGES ON DATABASE hilabs TO hilabs;

