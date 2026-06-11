# models/customer.py
import sqlite3
from database.db import DatabaseManager

class Customer:
    """
    Represents a Customer and handles CRUD database operations, search directories,
    and purchase history logs.
    """
    def __init__(self, id=None, customer_name="", phone="", address="", created_at=""):
        """Initializes a Customer instance and its DatabaseManager."""
        self.db = DatabaseManager()
        self.id = id
        self.customer_name = customer_name
        self.phone = phone
        self.address = address
        self.created_at = created_at

    @staticmethod
    def from_row(row):
        """
        Converts a SQLite result row (tuple or sqlite3.Row) into a Customer instance.
        """
        if not row:
            return None
        try:
            # Handle standard tuple (default from DatabaseManager)
            if isinstance(row, (tuple, list)):
                return Customer(
                    id=row[0],
                    customer_name=row[1],
                    phone=row[2],
                    address=row[3],
                    created_at=row[4] if len(row) > 4 else None
                )
            # Handle sqlite3.Row or dict
            else:
                return Customer(
                    id=row['id'],
                    customer_name=row['customer_name'],
                    phone=row['phone'],
                    address=row['address'],
                    created_at=row['created_at']
                )
        except Exception as e:
            print(f"Error mapping row to Customer: {e}")
            return None

    # --- Complete Customer CRUD (Instance Methods utilizing DatabaseManager) ---

    def add_customer(self, customer_name, phone, address):
        """
        Inserts a new customer record. Prevents duplicate phone numbers if phone is provided.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            phone_clean = phone.strip() if phone else ""
            
            # Check duplicate phone if a phone number is provided
            if phone_clean:
                if self.get_customer_by_phone(phone_clean):
                    print(f"Insert failed: Customer with phone '{phone_clean}' already exists.")
                    return False

            query = """
            INSERT INTO customers (customer_name, phone, address)
            VALUES (?, ?, ?);
            """
            cursor = self.db.get_cursor()
            cursor.execute(query, (customer_name.strip(), phone_clean if phone_clean else None, address.strip() if address else None))
            self.id = cursor.lastrowid
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error adding customer: {e}")
            self.db.rollback()
            return False

    def get_customer_by_id(self, customer_id):
        """
        Retrieves a single customer record by its ID.
        
        Returns:
            tuple/None: The customer record tuple or None.
        """
        try:
            query = "SELECT * FROM customers WHERE id = ?;"
            return self.db.fetch_one(query, (customer_id,))
        except Exception as e:
            print(f"Error getting customer by id: {e}")
            return None

    def get_customer_by_phone(self, phone):
        """
        Retrieves a single customer record by phone number.
        
        Returns:
            tuple/None: The customer record tuple or None.
        """
        try:
            query = "SELECT * FROM customers WHERE phone = ?;"
            return self.db.fetch_one(query, (phone.strip(),))
        except Exception as e:
            print(f"Error getting customer by phone: {e}")
            return None

    def get_all_customers(self):
        """
        Retrieves all customer records sorted by customer_name ASC.
        
        Returns:
            list: List of customer record tuples.
        """
        try:
            query = "SELECT * FROM customers ORDER BY customer_name;"
            return self.db.fetch_all(query)
        except Exception as e:
            print(f"Error getting all customers: {e}")
            return []

    def search_customers(self, keyword):
        """
        Searches for customers matching a keyword in customer_name, phone, or address.
        
        Returns:
            list: List of matching customer record tuples.
        """
        try:
            query = """
            SELECT * FROM customers 
            WHERE customer_name LIKE ? 
               OR phone LIKE ? 
               OR address LIKE ?
            ORDER BY customer_name;
            """
            kw = f"%{keyword.strip()}%"
            return self.db.fetch_all(query, (kw, kw, kw))
        except Exception as e:
            print(f"Error searching customers: {e}")
            return []

    def update_customer(self, customer_id, customer_name, phone, address):
        """
        Updates an existing customer's details. Enforces unique phone numbers among other profiles.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            phone_clean = phone.strip() if phone else ""
            
            # Enforce unique phone if provided
            if phone_clean:
                existing = self.get_customer_by_phone(phone_clean)
                if existing and existing[0] != customer_id:
                    print(f"Update failed: Phone '{phone_clean}' is already in use by customer ID {existing[0]}.")
                    return False
            
            query = """
            UPDATE customers
            SET customer_name = ?, phone = ?, address = ?
            WHERE id = ?;
            """
            cursor = self.db.get_cursor()
            cursor.execute(query, (customer_name.strip(), phone_clean if phone_clean else None, address.strip() if address else None, customer_id))
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error updating customer: {e}")
            self.db.rollback()
            return False

    def delete_customer(self, customer_id):
        """
        Deletes a customer by ID only if they have no linked sales.
        
        Returns:
            tuple: (bool, str) -> (Success status, explanatory status message).
        """
        try:
            # Check for linked sales
            cursor = self.db.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM sales WHERE customer_id = ?;", (customer_id,))
            linked_sales = cursor.fetchone()[0]
            
            if linked_sales > 0:
                msg = f"Cannot delete customer ID {customer_id}: Profile is linked to {linked_sales} checkout invoices."
                print(msg)
                return False, msg
            
            cursor.execute("DELETE FROM customers WHERE id = ?;", (customer_id,))
            self.db.commit()
            return True, "Customer deleted successfully."
        except Exception as e:
            msg = f"Error deleting customer: {str(e)}"
            print(msg)
            self.db.rollback()
            return False, msg

    def get_customer_count(self):
        """
        Gets the total count of registered customers.
        
        Returns:
            int: Total customers count.
        """
        try:
            query = "SELECT COUNT(*) FROM customers;"
            res = self.db.fetch_one(query)
            return res[0] if res else 0
        except Exception as e:
            print(f"Error getting customer count: {e}")
            return 0

    def get_recent_customers(self, limit=10):
        """
        Retrieves recently registered customer record tuples.
        
        Returns:
            list: List of customer tuples.
        """
        try:
            query = "SELECT * FROM customers ORDER BY created_at DESC LIMIT ?;"
            return self.db.fetch_all(query, (limit,))
        except Exception as e:
            print(f"Error getting recent customers: {e}")
            return []

    # --- Backwards Compatibility Wrappers for UI and Services ---

    def save(self):
        """Saves current instance. Inserts if id is None, updates if id is set."""
        if self.id is None:
            success = self.add_customer(self.customer_name, self.phone, self.address)
            if success:
                db_cust = self.get_customer_by_phone(self.phone)
                if db_cust:
                    self.id = db_cust[0]
            return success
        else:
            return self.update_customer(self.id, self.customer_name, self.phone, self.address)

    @staticmethod
    def get_all():
        """Static wrapper for UI compatibility. Returns list of Customer instances."""
        c = Customer()
        rows = c.get_all_customers()
        return [Customer.from_row(r) for r in rows if r]

    @staticmethod
    def get_by_id(customer_id):
        """Static wrapper for UI compatibility. Returns Customer instance."""
        c = Customer()
        row = c.get_customer_by_id(customer_id)
        return Customer.from_row(row)

    @staticmethod
    def get_by_phone(phone):
        """Static wrapper for UI compatibility. Returns Customer instance."""
        c = Customer()
        row = c.get_customer_by_phone(phone)
        return Customer.from_row(row)

    @staticmethod
    def get_purchases(customer_id):
        """Static wrapper. Returns all invoices linked to customer as key-value dictionaries."""
        c = Customer()
        query = """
        SELECT s.invoice_no, s.sale_date, s.payment_method, s.total_amount
        FROM sales s
        WHERE s.customer_id = ?
        ORDER BY s.sale_date DESC;
        """
        rows = c.db.fetch_all(query, (customer_id,))
        mapped_purchases = []
        for r in rows:
            mapped_purchases.append({
                'invoice_no': r[0],
                'sale_date': r[1],
                'payment_method': r[2],
                'total_amount': r[3]
            })
        return mapped_purchases

if __name__ == "__main__":
    from database.db import init_db
    
    # Initialize database
    init_db()
    
    cust_mgr = Customer()
    
    print("=== STARTING CUSTOMER TEST RUN ===")
    
    # Clean up test numbers
    test_phone_1 = "9876543210"
    test_phone_2 = "8765432109"
    
    existing_1 = cust_mgr.get_customer_by_phone(test_phone_1)
    if existing_1:
        cust_mgr.db.execute("DELETE FROM customers WHERE id = ?;", (existing_1[0],))
        
    existing_2 = cust_mgr.get_customer_by_phone(test_phone_2)
    if existing_2:
        cust_mgr.db.execute("DELETE FROM customers WHERE id = ?;", (existing_2[0],))
        
    # 1. Add sample customers
    print("\n1. Adding Sample Customers:")
    success_1 = cust_mgr.add_customer("Ramesh Kumar", test_phone_1, "123 Main St, Chennai")
    success_2 = cust_mgr.add_customer("Suresh Raina", test_phone_2, "456 Park St, Coimbatore")
    print(f"   Add Ramesh: {success_1}")
    print(f"   Add Suresh: {success_2}")
    
    # Verify phone duplicate check
    dup_success = cust_mgr.add_customer("Ramesh Duplicate", test_phone_1, "Duplicate Road")
    print(f"   Add Duplicate Phone (should be False): {dup_success}")
    
    # 2. Search customers
    print("\n2. Searching Customers (Keyword: 'Kumar'):")
    results = cust_mgr.search_customers("Kumar")
    for c in results:
        print(f"   - Match: {c[1]} (Phone: {c[2]}, Address: {c[3]})")
        
    # 3. Update customer
    print("\n3. Updating Customer Details:")
    c_data = cust_mgr.get_customer_by_phone(test_phone_1)
    if c_data:
        c_id = c_data[0]
        updated = cust_mgr.update_customer(c_id, "Ramesh Kumar Updated", test_phone_1, "999 New Way Road, Chennai")
        print(f"   Update Status: {updated}")
        updated_data = cust_mgr.get_customer_by_id(c_id)
        print(f"   New Address: {updated_data[3] if updated_data else 'N/A'}")
        
    # 4. Count customers
    print("\n4. Counting Total Customers:")
    count = cust_mgr.get_customer_count()
    print(f"   Total Customers: {count}")
    
    # 5. List recent customers
    print("\n5. Listing Recent Customers (Limit 5):")
    recent = cust_mgr.get_recent_customers(limit=5)
    for c in recent:
        print(f"   - Customer: {c[1]} (Phone: {c[2]}, Created At: {c[4]})")
        
    # 6. Test Deletion
    print("\n6. Testing Deletion:")
    del_c = cust_mgr.get_customer_by_phone(test_phone_1)
    if del_c:
        success, msg = cust_mgr.delete_customer(del_c[0])
        print(f"   Delete Ramesh: Status={success}, Msg={msg}")
        
    del_c2 = cust_mgr.get_customer_by_phone(test_phone_2)
    if del_c2:
        success, msg = cust_mgr.delete_customer(del_c2[0])
        print(f"   Delete Suresh: Status={success}, Msg={msg}")
        
    print("\n=== CUSTOMER TEST RUN COMPLETED successfully ===")
