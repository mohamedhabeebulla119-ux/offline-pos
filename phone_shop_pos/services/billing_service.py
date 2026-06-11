# services/billing_service.py
import os
import json
import time
import datetime
import sqlite3
from database.db import get_connection
from models.sale import Sale
from models.product import Product
from models.customer import Customer

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

DEFAULT_SETTINGS = {
    "shopName": "Offline Phone Shop",
    "shopAddress": "123 Phone Plaza, Main Road",
    "shopPhone": "+91 9876543210",
    "shopEmail": "contact@phoneshop.com",
    "taxRate": 18.0,
    "printerWidth": "80mm"
}

class BillingService:
    """
    Acts as the business logic layer between the UI and database models for 
    handling checkout registers, cart updates, receipts, settings, and dashboards.
    """
    
    # --- FEATURE 1: create_invoice ---
    def create_invoice(self, customer_id, cart_items, discount, payment_method):
        """
        Creates a sales invoice by invoking the Sale transaction model.
        
        Args:
            customer_id (int/None): ID of the customer.
            cart_items (list): Checkout list of dictionaries with product ID and quantity.
            discount (float): Total discount applied.
            payment_method (str): Mode of payment.
            
        Returns:
            dict: Checkout success information, or error message.
        """
        try:
            sale_mgr = Sale()
            return sale_mgr.create_sale(
                customer_id=customer_id,
                cart_items=cart_items,
                discount=discount,
                payment_method=payment_method
            )
        except Exception as e:
            print(f"Error creating invoice: {e}")
            return {"success": False, "message": str(e)}

    # --- FEATURE 2: scan_barcode ---
    def scan_barcode(self, barcode):
        """
        Scans a barcode to search for a product and check its stock availability.
        
        Args:
            barcode (str): The product barcode.
            
        Returns:
            dict: Product details on success, or failure message.
        """
        try:
            prod_mgr = Product()
            product_row = prod_mgr.get_product_by_barcode(barcode)
            if not product_row:
                return {"success": False, "message": f"Product with barcode '{barcode}' was not found."}
                
            # Mapping columns by indices: 0:id, 1:barcode, 2:product_name, 3:brand, 4:category, 5:purchase, 6:selling, 7:quantity, 8:created_at
            stock_qty = product_row[7]
            if stock_qty <= 0:
                return {"success": False, "message": f"Product '{product_row[2]}' is currently out of stock."}
                
            product_data = {
                "id": product_row[0],
                "barcode": product_row[1],
                "product_name": product_row[2],
                "brand": product_row[3],
                "category": product_row[4],
                "purchase_price": product_row[5],
                "selling_price": product_row[6],
                "quantity": product_row[7],
                "created_at": product_row[8]
            }
            return {"success": True, "product": product_data}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --- FEATURE 3: add_item_to_cart ---
    def add_item_to_cart(self, cart, barcode, quantity):
        """
        Adds a product to the cart. If the item is already present, it merges the quantities.
        Validates stock limits and calculates line totals.
        
        Args:
            cart (list): Current shopping cart list.
            barcode (str): Product barcode.
            quantity (int): Quantity to add.
            
        Returns:
            dict: Success status message.
        """
        try:
            scan_res = self.scan_barcode(barcode)
            if not scan_res["success"]:
                return {"success": False, "message": scan_res["message"]}
                
            prod = scan_res["product"]
            product_id = prod["id"]
            stock_qty = prod["quantity"]
            price = prod["selling_price"]
            
            # Check for existing item in cart
            existing_item = None
            for item in cart:
                if item.get("product_id") == product_id:
                    existing_item = item
                    break
                    
            requested_qty = quantity
            if existing_item:
                requested_qty += existing_item["quantity"]
                
            if requested_qty > stock_qty:
                return {
                    "success": False, 
                    "message": f"Cannot add. Available stock: {stock_qty}, Requested: {requested_qty}."
                }
                
            if existing_item:
                existing_item["quantity"] = requested_qty
                existing_item["total_price"] = requested_qty * price
            else:
                cart.append({
                    "product_id": product_id,
                    "barcode": prod["barcode"],
                    "product_name": prod["product_name"],
                    "brand": prod["brand"],
                    "selling_price": price,
                    "quantity": quantity,
                    "total_price": quantity * price
                })
                
            return {"success": True, "message": "Product added to cart successfully."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --- FEATURE 4: remove_item_from_cart ---
    def remove_item_from_cart(self, cart, product_id):
        """
        Removes an item from the cart by its product ID.
        
        Returns:
            bool: True if removed, False otherwise.
        """
        try:
            for idx, item in enumerate(cart):
                if item.get("product_id") == product_id:
                    cart.pop(idx)
                    return True
            return False
        except Exception as e:
            print(f"Error removing item from cart: {e}")
            return False

    # --- FEATURE 5: update_cart_quantity ---
    def update_cart_quantity(self, cart, product_id, quantity):
        """
        Updates the checkout quantity of a cart item after verifying stock levels.
        
        Returns:
            dict: Status confirmation message.
        """
        if quantity <= 0:
            removed = self.remove_item_from_cart(cart, product_id)
            if removed:
                return {"success": True, "message": "Item removed from cart."}
            return {"success": False, "message": "Item was not found in cart."}
            
        try:
            prod_mgr = Product()
            prod_row = prod_mgr.get_product_by_id(product_id)
            if not prod_row:
                return {"success": False, "message": "Product not found."}
                
            stock_qty = prod_row[7]
            if quantity > stock_qty:
                return {"success": False, "message": f"Insufficient stock. Available: {stock_qty}."}
                
            for item in cart:
                if item.get("product_id") == product_id:
                    item["quantity"] = quantity
                    item["total_price"] = quantity * item["selling_price"]
                    return {"success": True, "message": "Cart quantity updated."}
                    
            return {"success": False, "message": "Product not in cart."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --- FEATURE 6: calculate_cart_total ---
    def calculate_cart_total(self, cart, discount=0):
        """
        Calculates subtotal, discount, grand total, and item count of cart.
        
        Returns:
            dict: Totals summary.
        """
        try:
            subtotal = sum(item["total_price"] for item in cart)
            item_count = sum(item["quantity"] for item in cart)
            grand_total = max(0.0, subtotal - discount)
            return {
                "subtotal": subtotal,
                "discount": discount,
                "grand_total": grand_total,
                "item_count": item_count
            }
        except Exception as e:
            print(f"Error calculating totals: {e}")
            return {
                "subtotal": 0.0,
                "discount": discount,
                "grand_total": 0.0,
                "item_count": 0
            }

    # --- FEATURE 7: generate_invoice_data ---
    def generate_invoice_data(self, invoice_no):
        """
        Retrieves database structures and generates invoice printing fields.
        
        Returns:
            dict/None: Summary structure or None.
        """
        try:
            sale_mgr = Sale()
            cust_mgr = Customer()
            settings = self.get_shop_settings()
            
            s = sale_mgr.get_sale_by_invoice(invoice_no)
            if not s:
                return None
                
            sale_id, inv_no, customer_id, subtotal, discount, total, pay_method, sale_date = s
            
            customer_name = "Walk-in Guest"
            customer_phone = ""
            if customer_id:
                c = cust_mgr.get_customer_by_id(customer_id)
                if c:
                    customer_name = c[1]
                    customer_phone = c[2]
                    
            items = sale_mgr.get_sale_items(sale_id)
            products_list = []
            for item in items:
                products_list.append({
                    "product_name": item[0],
                    "quantity": item[1],
                    "unit_price": item[2],
                    "total_price": item[3]
                })
                
            return {
                "shop_name": settings.get("shopName", "Offline Phone Shop"),
                "invoice_no": inv_no,
                "date": sale_date,
                "customer": {
                    "name": customer_name,
                    "phone": customer_phone
                },
                "products": products_list,
                "subtotal": subtotal,
                "discount": discount,
                "total": total
            }
        except Exception as e:
            print(f"Error generating invoice data: {e}")
            return None

    # --- FEATURE 8: cancel_invoice ---
    def cancel_invoice(self, sale_id):
        """Cancels invoice and restores inventory."""
        try:
            sale_mgr = Sale()
            return sale_mgr.cancel_sale(sale_id)
        except Exception as e:
            print(f"Error cancelling invoice: {e}")
            return False

    # --- FEATURE 9: search_customer ---
    def search_customer(self, phone):
        """Retrieves customer registry directory by phone."""
        try:
            cust_mgr = Customer()
            c = cust_mgr.get_customer_by_phone(phone)
            if not c:
                return None
            return {
                "id": c[0],
                "customer_name": c[1],
                "phone": c[2],
                "address": c[3],
                "created_at": c[4]
            }
        except Exception as e:
            print(f"Error searching customer: {e}")
            return None

    # --- FEATURE 10: create_customer ---
    def create_customer(self, customer_name, phone, address):
        """Creates customer profile."""
        try:
            cust_mgr = Customer()
            success = cust_mgr.add_customer(customer_name, phone, address)
            if success:
                c = cust_mgr.get_customer_by_phone(phone)
                if c:
                    return {
                        "success": True,
                        "customer": {
                            "id": c[0],
                            "customer_name": c[1],
                            "phone": c[2],
                            "address": c[3],
                            "created_at": c[4]
                        }
                    }
            return {"success": False, "message": "Failed to create customer profile. Phone might exist."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # --- FEATURE 11: get_dashboard_summary ---
    def get_dashboard_summary(self):
        """Retrieves dashboard KPIs."""
        try:
            sale_mgr = Sale()
            prod_mgr = Product()
            cust_mgr = Customer()
            
            return {
                "today_revenue": sale_mgr.get_today_revenue(),
                "month_revenue": sale_mgr.get_month_revenue(),
                "total_sales": sale_mgr.get_total_sales_count(),
                "product_count": prod_mgr.get_product_count(),
                "customer_count": cust_mgr.get_customer_count()
            }
        except Exception as e:
            print(f"Error getting dashboard KPIs: {e}")
            return {
                "today_revenue": 0.0,
                "month_revenue": 0.0,
                "total_sales": 0,
                "product_count": 0,
                "customer_count": 0
            }

    # --- Backwards Compatibility Configuration Management Helpers ---

    @staticmethod
    def get_shop_settings():
        """Fetches shop configurations from local config.json file."""
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2)
            return DEFAULT_SETTINGS
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return DEFAULT_SETTINGS

    @staticmethod
    def save_shop_settings(settings_dict):
        """Saves shop configurations to config.json file."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(settings_dict, f, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def checkout(cart_items, subtotal, discount, tax, total, payment_method, customer_id, cashier):
        """Processes checkout order transaction in a single database transaction block."""
        conn = get_connection()
        cursor = conn.cursor()
        success = False
        invoice_number = f"INV-{int(time.time())}"
        date_str = time.strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            cursor.execute(
                """
                INSERT INTO sales (invoice_no, customer_id, subtotal, discount, total_amount, payment_method)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (invoice_number, customer_id, subtotal, discount, total, payment_method)
            )
            sale_id = cursor.lastrowid
            
            for item in cart_items:
                product = item['product']
                qty = item['quantity']
                price = item['price']
                total_price = price * qty
                
                cursor.execute(
                    """
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (sale_id, product.id, qty, price, total_price)
                )
                
                cursor.execute("SELECT quantity FROM products WHERE id = ?;", (product.id,))
                row = cursor.fetchone()
                previous_qty = row[0] if row else 0
                new_qty = max(0, previous_qty - qty)
                
                cursor.execute("UPDATE products SET quantity = ? WHERE id = ?;", (new_qty, product.id))
                
                cursor.execute(
                    """
                    INSERT INTO stock_history (product_id, previous_qty, new_qty, action_type)
                    VALUES (?, ?, ?, ?);
                    """,
                    (product.id, previous_qty, new_qty, f"Sales Invoice #{invoice_number}")
                )
                
            conn.commit()
            success = True
            BillingService.save_text_receipt(invoice_number, date_str, cart_items, subtotal, discount, tax, total, payment_method, customer_id, cashier)
        except sqlite3.Error as e:
            print("Checkout failed:", e)
            conn.rollback()
            success = False
            invoice_number = None
        finally:
            conn.close()
            
        return success, invoice_number

    @staticmethod
    def save_text_receipt(invoice_number, date_str, cart_items, subtotal, discount, tax, total, payment_method, customer_id, cashier):
        """Generates a plain-text invoice file and writes to receipts/ folder."""
        folder = "receipts"
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        settings = BillingService.get_shop_settings()
        shop_name = settings.get('shopName', 'Phone Shop')
        shop_addr = settings.get('shopAddress', 'Store Address')
        shop_phone = settings.get('shopPhone', 'Phone Number')
        
        cust_info = "Customer: Walk-in Guest"
        if customer_id:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT customer_name as name, phone FROM customers WHERE id = ?;", (customer_id,))
            c = cursor.fetchone()
            conn.close()
            if c:
                cust_info = f"Customer: {c['name']}\nPhone: {c['phone']}"
                
        receipt = []
        receipt.append("="*40)
        receipt.append(shop_name.center(40))
        receipt.append(shop_addr.center(40))
        receipt.append(f"Phone: {shop_phone}".center(40))
        receipt.append("="*40)
        receipt.append(f"Invoice: {invoice_number}")
        receipt.append(f"Date: {date_str}")
        receipt.append(f"Cashier: {cashier}")
        receipt.append(cust_info)
        receipt.append("-"*40)
        
        for item in cart_items:
            prod = item['product']
            name = f"{prod.brand} {prod.product_name}"
            receipt.append(f"{name:<28} {item['quantity']:>3}x")
            receipt.append(f"  @{item['price']:<15.2f} Total: {item['price']*item['quantity']:>15.2f}")
            if item['imeis']:
                receipt.append(f"  IMEI(s): {', '.join(item['imeis'])}")
                
        receipt.append("-"*40)
        receipt.append(f"Subtotal: {subtotal:>30.2f}")
        if discount > 0:
            receipt.append(f"Discount: -{discount:>29.2f}")
        receipt.append(f"GST ({settings.get('taxRate', '18.0')}%): {tax:>30.2f}")
        receipt.append("="*40)
        receipt.append(f"GRAND TOTAL: {total:>27.2f}")
        receipt.append(f"Payment Mode: {payment_method:>26}")
        receipt.append("="*40)
        receipt.append("Thank you for your purchase!".center(40))
        receipt.append("Please preserve invoice for warranty.".center(40))
        receipt.append("="*40)
        
        filepath = os.path.join(folder, f"{invoice_number}.txt")
        with open(filepath, "w") as f:
            f.write("\n".join(receipt))

    @staticmethod
    def reprint_receipt_file(invoice_number):
        """Opens receipt file in default text viewer/notepad on system."""
        filepath = os.path.join("receipts", f"{invoice_number}.txt")
        if os.path.exists(filepath):
            absolute_path = os.path.abspath(filepath)
            os.startfile(absolute_path)
            return True
        return False

if __name__ == "__main__":
    from database.db import init_db
    
    init_db()
    
    prod_mgr = Product()
    cust_mgr = Customer()
    billing_srv = BillingService()
    
    print("=== STARTING BILLING SERVICE TEST RUN ===")
    
    # 0. Setup test values
    test_barcode = "BILLING-TEST-BARCODE"
    existing_p = prod_mgr.get_product_by_barcode(test_barcode)
    if existing_p:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (existing_p[0],))
        prod_mgr.delete_product(existing_p[0])
        
    prod_mgr.add_product(
        barcode=test_barcode,
        product_name="Billing Demo Phone",
        brand="BrandX",
        category="Phones",
        purchase_price=300.00,
        selling_price=450.00,
        quantity=5
    )
    product = prod_mgr.get_product_by_barcode(test_barcode)
    product_id = product[0]
    
    # 1. Scan barcode
    print("\n1. Testing Scan Barcode:")
    scan_res = billing_srv.scan_barcode(test_barcode)
    print(f"   Success Status: {scan_res['success']}")
    if scan_res['success']:
        print(f"   Product: {scan_res['product']['brand']} {scan_res['product']['product_name']} | Price: ${scan_res['product']['selling_price']}")
        
    # 2. Add items to cart
    print("\n2. Testing Add Items to Cart:")
    cart = []
    add_res_1 = billing_srv.add_item_to_cart(cart, test_barcode, 2)
    print(f"   Add Qty 2 Success: {add_res_1['success']}")
    # Merge quantity
    add_res_2 = billing_srv.add_item_to_cart(cart, test_barcode, 1)
    print(f"   Merge Qty 1 Success: {add_res_2['success']}")
    print(f"   Cart Items: {len(cart)} | Qty in cart: {cart[0]['quantity']} | Line Total: ${cart[0]['total_price']:.2f}")
    
    # 3. Calculate total
    print("\n3. Testing Calculate Total:")
    totals = billing_srv.calculate_cart_total(cart, discount=25.00)
    print(f"   Subtotal:    ${totals['subtotal']:.2f}")
    print(f"   Discount:    ${totals['discount']:.2f}")
    print(f"   Grand Total: ${totals['grand_total']:.2f}")
    print(f"   Item Count:  {totals['item_count']}")
    
    # 4. Create invoice
    print("\n4. Testing Create Invoice:")
    # Format cart items for Sale model (list of product_id and quantity)
    formatted_cart = [{"product_id": item["product_id"], "quantity": item["quantity"]} for item in cart]
    invoice_res = billing_srv.create_invoice(
        customer_id=None,
        cart_items=formatted_cart,
        discount=25.00,
        payment_method="UPI / QR Code"
    )
    print(f"   Success Status: {invoice_res['success']}")
    if invoice_res['success']:
        invoice_no = invoice_res['invoice_no']
        sale_id = invoice_res['sale_id']
        print(f"   Invoice Created: {invoice_no} | Sale ID: {sale_id}")
        
        # 5. Generate invoice data
        print("\n5. Testing Generate Invoice Data:")
        inv_data = billing_srv.generate_invoice_data(invoice_no)
        if inv_data:
            print(f"   Shop:       {inv_data['shop_name']}")
            print(f"   Invoice No: {inv_data['invoice_no']}")
            print(f"   Date:       {inv_data['date']}")
            print(f"   Customer:   {inv_data['customer']['name']}")
            print(f"   Total:      ${inv_data['total']:.2f}")
            for p in inv_data['products']:
                print(f"     * Product: {p['product_name']} | Qty: {p['quantity']} | Total: ${p['total_price']:.2f}")
                
        # 6. Cancel invoice
        print("\n6. Testing Cancel Invoice:")
        cancelled = billing_srv.cancel_invoice(sale_id)
        print(f"   Cancellation Status: {cancelled}")
        
    # Clean up test database records (delete stock histories first)
    prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (product_id,))
    prod_mgr.delete_product(product_id)
    
    print("\n=== BILLING SERVICE TEST RUN COMPLETED successfully ===")
