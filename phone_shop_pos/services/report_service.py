# services/report_service.py
import os
import datetime
import pandas as pd
import openpyxl
from database.db import get_connection
from models.sale import Sale
from models.product import Product
from models.customer import Customer

class ReportService:
    """
    Business layer service to generate financial, sales, inventory, and customer reports,
    export data to Excel sheets, and compile dashboard metrics.
    """

    # --- FEATURE 1: daily_sales_report ---
    def daily_sales_report(self):
        """
        Generates daily sales report details.
        
        Returns:
            dict: total sales count, total revenue, total discounts, and invoices list.
        """
        try:
            sale_mgr = Sale()
            sales = sale_mgr.get_daily_sales()
            total_sales_count = len(sales)
            total_revenue = sum(s[5] for s in sales)
            total_discounts = sum(s[4] for s in sales)
            
            invoices_list = []
            for s in sales:
                invoices_list.append({
                    "id": s[0],
                    "invoice_no": s[1],
                    "customer_id": s[2],
                    "subtotal": s[3],
                    "discount": s[4],
                    "total_amount": s[5],
                    "payment_method": s[6],
                    "sale_date": s[7]
                })
            
            return {
                "total_sales_count": total_sales_count,
                "total_revenue": total_revenue,
                "total_discounts": total_discounts,
                "invoices": invoices_list
            }
        except Exception as e:
            print(f"Error generating daily sales report: {e}")
            return {
                "total_sales_count": 0,
                "total_revenue": 0.0,
                "total_discounts": 0.0,
                "invoices": []
            }

    # --- FEATURE 2: monthly_sales_report ---
    def monthly_sales_report(self):
        """
        Generates monthly sales report details.
        
        Returns:
            dict: monthly revenue, invoice count, and average invoice value.
        """
        try:
            sale_mgr = Sale()
            sales = sale_mgr.get_monthly_sales()
            invoice_count = len(sales)
            monthly_revenue = sum(s[5] for s in sales)
            average_invoice_value = monthly_revenue / invoice_count if invoice_count > 0 else 0.0
            
            return {
                "monthly_revenue": monthly_revenue,
                "invoice_count": invoice_count,
                "average_invoice_value": average_invoice_value
            }
        except Exception as e:
            print(f"Error generating monthly sales report: {e}")
            return {
                "monthly_revenue": 0.0,
                "invoice_count": 0,
                "average_invoice_value": 0.0
            }

    # --- FEATURE 3: sales_between_dates ---
    def sales_between_dates(self, start_date, end_date):
        """
        Retrieves sales records between the specified date range.
        
        Args:
            start_date (str): Start timestamp (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
            end_date (str): End timestamp (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
            
        Returns:
            list: List of sales dictionaries.
        """
        try:
            sale_mgr = Sale()
            sales = sale_mgr.get_sales_between_dates(start_date, end_date)
            sales_data = []
            for s in sales:
                sales_data.append({
                    "id": s[0],
                    "invoice_no": s[1],
                    "customer_id": s[2],
                    "subtotal": s[3],
                    "discount": s[4],
                    "total_amount": s[5],
                    "payment_method": s[6],
                    "sale_date": s[7]
                })
            return sales_data
        except Exception as e:
            print(f"Error generating sales between dates: {e}")
            return []

    # --- FEATURE 4: top_selling_products ---
    def top_selling_products(self, limit=10):
        """
        Retrieves top selling products based on total quantity sold.
        
        Args:
            limit (int): Max number of items to return.
            
        Returns:
            list: List of products with keys 'product_name' and 'quantity_sold'.
        """
        try:
            sale_mgr = Sale()
            top_prods = sale_mgr.get_top_selling_products(limit=limit)
            return [
                {
                    "product_name": tp[0],
                    "quantity_sold": tp[1]
                }
                for tp in top_prods
            ]
        except Exception as e:
            print(f"Error generating top selling products: {e}")
            return []

    # --- FEATURE 5: low_stock_report ---
    def low_stock_report(self, threshold=5):
        """
        Retrieves products below the inventory minimum threshold.
        
        Args:
            threshold (int): Minimum inventory levels limit.
            
        Returns:
            list: List of product records.
        """
        try:
            prod_mgr = Product()
            low_stock = prod_mgr.get_low_stock_products(threshold=threshold)
            return [
                {
                    "barcode": p[1],
                    "product_name": p[2],
                    "brand": p[3],
                    "category": p[4],
                    "current_quantity": p[7]
                }
                for p in low_stock
            ]
        except Exception as e:
            print(f"Error generating low stock report: {e}")
            return []

    # --- FEATURE 6: inventory_report ---
    def inventory_report(self):
        """
        Generates inventory metrics report.
        
        Returns:
            dict: total unique product types count, valuation, and aggregate stock quantity.
        """
        try:
            prod_mgr = Product()
            product_count = prod_mgr.get_product_count()
            inventory_value = prod_mgr.get_inventory_value()
            
            # Aggregate stock quantities from products catalog
            cursor = prod_mgr.db.get_cursor()
            cursor.execute("SELECT SUM(quantity) FROM products;")
            row = cursor.fetchone()
            stock_quantities = row[0] if row and row[0] is not None else 0
            
            return {
                "product_count": product_count,
                "inventory_value": inventory_value,
                "stock_quantities": stock_quantities
            }
        except Exception as e:
            print(f"Error generating inventory report: {e}")
            return {
                "product_count": 0,
                "inventory_value": 0.0,
                "stock_quantities": 0
            }

    # --- FEATURE 7: customer_report ---
    def customer_report(self):
        """
        Generates customer registry metrics.
        
        Returns:
            dict: total customer count and list of recently registered customer dicts.
        """
        try:
            cust_mgr = Customer()
            customer_count = cust_mgr.get_customer_count()
            recent_rows = cust_mgr.get_recent_customers(limit=10)
            
            recent_customers = [
                {
                    "id": c[0],
                    "customer_name": c[1],
                    "phone": c[2] if c[2] else "N/A",
                    "address": c[3] if c[3] else "N/A",
                    "created_at": c[4]
                }
                for c in recent_rows
            ]
            
            return {
                "customer_count": customer_count,
                "recent_customers": recent_customers
            }
        except Exception as e:
            print(f"Error generating customer report: {e}")
            return {
                "customer_count": 0,
                "recent_customers": []
            }

    # --- FEATURE 8: export_sales_excel ---
    def export_sales_excel(self, filename=None):
        """
        Exports all sales history records to an Excel file.
        Creates reports folder automatically if not present.
        
        Returns:
            str: Absolute file path.
        """
        try:
            if filename is None:
                filename = "reports/sales_report.xlsx"
                
            folder = os.path.dirname(filename)
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
                
            sale_mgr = Sale()
            sales = sale_mgr.get_all_sales()
            
            data = []
            for s in sales:
                data.append({
                    "Invoice No": s[1],
                    "Customer ID": s[2] if s[2] else "Walk-in Guest",
                    "Subtotal": s[3],
                    "Discount": s[4],
                    "Total Amount": s[5],
                    "Payment Method": s[6],
                    "Sale Date": s[7]
                })
                
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            return os.path.abspath(filename)
        except Exception as e:
            print(f"Error exporting sales excel: {e}")
            return None

    # --- FEATURE 9: export_inventory_excel ---
    def export_inventory_excel(self, filename=None):
        """
        Exports complete inventory catalog to an Excel file.
        
        Returns:
            str: Absolute file path.
        """
        try:
            if filename is None:
                filename = "reports/inventory_report.xlsx"
                
            folder = os.path.dirname(filename)
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
                
            prod_mgr = Product()
            products = prod_mgr.get_all_products()
            
            data = []
            for p in products:
                data.append({
                    "Product ID": p[0],
                    "Barcode": p[1],
                    "Product Name": p[2],
                    "Brand": p[3],
                    "Category": p[4],
                    "Purchase Price": p[5],
                    "Selling Price": p[6],
                    "Quantity": p[7],
                    "Created At": p[8]
                })
                
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            return os.path.abspath(filename)
        except Exception as e:
            print(f"Error exporting inventory excel: {e}")
            return None

    # --- FEATURE 10: export_customer_excel ---
    def export_customer_excel(self, filename=None):
        """
        Exports registered customer catalog records to an Excel file.
        
        Returns:
            str: Absolute file path.
        """
        try:
            if filename is None:
                filename = "reports/customer_report.xlsx"
                
            folder = os.path.dirname(filename)
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
                
            cust_mgr = Customer()
            customers = cust_mgr.get_all_customers()
            
            data = []
            for c in customers:
                data.append({
                    "Customer ID": c[0],
                    "Customer Name": c[1],
                    "Phone": c[2] if c[2] else "N/A",
                    "Address": c[3] if c[3] else "N/A",
                    "Created At": c[4]
                })
                
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            return os.path.abspath(filename)
        except Exception as e:
            print(f"Error exporting customer excel: {e}")
            return None

    # --- FEATURE 11: dashboard_metrics ---
    def dashboard_metrics(self):
        """
        Generates general dashboard summaries.
        
        Returns:
            dict: key indicators dashboard metrics.
        """
        try:
            sale_mgr = Sale()
            prod_mgr = Product()
            cust_mgr = Customer()
            
            return {
                "today_revenue": sale_mgr.get_today_revenue(),
                "month_revenue": sale_mgr.get_month_revenue(),
                "total_sales": sale_mgr.get_total_sales_count(),
                "total_products": prod_mgr.get_product_count(),
                "total_customers": cust_mgr.get_customer_count(),
                "inventory_value": prod_mgr.get_inventory_value()
            }
        except Exception as e:
            print(f"Error getting dashboard metrics: {e}")
            return {
                "today_revenue": 0.0,
                "month_revenue": 0.0,
                "total_sales": 0,
                "total_products": 0,
                "total_customers": 0,
                "inventory_value": 0.0
            }

    # --- Pre-existing Backward Compatibility Dashboard UI Queries ---

    @staticmethod
    def get_dashboard_metrics():
        """Calculates core KPI parameters for today and total stock."""
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Total Stock Count (simply SUM from products quantity column)
        cursor.execute("SELECT SUM(quantity) FROM products;")
        total_stock_row = cursor.fetchone()
        total_stock = total_stock_row[0] if total_stock_row and total_stock_row[0] is not None else 0
                
        # 2. Today's Metrics (Revenue, Transactions count, Profit)
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        # Sales today
        cursor.execute("SELECT id, total_amount FROM sales WHERE sale_date LIKE ?;", (f"{today_str}%",))
        sales_today = cursor.fetchall()
        
        today_revenue = sum(s['total_amount'] for s in sales_today)
        today_transactions = len(sales_today)
        
        # Profit today (Revenue - Cost of Sold Items)
        today_profit = 0.0
        for sale in sales_today:
            cursor.execute(
                """
                SELECT si.quantity, p.purchase_price
                FROM sale_items si
                JOIN products p ON si.product_id = p.id
                WHERE si.sale_id = ?;
                """,
                (sale['id'],)
            )
            items = cursor.fetchall()
            sale_cogs = sum(item['purchase_price'] * item['quantity'] for item in items)
            today_profit += (sale['total_amount'] - sale_cogs)
            
        conn.close()
        return {
            'total_stock': total_stock,
            'today_revenue': today_revenue,
            'today_transactions': today_transactions,
            'today_profit': today_profit
        }

    @staticmethod
    def get_low_stock_alerts():
        """Returns products whose stock levels are equal to or lower than threshold (default 5)."""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Load all products below min stock (default 5)
        cursor.execute("SELECT id, barcode as sku, brand || ' ' || product_name as name, quantity as stock FROM products WHERE quantity <= 5;")
        rows = cursor.fetchall()
        conn.close()
        
        alerts = []
        for r in rows:
            alerts.append({
                'id': r['id'],
                'sku': r['sku'],
                'name': r['name'],
                'stock': r['stock'],
                'min': 5
            })
        return alerts

    @staticmethod
    def get_weekly_trend():
        """Calculates revenue values for each of the last 7 days."""
        conn = get_connection()
        cursor = conn.cursor()
        
        trend = []
        for i in range(6, -1, -1):
            d = datetime.date.today() - datetime.timedelta(days=i)
            d_str = d.strftime('%Y-%m-%d')
            cursor.execute("SELECT SUM(total_amount) FROM sales WHERE sale_date LIKE ?;", (f"{d_str}%",))
            val = cursor.fetchone()[0]
            val = val if val is not None else 0.0
            trend.append((d.strftime('%a'), val))
            
        conn.close()
        return trend

    @staticmethod
    def get_financial_reports(range_type='today'):
        """Calculates revenue, COGS, profits, and log details for today, month or all time."""
        conn = get_connection()
        cursor = conn.cursor()
        
        now = datetime.datetime.now()
        if range_type == 'today':
            query_date = now.strftime('%Y-%m-%d') + '%'
        elif range_type == 'month':
            query_date = now.strftime('%Y-%m-') + '%'
        else:
            query_date = '%' # All-Time
            
        # Get sales logs matching criteria
        cursor.execute(
            """
            SELECT s.id, s.invoice_no, s.sale_date, s.total_amount, s.payment_method, c.customer_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.sale_date LIKE ?
            ORDER BY s.sale_date DESC;
            """,
            (query_date,)
        )
        sales_rows = cursor.fetchall()
        
        total_rev = 0.0
        total_cogs = 0.0
        invoices = []
        
        for s in sales_rows:
            total_rev += s['total_amount']
            
            # Fetch items details to compute margins
            cursor.execute(
                """
                SELECT si.quantity, p.purchase_price
                FROM sale_items si
                JOIN products p ON si.product_id = p.id
                WHERE si.sale_id = ?;
                """,
                (s['id'],)
            )
            items = cursor.fetchall()
            sale_cogs = sum(item['purchase_price'] * item['quantity'] for item in items)
            total_cogs += sale_cogs
            
            margin_profit = s['total_amount'] - sale_cogs
            invoices.append({
                'invoice': s['invoice_no'],
                'date': s['sale_date'],
                'cashier': 'system',
                'customer': s['customer_name'] or 'Walk-in Guest',
                'amount': s['total_amount'],
                'profit': margin_profit
            })
            
        # Get Best Sellers ranking
        cursor.execute(
            """
            SELECT si.product_id, p.brand, p.product_name as model, SUM(si.quantity) as units, SUM(si.unit_price * si.quantity) as rev
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.sale_date LIKE ?
            GROUP BY si.product_id
            ORDER BY units DESC, rev DESC
            LIMIT 10;
            """,
            (query_date,)
        )
        bestsellers = cursor.fetchall()
        
        conn.close()
        return {
            'total_revenue': total_rev,
            'total_cogs': total_cogs,
            'net_profit': total_rev - total_cogs,
            'invoices': invoices,
            'bestsellers': bestsellers
        }

if __name__ == "__main__":
    from database.db import init_db
    
    # 0. Initialize schemas
    init_db()
    
    prod_mgr = Product()
    cust_mgr = Customer()
    sale_mgr = Sale()
    report_srv = ReportService()
    
    print("=== STARTING REPORT SERVICE TEST RUN ===")
    
    # Setup test variables and clean database
    test_barcode = "REPORT-TEST-BARCODE"
    existing_p = prod_mgr.get_product_by_barcode(test_barcode)
    if existing_p:
        prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (existing_p[0],))
        prod_mgr.delete_product(existing_p[0])
        
    prod_mgr.add_product(
        barcode=test_barcode,
        product_name="Report Demo Phone",
        brand="BrandY",
        category="Phones",
        purchase_price=500.00,
        selling_price=750.00,
        quantity=8
    )
    product = prod_mgr.get_product_by_barcode(test_barcode)
    product_id = product[0]
    
    test_phone = "9990001111"
    existing_c = cust_mgr.get_customer_by_phone(test_phone)
    if existing_c:
        cust_mgr.db.execute("DELETE FROM customers WHERE id = ?;", (existing_c[0],))
        
    cust_mgr.add_customer("Tester Report", test_phone, "Reports Lane")
    customer = cust_mgr.get_customer_by_phone(test_phone)
    customer_id = customer[0]
    
    # Create a test sale to populate report data
    sale_res = sale_mgr.create_sale(
        customer_id=customer_id,
        cart_items=[{"product_id": product_id, "quantity": 2}],
        discount=50.00,
        payment_method="Card"
    )
    
    # 1. Generate Daily Report
    print("\n1. Testing Daily Sales Report:")
    daily = report_srv.daily_sales_report()
    print(f"   Total Sales Count: {daily['total_sales_count']}")
    print(f"   Total Revenue:     ${daily['total_revenue']:.2f}")
    print(f"   Total Discounts:   ${daily['total_discounts']:.2f}")
    print(f"   Invoices List Len: {len(daily['invoices'])}")
    
    # 2. Generate Inventory Report
    print("\n2. Testing Inventory Report:")
    inv = report_srv.inventory_report()
    print(f"   Unique Product Count: {inv['product_count']}")
    print(f"   Inventory Value:      ${inv['inventory_value']:.2f}")
    print(f"   Stock Quantities sum: {inv['stock_quantities']}")
    
    # 3. Export Excel files
    print("\n3. Testing Export Excel Files:")
    sales_file = report_srv.export_sales_excel()
    inv_file = report_srv.export_inventory_excel()
    cust_file = report_srv.export_customer_excel()
    print(f"   Sales report saved:     {sales_file}")
    print(f"   Inventory report saved: {inv_file}")
    print(f"   Customer report saved:  {cust_file}")
    
    # 4. Print Dashboard Metrics
    print("\n4. Testing Dashboard Metrics:")
    metrics = report_srv.dashboard_metrics()
    for key, val in metrics.items():
        print(f"   - {key}: {val}")
        
    # Clean up test database records (delete stock histories first)
    if sale_res['success']:
        sale_mgr.cancel_sale(sale_res['sale_id'])
    prod_mgr.db.execute("DELETE FROM stock_history WHERE product_id = ?;", (product_id,))
    prod_mgr.delete_product(product_id)
    cust_mgr.db.execute("DELETE FROM customers WHERE id = ?;", (customer_id,))
    
    # Delete temporary Excel files
    for file in [sales_file, inv_file, cust_file]:
        if file and os.path.exists(file):
            try:
                os.remove(file)
            except OSError:
                pass
                
    print("\n=== REPORT SERVICE TEST RUN COMPLETED successfully ===")
