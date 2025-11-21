-- Run this in psql to create the database
-- Connect first: psql -U postgres

CREATE DATABASE star4ce_db;
CREATE USER star4ce_user WITH PASSWORD 'star4ce123';
GRANT ALL PRIVILEGES ON DATABASE star4ce_db TO star4ce_user;

-- Then connect to the new database and grant schema privileges
\c star4ce_db
GRANT ALL ON SCHEMA public TO star4ce_user;

