# models/product.py
import sqlite3
from database.db import DatabaseManager

class Product:
    """
    Represents a Product and handles CRUD database operations, stock management,
    and history logs for inventory auditing.
    """
    def __init__(self, id=None, barcode="", product_name="", brand="", category="Phones", 
                 purchase_price=0.0, selling_price=0.0, quantity=0, created_at=None):
        """
        Initializes a Product instance.
        Also instantiates a DatabaseManager to perform database operations.
        """
        self.db = DatabaseManager()
        self.id = id
        self.barcode = barcode
        self.product_name = product_name
        self.brand = brand
        self.category = category
        self.purchase_price = purchase_price
        self.selling_price = selling_price
        self.quantity = quantity
        self.created_at = created_at
        
        # Compatibility properties for UI alerts
        self.min_stock = 5 

    @staticmethod
    def from_row(row):
        """
        Converts a SQLite result row (tuple or sqlite3.Row) into a Product instance.
        """
        if not row:
            return None
        try:
            # Handle standard tuple (default from DatabaseManager)
            if isinstance(row, (tuple, list)):
                return Product(
                    id=row[0],
                    barcode=row[1],
                    product_name=row[2],
                    brand=row[3],
                    category=row[4],
                    purchase_price=row[5],
                    selling_price=row[6],
                    quantity=row[7],
                    created_at=row[8] if len(row) > 8 else None
                )
            # Handle sqlite3.Row or dict
            else:
                return Product(
                    id=row['id'],
                    barcode=row['barcode'],
                    product_name=row['product_name'],
                    brand=row['brand'],
                    category=row['category'],
                    purchase_price=row['purchase_price'],
                    selling_price=row['selling_price'],
                    quantity=row['quantity'],
                    created_at=row['created_at']
                )
        except Exception as e:
            print(f"Error mapping row to Product: {e}")
            return None

    # --- Complete Product CRUD (Instance Methods utilizing DatabaseManager) ---

    def add_product(self, barcode, product_name, brand, category, purchase_price, selling_price, quantity):
        """
        Inserts a new product into the database. Prevents duplicate barcodes.
        Automatically logs the initial entry in stock_history.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            # Check for duplicate barcode first
            if self.get_product_by_barcode(barcode):
                print(f"Insert failed: Product with barcode '{barcode}' already exists.")
                return False

            query = """
            INSERT INTO products (barcode, product_name, brand, category, purchase_price, selling_price, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """
            cursor = self.db.get_cursor()
            cursor.execute(query, (barcode.strip(), product_name.strip(), brand.strip(), 
                                   category.strip(), purchase_price, selling_price, quantity))
            
            product_id = cursor.lastrowid

            # Log initial stock history
            history_query = """
            INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
            VALUES (?, 0, ?, 'Initial Catalog Entry');
            """
            cursor.execute(history_query, (product_id, quantity))
            
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error adding product: {e}")
            self.db.rollback()
            return False

    def generate_next_barcode(self):
        """Reads latest product barcode and generates the next increment."""
        try:
            cursor = self.db.get_cursor()
            cursor.execute("SELECT barcode FROM products WHERE barcode LIKE 'PS%' ORDER BY id DESC LIMIT 1;")
            row = cursor.fetchone()
            if row:
                latest = row[0]
                try:
                    num_part = int(latest[2:])
                    next_num = num_part + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            return f"PS{str(next_num).zfill(6)}"
        except Exception as e:
            print(f"Error in generate_next_barcode: {e}")
            return "PS000001"

    def is_barcode_unique(self, barcode_val):
        """Checks if the barcode is unique in the products table."""
        try:
            cursor = self.db.get_cursor()
            cursor.execute("SELECT COUNT(*) FROM products WHERE barcode = ?;", (barcode_val,))
            count = cursor.fetchone()[0]
            return count == 0
        except Exception:
            return False

    def generate_unique_barcode(self):
        """Generates a guaranteed unique barcode by incrementing."""
        barcode_val = self.generate_next_barcode()
        while not self.is_barcode_unique(barcode_val):
            try:
                num_part = int(barcode_val[2:])
                barcode_val = f"PS{str(num_part + 1).zfill(6)}"
            except Exception:
                barcode_val = "PS000001"
        return barcode_val

    def create_product_with_barcode(self, brand, product_name, category, purchase_price, selling_price, quantity):
        """
        Creates a new product with an automatically generated unique barcode of format PSXXXXXX.
        Generates the barcode PNG image file automatically.
        Uses a single transaction and rolls back on failure.
        
        Returns:
            dict: Success status, product_id, generated barcode, and image path or failure message.
        """
        try:
            barcode_val = self.generate_unique_barcode()
            cursor = self.db.get_cursor()
            
            # Insert product
            query = """
            INSERT INTO products (barcode, product_name, brand, category, purchase_price, selling_price, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """
            cursor.execute(query, (barcode_val, product_name.strip(), brand.strip(), category.strip(),
                                   purchase_price, selling_price, quantity))
            product_id = cursor.lastrowid
            
            # Log initial stock history
            history_query = """
            INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
            VALUES (?, 0, ?, 'Initial Catalog Entry');
            """
            cursor.execute(history_query, (product_id, quantity))
            
            # Generate PNG barcode image
            from services.barcode_service import BarcodeService
            barcode_srv = BarcodeService()
            success, img_path = barcode_srv.create_barcode(barcode_val)
            if not success:
                raise Exception(f"Failed to generate barcode image: {img_path}")
                
            self.db.commit()
            
            return {
                "success": True,
                "product_id": product_id,
                "barcode": barcode_val,
                "barcode_image": f"barcodes/{barcode_val}.png"
            }
        except Exception as e:
            self.db.rollback()
            print(f"Error creating product with barcode: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def regenerate_barcode(self, product_id):
        """
        Generates a new barcode for an existing product.
        Updates the database, generates the new PNG, and deletes the old PNG.
        Uses a single transaction.
        
        Returns:
            dict: success status, new barcode, and image path or error message.
        """
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return {"success": False, "message": "Product not found."}
                
            old_barcode = product[1]
            new_barcode = self.generate_unique_barcode()
            
            cursor = self.db.get_cursor()
            cursor.execute("UPDATE products SET barcode = ? WHERE id = ?;", (new_barcode, product_id))
            
            # Generate new PNG
            from services.barcode_service import BarcodeService
            barcode_srv = BarcodeService()
            success, img_path = barcode_srv.create_barcode(new_barcode)
            if not success:
                raise Exception(f"Failed to generate barcode image: {img_path}")
                
            # Delete old PNG if it exists
            barcode_srv.delete_barcode(old_barcode)
            
            self.db.commit()
            
            return {
                "success": True,
                "barcode": new_barcode,
                "barcode_image": f"barcodes/{new_barcode}.png"
            }
        except Exception as e:
            self.db.rollback()
            print(f"Error in regenerate_barcode: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def get_all_products(self):
        """
        Retrieves all products from the database, sorted by product_name ASC.
        
        Returns:
            list: List of product record tuples.
        """
        try:
            query = "SELECT * FROM products ORDER BY product_name ASC;"
            return self.db.fetch_all(query)
        except Exception as e:
            print(f"Error getting all products: {e}")
            return []

    def get_product_by_id(self, product_id):
        """
        Retrieves a single product by its database ID.
        
        Returns:
            tuple/None: The product record tuple or None.
        """
        try:
            query = "SELECT * FROM products WHERE id = ?;"
            return self.db.fetch_one(query, (product_id,))
        except Exception as e:
            print(f"Error getting product by id: {e}")
            return None

    def get_product_by_barcode(self, barcode):
        """
        Retrieves a single product by its barcode.
        
        Returns:
            tuple/None: The product record tuple or None.
        """
        try:
            query = "SELECT * FROM products WHERE UPPER(barcode) = UPPER(?);"
            return self.db.fetch_one(query, (barcode.strip(),))
        except Exception as e:
            print(f"Error getting product by barcode: {e}")
            return None

    def search_products(self, keyword):
        """
        Searches for products matching a keyword in barcode, product_name, brand, or category.
        
        Returns:
            list: List of matching product record tuples.
        """
        try:
            query = """
            SELECT * FROM products 
            WHERE barcode LIKE ? 
               OR product_name LIKE ? 
               OR brand LIKE ? 
               OR category LIKE ?
            ORDER BY product_name ASC;
            """
            kw = f"%{keyword.strip()}%"
            return self.db.fetch_all(query, (kw, kw, kw, kw))
        except Exception as e:
            print(f"Error searching products: {e}")
            return []

    def update_product(self, product_id, barcode, product_name, brand, category, purchase_price, selling_price, quantity):
        """
        Updates all fields of an existing product in the database.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            query = """
            UPDATE products 
            SET barcode = ?, product_name = ?, brand = ?, category = ?, purchase_price = ?, selling_price = ?, quantity = ?
            WHERE id = ?;
            """
            cursor = self.db.get_cursor()
            cursor.execute(query, (barcode.strip(), product_name.strip(), brand.strip(), 
                                   category.strip(), purchase_price, selling_price, quantity, product_id))
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error updating product: {e}")
            self.db.rollback()
            return False

    def update_stock(self, product_id, new_quantity):
        """
        Updates stock quantity and inserts a MANUAL_UPDATE record into stock_history.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return False
            
            previous_qty = product[7] # quantity index
            
            cursor = self.db.get_cursor()
            cursor.execute("UPDATE products SET quantity = ? WHERE id = ?;", (new_quantity, product_id))
            
            cursor.execute(
                """
                INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
                VALUES (?, ?, ?, 'MANUAL_UPDATE');
                """,
                (product_id, previous_qty, new_quantity)
            )
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error updating stock: {e}")
            self.db.rollback()
            return False

    def increase_stock(self, product_id, amount):
        """
        Increases stock quantity by the specified amount and logs as STOCK_IN.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return False
            
            previous_qty = product[7]
            new_qty = previous_qty + amount
            
            cursor = self.db.get_cursor()
            cursor.execute("UPDATE products SET quantity = ? WHERE id = ?;", (new_qty, product_id))
            
            cursor.execute(
                """
                INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
                VALUES (?, ?, ?, 'STOCK_IN');
                """,
                (product_id, previous_qty, new_qty)
            )
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error increasing stock: {e}")
            self.db.rollback()
            return False

    def decrease_stock(self, product_id, amount):
        """
        Decreases stock quantity by the specified amount (preventing negative stock) and logs as STOCK_OUT.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            product = self.get_product_by_id(product_id)
            if not product:
                return False
            
            previous_qty = product[7]
            new_qty = previous_qty - amount
            if new_qty < 0:
                print(f"Cannot decrease stock: requested {amount}, but only {previous_qty} in stock.")
                return False
            
            cursor = self.db.get_cursor()
            cursor.execute("UPDATE products SET quantity = ? WHERE id = ?;", (new_qty, product_id))
            
            cursor.execute(
                """
                INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
                VALUES (?, ?, ?, 'STOCK_OUT');
                """,
                (product_id, previous_qty, new_qty)
            )
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error decreasing stock: {e}")
            self.db.rollback()
            return False

    def delete_product(self, product_id):
        """
        Deletes a product record by its ID.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            cursor = self.db.get_cursor()
            cursor.execute("DELETE FROM products WHERE id = ?;", (product_id,))
            self.db.commit()
            return True
        except Exception as e:
            print(f"Error deleting product: {e}")
            self.db.rollback()
            return False

    def get_low_stock_products(self, threshold=5):
        """
        Retrieves products with quantities less than or equal to the threshold.
        
        Returns:
            list: List of product record tuples.
        """
        try:
            query = "SELECT * FROM products WHERE quantity <= ? ORDER BY product_name ASC;"
            return self.db.fetch_all(query, (threshold,))
        except Exception as e:
            print(f"Error checking low stock: {e}")
            return []

    def get_product_count(self):
        """
        Gets the total count of product types.
        
        Returns:
            int: The total count of products.
        """
        try:
            query = "SELECT COUNT(*) FROM products;"
            res = self.db.fetch_one(query)
            return res[0] if res else 0
        except Exception as e:
            print(f"Error getting product count: {e}")
            return 0

    def get_inventory_value(self):
        """
        Calculates the total value of all product inventory (purchase_price * quantity).
        
        Returns:
            float: Total inventory purchase value.
        """
        try:
            query = "SELECT SUM(purchase_price * quantity) FROM products;"
            res = self.db.fetch_one(query)
            return res[0] if res and res[0] is not None else 0.0
        except Exception as e:
            print(f"Error calculating inventory value: {e}")
            return 0.0

    # --- Backwards Compatibility Static and Instance Methods for UI / Services ---

    def save(self):
        """
        Saves the current Product instance. 
        Inserts if id is None, updates if id is set.
        """
        if self.id is None:
            success = self.add_product(
                self.barcode, self.product_name, self.brand, self.category,
                self.purchase_price, self.selling_price, self.quantity
            )
            if success:
                # Retrieve the newly generated ID
                db_prod = self.get_product_by_barcode(self.barcode)
                if db_prod:
                    self.id = db_prod[0]
            return success
        else:
            return self.update_product(
                self.id, self.barcode, self.product_name, self.brand, self.category,
                self.purchase_price, self.selling_price, self.quantity
            )

    @staticmethod
    def get_all():
        """Static wrapper for UI compatibility. Returns list of Product objects."""
        p = Product()
        rows = p.get_all_products()
        return [Product.from_row(r) for r in rows if r]

    @staticmethod
    def get_by_id(product_id):
        """Static wrapper for UI compatibility. Returns Product instance."""
        p = Product()
        row = p.get_product_by_id(product_id)
        return Product.from_row(row)

    @staticmethod
    def get_by_barcode(barcode):
        """Static wrapper for UI compatibility. Returns Product instance."""
        p = Product()
        row = p.get_product_by_barcode(barcode)
        return Product.from_row(row)

    @staticmethod
    def get_by_sku(sku):
        """Static alias. Barcode and SKU are identical."""
        return Product.get_by_barcode(sku)

    @staticmethod
    def delete(product_id):
        """Static wrapper for UI compatibility. Deletes product by ID."""
        p = Product()
        return p.delete_product(product_id)

    @staticmethod
    def get_stock(product_id):
        """Static wrapper. Returns raw quantity of product."""
        p = Product.get_by_id(product_id)
        return p.quantity if p else 0

    @staticmethod
    def add_inventory_tx(product_id, tx_type, qty, reason, date_str):
        """Static wrapper. Processes a manual transaction and log entry."""
        p = Product()
        try:
            prod_row = p.get_product_by_id(product_id)
            if not prod_row:
                return
            previous_qty = prod_row[7]
            
            if tx_type == 'in':
                new_qty = previous_qty + qty
            else:
                new_qty = max(0, previous_qty - qty)
                
            cursor = p.db.get_cursor()
            cursor.execute("UPDATE products SET quantity = ? WHERE id = ?;", (new_qty, product_id))
            
            # Log in stock history with custom date and action reason
            cursor.execute(
                """
                INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type, updated_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (product_id, previous_qty, new_qty, reason, date_str)
            )
            p.db.commit()
        except Exception as e:
            print(f"Error in add_inventory_tx: {e}")
            p.db.rollback()

    @staticmethod
    def get_inventory_log():
        """Static wrapper. Returns transaction list formatted with UI dictionary keys."""
        p = Product()
        query = """
        SELECT sh.updated_at as date, p.brand, p.product_name as model, p.barcode as sku,
               (CASE WHEN sh.new_qty > sh.previous_qty THEN 'in' ELSE 'out' END) as type,
               ABS(sh.new_qty - sh.previous_qty) as quantity,
               sh.action_type as reason
        FROM stock_history sh
        JOIN products p ON sh.product_id = p.id
        ORDER BY sh.updated_at DESC;
        """
        rows = p.db.fetch_all(query)
        mapped_logs = []
        for r in rows:
            mapped_logs.append({
                'date': r[0],
                'brand': r[1],
                'model': r[2],
                'sku': r[3],
                'type': r[4],
                'quantity': r[5],
                'reason': r[6]
            })
        return mapped_logs

if __name__ == "__main__":
    from database.db import init_db
    
    # 0. Initialize database schemas
    init_db()
    
    # Create product manager instance
    prod_mgr = Product()
    
    print("=== STARTING PRODUCT TEST RUN ===")
    
    # Setup clean environment for test keys
    test_barcode_1 = "TEST-BARCODE-999"
    test_barcode_2 = "TEST-LOW-STOCK-999"
    
    existing_1 = prod_mgr.get_product_by_barcode(test_barcode_1)
    if existing_1:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (existing_1[0],))
        prod_mgr.delete_product(existing_1[0])
        
    existing_2 = prod_mgr.get_product_by_barcode(test_barcode_2)
    if existing_2:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (existing_2[0],))
        prod_mgr.delete_product(existing_2[0])
        
    # 1. Add sample product
    print("\n1. Add Sample Product:")
    success = prod_mgr.add_product(
        barcode=test_barcode_1,
        product_name="iPhone 15 Pro Max",
        brand="Apple",
        category="Phones",
        purchase_price=1100.00,
        selling_price=1399.99,
        quantity=12
    )
    print(f"   Success Status: {success}")
    
    # Add a second product that will trigger low stock alert
    prod_mgr.add_product(
        barcode=test_barcode_2,
        product_name="Nokia 105",
        brand="Nokia",
        category="Phones",
        purchase_price=15.00,
        selling_price=25.00,
        quantity=2
    )
    
    # 2. Get all products
    print("\n2. Get All Products (Sorted by product_name ASC):")
    products = prod_mgr.get_all_products()
    print(f"   Total products found: {len(products)}")
    for p in products:
        print(f"   - {p[3]} {p[2]} (Barcode: {p[1]}, Price: ${p[6]}, Qty: {p[7]})")
        
    # 3. Search product
    print("\n3. Search Product (Keyword: 'iPhone'):")
    search_results = prod_mgr.search_products("iPhone")
    for p in search_results:
        print(f"   - Match: {p[3]} {p[2]} (Barcode: {p[1]})")
        
    # 4. Update stock
    print("\n4. Update Stock & Movement History Log:")
    target_product = prod_mgr.get_product_by_barcode(test_barcode_1)
    if target_product:
        p_id = target_product[0]
        print(f"   Initial Stock: {target_product[7]}")
        
        # Test update_stock (Manual Update)
        prod_mgr.update_stock(p_id, 20)
        print(f"   Stock after Manual Update (to 20): {prod_mgr.get_product_by_id(p_id)[7]}")
        
        # Test increase_stock (Stock In)
        prod_mgr.increase_stock(p_id, 5)
        print(f"   Stock after STOCK_IN (+5): {prod_mgr.get_product_by_id(p_id)[7]}")
        
        # Test decrease_stock (Stock Out)
        prod_mgr.decrease_stock(p_id, 3)
        print(f"   Stock after STOCK_OUT (-3): {prod_mgr.get_product_by_id(p_id)[7]}")
        
        # Verify transaction log
        print("   Recent transaction logs:")
        logs = Product.get_inventory_log()
        for log in logs[:3]:
            print(f"     * {log['date']} | {log['brand']} {log['model']} | Action: {log['reason']} | Qty: {log['quantity']} | Dir: {log['type']}")

    # 5. Show low stock products
    print("\n5. Show Low Stock Products (Threshold = 5):")
    low_stock = prod_mgr.get_low_stock_products(threshold=5)
    for p in low_stock:
        print(f"   - Low Stock Alert: {p[3]} {p[2]} has only {p[7]} left.")
        
    # 6. Show product count
    print("\n6. Show Product Count:")
    print(f"   Total Unique Products: {prod_mgr.get_product_count()}")
    
    # 7. Show inventory value
    print("\n7. Show Inventory Value:")
    print(f"   Total Assets Valuation: ${prod_mgr.get_inventory_value():,.2f}")
    
    # Clean up test database records (delete stock_history references first to satisfy Foreign Key constraints)
    t1 = prod_mgr.get_product_by_barcode(test_barcode_1)
    if t1:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (t1[0],))
        prod_mgr.delete_product(t1[0])
        
    t2 = prod_mgr.get_product_by_barcode(test_barcode_2)
    if t2:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (t2[0],))
        prod_mgr.delete_product(t2[0])
        
    print("\n=== TEST RUN COMPLETED successfully ===")
