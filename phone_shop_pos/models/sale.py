# models/sale.py
import sqlite3
import datetime
from database.db import DatabaseManager
from models.product import Product

class Sale:
    """
    Represents a Sale checkout transaction and handles transactional database writes,
    invoice queries, cancel operations, and statistical reports.
    """
    def __init__(self, id=None, invoice_no="", sale_date="", subtotal=0.0, discount=0.0, 
                 total_amount=0.0, payment_method="Cash", customer_id=None):
        """
        Initializes a Sale instance.
        Instantiates DatabaseManager and Product model for operation validations.
        """
        self.db = DatabaseManager()
        self.product_model = Product()
        
        self.id = id
        self.invoice_no = invoice_no
        self.sale_date = sale_date
        self.subtotal = subtotal
        self.discount = discount
        self.total_amount = total_amount
        self.payment_method = payment_method
        self.customer_id = customer_id

    # --- FEATURE 1: generate_invoice_no ---
    def generate_invoice_no(self):
        """
        Generates the next unique invoice number in the format INV-XXXXXX.
        Increments from the latest invoice number in the database.
        
        Returns:
            str: Generated invoice string.
        """
        try:
            query = "SELECT invoice_no FROM sales ORDER BY id DESC LIMIT 1;"
            latest = self.db.fetch_one(query)
            if latest:
                latest_invoice = latest[0]
                try:
                    num_part = int(latest_invoice.split("-")[1])
                    next_num = num_part + 1
                except (IndexError, ValueError):
                    next_num = 1
            else:
                next_num = 1
            return f"INV-{str(next_num).zfill(6)}"
        except Exception as e:
            print(f"Error generating invoice number: {e}")
            return "INV-000001"

    # --- FEATURE 2: create_sale ---
    def create_sale(self, customer_id=None, cart_items=None, discount=0, payment_method="Cash"):
        """
        Processes checkout and inserts sales, sale items, deducts stock, 
        and inserts stock history records in a single transactional block.
        
        Args:
            customer_id (int/None): The ID of the customer.
            cart_items (list): A list of dicts with keys 'product_id' and 'quantity'.
            discount (float): The discount amount.
            payment_method (str): Mode of payment.
            
        Returns:
            dict: Sales metadata on success, or failure message.
        """
        if cart_items is None:
            cart_items = []
            
        # --- Parameter Validations ---
        if not cart_items:
            return {"success": False, "message": "Checkout cart is empty."}
        if discount < 0:
            return {"success": False, "message": "Discount amount cannot be negative."}
        if not payment_method or not payment_method.strip():
            return {"success": False, "message": "Payment method cannot be empty."}
            
        try:
            cursor = self.db.get_cursor()
            
            subtotal = 0.0
            validated_items = []
            
            # Validate products exist and check stock limits
            for item in cart_items:
                product_id = item.get("product_id")
                qty = item.get("quantity")
                
                if qty is None or qty <= 0:
                    return {"success": False, "message": f"Invalid quantity {qty} for product ID {product_id}."}
                
                cursor.execute("SELECT id, selling_price, quantity, product_name FROM products WHERE id = ?;", (product_id,))
                prod = cursor.fetchone()
                if not prod:
                    return {"success": False, "message": f"Product with ID {product_id} does not exist."}
                
                prod_id, price, stock_qty, name = prod
                if stock_qty < qty:
                    return {
                        "success": False, 
                        "message": f"Insufficient stock for '{name}' (ID: {product_id}). Available: {stock_qty}, Checkout: {qty}."
                    }
                
                item_total = price * qty
                subtotal += item_total
                
                validated_items.append({
                    "product_id": product_id,
                    "quantity": qty,
                    "unit_price": price,
                    "total_price": item_total,
                    "previous_qty": stock_qty,
                    "new_qty": stock_qty - qty
                })
                
            total = max(0.0, subtotal - discount)
            invoice_no = self.generate_invoice_no()
            
            # Insert record into sales table
            cursor.execute(
                """
                INSERT INTO sales (invoice_no, customer_id, subtotal, discount, total_amount, payment_method)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (invoice_no, customer_id, subtotal, discount, total, payment_method)
            )
            sale_id = cursor.lastrowid
            
            # Insert items, update quantities, and insert stock histories
            for item in validated_items:
                cursor.execute(
                    """
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (sale_id, item["product_id"], item["quantity"], item["unit_price"], item["total_price"])
                )
                
                cursor.execute(
                    "UPDATE products SET quantity = ? WHERE id = ?;",
                    (item["new_qty"], item["product_id"])
                )
                
                cursor.execute(
                    """
                    INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
                    VALUES (?, ?, ?, 'SALE');
                    """,
                    (item["product_id"], item["previous_qty"], item["new_qty"])
                )
                
            self.db.commit()
            
            return {
                "success": True,
                "sale_id": sale_id,
                "invoice_no": invoice_no,
                "subtotal": subtotal,
                "discount": discount,
                "total": total
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Checkout Transaction failed: {e}")
            return {"success": False, "message": str(e)}

    # --- FEATURE 3: get_sale_by_id ---
    def get_sale_by_id(self, sale_id):
        """Retrieves sale details by database ID."""
        try:
            query = "SELECT * FROM sales WHERE id = ?;"
            return self.db.fetch_one(query, (sale_id,))
        except Exception as e:
            print(f"Error fetching sale by ID: {e}")
            return None

    # --- FEATURE 4: get_sale_by_invoice ---
    def get_sale_by_invoice(self, invoice_no):
        """Retrieves full invoice details by invoice number."""
        try:
            query = "SELECT * FROM sales WHERE invoice_no = ?;"
            return self.db.fetch_one(query, (invoice_no,))
        except Exception as e:
            print(f"Error fetching sale by invoice: {e}")
            return None

    # --- FEATURE 5: get_sale_items ---
    def get_sale_items(self, sale_id):
        """
        Retrieves line items for an invoice, including product names.
        
        Returns:
            list: List of tuples (product_name, quantity, unit_price, total_price).
        """
        try:
            query = """
            SELECT p.product_name, si.quantity, si.unit_price, si.total_price
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ?;
            """
            return self.db.fetch_all(query, (sale_id,))
        except Exception as e:
            print(f"Error fetching sale items: {e}")
            return []

    # --- FEATURE 6: get_all_sales ---
    def get_all_sales(self):
        """Retrieves all sales, sorted newest first."""
        try:
            query = "SELECT * FROM sales ORDER BY sale_date DESC, id DESC;"
            return self.db.fetch_all(query)
        except Exception as e:
            print(f"Error fetching all sales: {e}")
            return []

    # --- FEATURE 7: get_sales_between_dates ---
    def get_sales_between_dates(self, start_date, end_date):
        """Retrieves sales within a specific date range."""
        try:
            query = "SELECT * FROM sales WHERE sale_date BETWEEN ? AND ? ORDER BY sale_date DESC;"
            return self.db.fetch_all(query, (start_date, end_date))
        except Exception as e:
            print(f"Error fetching sales in range: {e}")
            return []

    # --- FEATURE 8: get_daily_sales ---
    def get_daily_sales(self):
        """Retrieves today's sales."""
        try:
            query = "SELECT * FROM sales WHERE date(sale_date) = date('now', 'localtime') ORDER BY sale_date DESC;"
            return self.db.fetch_all(query)
        except Exception as e:
            print(f"Error fetching daily sales: {e}")
            return []

    # --- FEATURE 9: get_monthly_sales ---
    def get_monthly_sales(self):
        """Retrieves current calendar month's sales."""
        try:
            query = """
            SELECT * FROM sales 
            WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m', 'now', 'localtime') 
            ORDER BY sale_date DESC;
            """
            return self.db.fetch_all(query)
        except Exception as e:
            print(f"Error fetching monthly sales: {e}")
            return []

    # --- FEATURE 10: get_total_revenue ---
    def get_total_revenue(self):
        """Calculates total revenue sum of all invoices."""
        try:
            query = "SELECT SUM(total_amount) FROM sales;"
            res = self.db.fetch_one(query)
            return res[0] if res and res[0] is not None else 0.0
        except Exception as e:
            print(f"Error calculating revenue: {e}")
            return 0.0

    # --- FEATURE 11: get_total_sales_count ---
    def get_total_sales_count(self):
        """Retrieves the total invoices count."""
        try:
            query = "SELECT COUNT(*) FROM sales;"
            res = self.db.fetch_one(query)
            return res[0] if res else 0
        except Exception as e:
            print(f"Error getting sales count: {e}")
            return 0

    # --- FEATURE 12: cancel_sale ---
    def cancel_sale(self, sale_id):
        """
        Cancels a sale, restores inventory stocks, logs history, and deletes sale records.
        Uses database transaction handler. Ensures double cancellation prevention.
        
        Returns:
            bool: True on success, False on failure.
        """
        try:
            cursor = self.db.get_cursor()
            
            # Prevent double cancellation check
            cursor.execute("SELECT id FROM sales WHERE id = ?;", (sale_id,))
            if not cursor.fetchone():
                print(f"Cancel failed: Sale ID {sale_id} does not exist or has already been cancelled.")
                return False

            # Fetch items to restore stock quantities
            cursor.execute("SELECT product_id, quantity FROM sale_items WHERE sale_id = ?;", (sale_id,))
            items = cursor.fetchall()
            
            for prod_id, qty in items:
                cursor.execute("SELECT quantity FROM products WHERE id = ?;", (prod_id,))
                row = cursor.fetchone()
                current_qty = row[0] if row else 0
                new_qty = current_qty + qty
                
                # Update product quantity
                cursor.execute("UPDATE products SET quantity = ? WHERE id = ?;", (new_qty, prod_id))
                
                # Log stock history cancel movement
                cursor.execute(
                    """
                    INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
                    VALUES (?, ?, ?, 'SALE_CANCELLED');
                    """,
                    (prod_id, current_qty, new_qty)
                )
                
            # Delete sale items
            cursor.execute("DELETE FROM sale_items WHERE sale_id = ?;", (sale_id,))
            
            # Delete sale record
            cursor.execute("DELETE FROM sales WHERE id = ?;", (sale_id,))
            
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            print(f"Cancel transaction failed: {e}")
            return False

    # --- FEATURE 13: get_top_selling_products ---
    def get_top_selling_products(self, limit=10):
        """
        Retrieves top selling products sorted by quantity sold descending.
        
        Returns:
            list: List of tuples (product_name, total_qty_sold).
        """
        try:
            query = """
            SELECT p.product_name, SUM(si.quantity) as total_quantity_sold
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            GROUP BY si.product_id
            ORDER BY total_quantity_sold DESC
            LIMIT ?;
            """
            return self.db.fetch_all(query, (limit,))
        except Exception as e:
            print(f"Error fetching top products: {e}")
            return []

    # --- FEATURE 14: get_customer_sales ---
    def get_customer_sales(self, customer_id):
        """Retrieves all invoices for a given customer."""
        try:
            query = "SELECT * FROM sales WHERE customer_id = ? ORDER BY sale_date DESC;"
            return self.db.fetch_all(query, (customer_id,))
        except Exception as e:
            print(f"Error fetching customer sales: {e}")
            return []

    # --- FEATURE 15: get_invoice_summary ---
    def get_invoice_summary(self, invoice_no):
        """
        Retrieves a summary of an invoice including the customer name and total item count.
        
        Returns:
            tuple/None: (invoice_no, customer_name, sale_date, subtotal, discount, total_amount, payment_method, item_count)
        """
        try:
            query = """
            SELECT s.invoice_no, COALESCE(c.customer_name, 'Walk-in Guest') as customer_name, 
                   s.sale_date, s.subtotal, s.discount, s.total_amount, s.payment_method, 
                   COALESCE(SUM(si.quantity), 0) as item_count
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.invoice_no = ?
            GROUP BY s.id;
            """
            return self.db.fetch_one(query, (invoice_no,))
        except Exception as e:
            print(f"Error fetching invoice summary: {e}")
            return None

    # --- FEATURE 16: get_today_revenue ---
    def get_today_revenue(self):
        """
        Calculates total revenue sum for today's sales.
        
        Returns:
            float: Today's revenue.
        """
        try:
            query = "SELECT SUM(total_amount) FROM sales WHERE date(sale_date) = date('now', 'localtime');"
            res = self.db.fetch_one(query)
            return res[0] if res and res[0] is not None else 0.0
        except Exception as e:
            print(f"Error getting today's revenue: {e}")
            return 0.0

    # --- FEATURE 17: get_month_revenue ---
    def get_month_revenue(self):
        """
        Calculates total revenue sum for the current month's sales.
        
        Returns:
            float: Current month's revenue.
        """
        try:
            query = """
            SELECT SUM(total_amount) FROM sales 
            WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m', 'now', 'localtime');
            """
            res = self.db.fetch_one(query)
            return res[0] if res and res[0] is not None else 0.0
        except Exception as e:
            print(f"Error getting current month's revenue: {e}")
            return 0.0

    # --- Backwards Compatibility Wrapper ---
    @staticmethod
    def get_all():
        """Static wrapper for UI compatibility. Returns all sale records."""
        s = Sale()
        return s.get_all_sales()


class SaleItem:
    """
    Represents an item itemized in a Sale checkout order.
    """
    def __init__(self, id=None, sale_id=None, product_id=None, quantity=1, unit_price=0.0, total_price=0.0):
        self.id = id
        self.sale_id = sale_id
        self.product_id = product_id
        self.quantity = quantity
        self.unit_price = unit_price
        self.total_price = total_price


class Imei:
    """
    Manages Hardware Unique IMEI Serialization numbers on products.
    """
    @staticmethod
    def get_by_product(product_id, status=None):
        """Fetches registered IMEIs for a product type, filtered by status."""
        db = DatabaseManager()
        cursor = db.get_cursor()
        
        cursor.execute("SELECT product_name, brand FROM products WHERE id = ?;", (product_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return []
        prod_name, brand = row[0], row[1]
        
        if status == 'available':
            cursor.execute(
                "SELECT barcode as imei, id, created_at as added_date FROM products WHERE product_name = ? AND brand = ? AND quantity > 0 AND length(barcode) >= 8;",
                (prod_name, brand)
            )
        elif status == 'sold':
            cursor.execute(
                "SELECT barcode as imei, id, created_at as added_date FROM products WHERE product_name = ? AND brand = ? AND quantity == 0 AND length(barcode) >= 8;",
                (prod_name, brand)
            )
        else:
            cursor.execute(
                "SELECT barcode as imei, id, created_at as added_date FROM products WHERE product_name = ? AND brand = ? AND length(barcode) >= 8;",
                (prod_name, brand)
            )
            
        rows = cursor.fetchall()
        mapped = []
        for r in rows:
            mapped.append({
                'imei': r[0],
                'id': r[1],
                'added_date': r[2]
            })
        db.close()
        return mapped

    @staticmethod
    def get_all(status=None):
        """Fetches all registered IMEIs, optionally filtered by status."""
        db = DatabaseManager()
        if status == 'available':
            query = """
            SELECT barcode as imei, brand, product_name as model, barcode as sku, 'available' as status, created_at as added_date, NULL as sale_id, NULL as sold_date
            FROM products
            WHERE quantity > 0 AND length(barcode) >= 8
            ORDER BY created_at DESC;
            """
        else:
            query = """
            SELECT p.barcode as imei, p.brand, p.product_name as model, p.barcode as sku, 'sold' as status, p.created_at as added_date, s.invoice_no as sale_id, s.sale_date as sold_date
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE p.quantity == 0 AND length(p.barcode) >= 8
            ORDER BY s.sale_date DESC;
            """
        rows = db.fetch_all(query)
        mapped = []
        for r in rows:
            mapped.append({
                'imei': r[0],
                'brand': r[1],
                'model': r[2],
                'sku': r[3],
                'status': r[4],
                'added_date': r[5],
                'sale_id': r[6],
                'sold_date': r[7]
            })
        db.close()
        return mapped

    @staticmethod
    def add(imei, product_id, date_str):
        """Registers a new IMEI for a product. Inserts a new product instance with qty=1."""
        db = DatabaseManager()
        cursor = db.get_cursor()
        success = False
        try:
            cursor.execute("SELECT product_name, brand, category, purchase_price, selling_price FROM products WHERE id = ?;", (product_id,))
            row = cursor.fetchone()
            if row:
                prod_name, brand, category, purchase_price, selling_price = row[0], row[1], row[2], row[3], row[4]
                
                cursor.execute(
                    """
                    INSERT INTO products (barcode, product_name, brand, category, purchase_price, selling_price, quantity, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?);
                    """,
                    (imei.strip(), prod_name, brand, category, purchase_price, selling_price, date_str)
                )
                new_product_id = cursor.lastrowid
                
                cursor.execute(
                    """
                    INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type, updated_at)
                    VALUES (?, 0, 1, ?, ?);
                    """,
                    (new_product_id, f"IMEI Registration ({imei.strip()})", date_str)
                )
                db.commit()
                success = True
        except sqlite3.Error as e:
            print("IMEI insert failed:", e)
            db.rollback()
            success = False
        db.close()
        return success

    @staticmethod
    def get_details(imei):
        """Searches single IMEI details, including phone info and transaction invoices if sold."""
        db = DatabaseManager()
        query = """
        SELECT p.barcode as imei, 
               (CASE WHEN p.quantity > 0 THEN 'available' ELSE 'sold' END) as status,
               p.created_at as added_date,
               s.sale_date as sold_date, s.invoice_no as sale_id,
               p.brand, p.product_name as model, p.barcode as sku,
               s.sale_date, 'system' as cashier, c.customer_name, c.phone as customer_phone
        FROM products p
        LEFT JOIN sale_items si ON p.id = si.product_id
        LEFT JOIN sales s ON si.sale_id = s.id
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE UPPER(p.barcode) = UPPER(?);
        """
        r = db.fetch_one(query, (imei.strip(),))
        db.close()
        if not r:
            return None
        return {
            'imei': r[0],
            'status': r[1],
            'added_date': r[2],
            'sold_date': r[3],
            'sale_id': r[4],
            'brand': r[5],
            'model': r[6],
            'sku': r[7],
            'sale_date': r[8],
            'cashier': r[9],
            'customer_name': r[10],
            'customer_phone': r[11]
        }

if __name__ == "__main__":
    from database.db import init_db
    from models.customer import Customer
    
    init_db()
    
    prod_mgr = Product()
    cust_mgr = Customer()
    sale_mgr = Sale()
    
    print("=== STARTING COMPLETE SALE MODEL TEST RUN ===")
    
    # 0. Set up temporary product and customer
    test_barcode = "SALE-TEST-PROD-999"
    existing_p = prod_mgr.get_product_by_barcode(test_barcode)
    if existing_p:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (existing_p[0],))
        prod_mgr.delete_product(existing_p[0])
        
    prod_mgr.add_product(
        barcode=test_barcode,
        product_name="Super Phone X",
        brand="BrandZ",
        category="Phones",
        purchase_price=800.00,
        selling_price=1000.00,
        quantity=10
    )
    product = prod_mgr.get_product_by_barcode(test_barcode)
    product_id = product[0]
    initial_stock = product[7]
    
    test_phone = "9998887777"
    existing_c = cust_mgr.get_customer_by_phone(test_phone)
    if existing_c:
        cust_mgr.db.execute("DELETE FROM customers WHERE id = ?;", (existing_c[0],))
    cust_mgr.add_customer("Alpha Tester", test_phone, "Coimbatore Road")
    customer = cust_mgr.get_customer_by_phone(test_phone)
    customer_id = customer[0]
    
    # Test 1: Invoice generation
    print("\n1. Testing Invoice Generation:")
    next_inv = sale_mgr.generate_invoice_no()
    print(f"   Next Generated Invoice: {next_inv}")
    
    # Test 2: Sale creation
    print("\n2. Testing Sale Creation:")
    cart = [
        {"product_id": product_id, "quantity": 3}
    ]
    sale_res = sale_mgr.create_sale(
        customer_id=customer_id,
        cart_items=cart,
        discount=100.00,
        payment_method="Cash"
    )
    print(f"   Success Status: {sale_res['success']}")
    if sale_res['success']:
        print(f"   Invoice:   {sale_res['invoice_no']}")
        print(f"   Subtotal:  ${sale_res['subtotal']:.2f}")
        print(f"   Discount:  ${sale_res['discount']:.2f}")
        print(f"   Total:     ${sale_res['total']:.2f}")
        
    # Test 3: Revenue calculations
    print("\n3. Testing Revenue Calculations:")
    print(f"   Today Revenue:   ${sale_mgr.get_today_revenue():,.2f}")
    print(f"   Month Revenue:   ${sale_mgr.get_month_revenue():,.2f}")
    print(f"   Total Revenue:   ${sale_mgr.get_total_revenue():,.2f}")
    print(f"   Total Sales:     {sale_mgr.get_total_sales_count()}")
    
    # Test 4: Product stock deduction
    print("\n4. Testing Product Stock Deduction:")
    stock_after = prod_mgr.get_product_by_id(product_id)[7]
    print(f"   Stock after sale: {stock_after} (Expected: {initial_stock - 3})")
    
    # Test 5: Invoice lookup
    print("\n5. Testing Invoice Lookup & Summary:")
    if sale_res['success']:
        summary = sale_mgr.get_invoice_summary(sale_res['invoice_no'])
        if summary:
            print(f"   Invoice No:     {summary[0]}")
            print(f"   Customer Name:  {summary[1]}")
            print(f"   Sale Date:      {summary[2]}")
            print(f"   Subtotal:       ${summary[3]:.2f}")
            print(f"   Discount:       ${summary[4]:.2f}")
            print(f"   Total Amount:   ${summary[5]:.2f}")
            print(f"   Payment Mode:   {summary[6]}")
            print(f"   Total Items:    {summary[7]}")
            
    # Test 6: Customer sales lookup
    print("\n6. Testing Customer Sales Lookup:")
    cust_sales = sale_mgr.get_customer_sales(customer_id)
    print(f"   Invoices for customer '{customer[1]}': {len(cust_sales)}")
    for cs in cust_sales:
        print(f"     * Invoice: {cs[1]} | Total: ${cs[5]:.2f} | Date: {cs[7]}")
        
    # Test 7: Top-selling products
    print("\n7. Testing Top Selling Products:")
    top_prods = sale_mgr.get_top_selling_products(limit=5)
    for tp in top_prods:
        print(f"   - Product: {tp[0]} | Quantity Sold: {tp[1]}")
        
    # Test 8: Sale cancellation & stock restoration verification
    print("\n8. Testing Sale Cancellation:")
    if sale_res['success']:
        cancelled = sale_mgr.cancel_sale(sale_res['sale_id'])
        print(f"   Cancellation Status: {cancelled}")
        
        # Double cancellation prevention check
        double_cancel = sale_mgr.cancel_sale(sale_res['sale_id'])
        print(f"   Double Cancellation Status (should fail): {double_cancel}")
        
        stock_restored = prod_mgr.get_product_by_id(product_id)[7]
        print(f"   Stock restored: {stock_restored} (Expected: {initial_stock})")
        
    # Clean up test database records (delete stock histories first)
    prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (product_id,))
    prod_mgr.delete_product(product_id)
    cust_mgr.db.execute("DELETE FROM customers WHERE id = ?;", (customer_id,))
    
    print("\n=== COMPLETE SALE TEST RUN COMPLETED successfully ===")
