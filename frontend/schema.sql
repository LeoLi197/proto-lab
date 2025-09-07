-- frontend/schema.sql
-- This schema defines the structure for the usage tracking table in Cloudflare D1.
-- It can be applied using the command:
-- wrangler d1 execute <DATABASE_NAME> --file=./schema.sql

-- Drop the table if it already exists to ensure a clean setup
DROP TABLE IF EXISTS Usage;

-- Create the main table for storing AI API usage records
CREATE TABLE Usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  feature TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  cost REAL DEFAULT 0.0,
  user_id TEXT
);

-- Optional: Create indexes to speed up queries for the dashboard
CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON Usage (timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_feature ON Usage (feature);
CREATE INDEX IF NOT EXISTS idx_usage_model ON Usage (model);