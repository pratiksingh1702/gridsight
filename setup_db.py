import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_database():
    """
    Connects to local PostgreSQL, creates the gridsight database, 
    and initializes tables and TimescaleDB hypertables.
    """
    dbname = "gridsight"
    # Assuming local Postgres with current user authentication or default settings
    # In a real production environment, these would be in config.py or environment variables.
    conn_params = {
        "host": "localhost",
        "user": "postgres",
        "password": "password", # Placeholder - common default
        "port": 5432
    }

    try:
        # 1. Create database if not exists
        conn = psycopg2.connect(dbname='postgres', **conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{dbname}'")
        exists = cur.fetchone()
        if not exists:
            logger.info(f"Creating database {dbname}...")
            cur.execute(f"CREATE DATABASE {dbname}")
        else:
            logger.info(f"Database {dbname} already exists.")
            
        cur.close()
        conn.close()

        # 2. Connect to the new database
        conn = psycopg2.connect(dbname=dbname, **conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # 3. Enable TimescaleDB extension
        logger.info("Enabling TimescaleDB extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

        # 4. Create meter_readings table
        logger.info("Creating meter_readings table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meter_readings (
                meter_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                kwh DOUBLE PRECISION,
                voltage DOUBLE PRECISION,
                status TEXT
            );
        """)
        
        # Convert to hypertable
        logger.info("Converting meter_readings to hypertable...")
        cur.execute("SELECT create_hypertable('meter_readings', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');")
        
        # Create index
        cur.execute("CREATE INDEX IF NOT EXISTS idx_meter_timestamp ON meter_readings (meter_id, timestamp DESC);")

        # 5. Create feeder_head_readings table
        logger.info("Creating feeder_head_readings table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feeder_head_readings (
                feeder_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                kwh DOUBLE PRECISION,
                voltage DOUBLE PRECISION,
                status TEXT
            );
        """)
        cur.execute("SELECT create_hypertable('feeder_head_readings', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_feeder_timestamp ON feeder_head_readings (feeder_id, timestamp DESC);")

        # 6. Create escalation_log table
        logger.info("Creating escalation_log table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS escalation_log (
                meter_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                weighted_score DOUBLE PRECISION,
                agents_firing INTEGER,
                outcome TEXT
            );
        """)

        # 7. Create agent_weights_log table
        logger.info("Creating agent_weights_log table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_weights_log (
                timestamp TIMESTAMPTZ NOT NULL,
                agent_name TEXT NOT NULL,
                old_weight DOUBLE PRECISION,
                new_weight DOUBLE PRECISION,
                reason TEXT
            );
        """)

        logger.info("Database setup completed successfully.")
        cur.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False

if __name__ == "__main__":
    setup_database()
