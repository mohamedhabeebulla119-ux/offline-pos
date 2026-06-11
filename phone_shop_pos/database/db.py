# database/db.py
import sqlite3
from database.schema import create_tables, DB_PATH

class DatabaseManager:
    """
    Manages database connections and common database operations for SQLite.
    """
    def __init__(self):
        """Initializes the database manager and establishes a connection."""
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        """
        Establishes SQLite connection and enables foreign key support.
        """
        try:
            self.conn = sqlite3.connect(DB_PATH)
            # Enable SQLite foreign key constraint enforcement
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            self.conn = None
            self.cursor = None

    def get_connection(self):
        """
        Returns the database connection object.
        """
        return self.conn

    def get_cursor(self):
        """
        Returns the database cursor object.
        """
        return self.cursor

    def commit(self):
        """
        Commits all pending database changes.
        """
        if self.conn:
            try:
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"Error committing transaction: {e}")

    def rollback(self):
        """
        Rolls back current database transaction in case of errors.
        """
        if self.conn:
            try:
                self.conn.rollback()
            except sqlite3.Error as e:
                print(f"Error rolling back transaction: {e}")

    def close(self):
        """
        Safely closes the database connection and cursor.
        """
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except sqlite3.Error as e:
            print(f"Error closing connection: {e}")
        finally:
            self.conn = None
            self.cursor = None

    def execute(self, query, params=None):
        """
        Executes INSERT, UPDATE, or DELETE queries and commits automatically.
        
        Args:
            query (str): The SQL query string.
            params (tuple/list, optional): Parameters to pass to the query.
            
        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        if params is None:
            params = []
        try:
            self.cursor.execute(query, params)
            self.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error executing query: {e}")
            self.rollback()
            return False

    def fetch_one(self, query, params=None):
        """
        Executes a query and fetches a single record.
        
        Args:
            query (str): The SQL query string.
            params (tuple/list, optional): Parameters to pass to the query.
            
        Returns:
            tuple/None: A single tuple containing the query result, or None.
        """
        if params is None:
            params = []
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Database error fetching single record: {e}")
            return None

    def fetch_all(self, query, params=None):
        """
        Executes a query and fetches all matching records.
        
        Args:
            query (str): The SQL query string.
            params (tuple/list, optional): Parameters to pass to the query.
            
        Returns:
            list: A list of tuples containing all matching records.
        """
        if params is None:
            params = []
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error fetching all records: {e}")
            return []

    def execute_many(self, query, data):
        """
        Executes a query with multiple data records (bulk insert/update).
        
        Args:
            query (str): The SQL query string.
            data (list): A list of tuples containing data records.
            
        Returns:
            bool: True if the bulk operation was successful, False otherwise.
        """
        try:
            self.cursor.executemany(query, data)
            self.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error executing bulk query: {e}")
            self.rollback()
            return False

def get_db():
    """
    Returns a DatabaseManager instance.
    """
    return DatabaseManager()

# --- Backward Compatibility Helpers ---
def get_connection():
    """
    Returns a sqlite3.Connection with Row factory enabled for backwards compatibility.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database schema.
    """
    create_tables()

if __name__ == "__main__":
    # Ensure database schema exists before testing
    init_db()
    
    # Instantiate manager and establish connection
    db = get_db()
    if db.get_connection():
        print("Connected to phone_shop.db")
        print("Tables Found:")
        
        # Query all table names, excluding system tables
        tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';")
        for table in tables:
            print(table[0])
            
        db.close()
        print("Connection Closed")
