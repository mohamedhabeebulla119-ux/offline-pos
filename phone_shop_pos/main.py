# main.py
import sys
import os
import json
import time
import datetime
import sqlite3

# PyQt6 Core and Widgets
from PyQt6.QtCore import QUrl, QObject, pyqtSlot, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel

# Import database, models and services
from database.db import init_db, get_connection
from models.product import Product
from models.customer import Customer
from models.sale import Sale, Imei
from services.billing_service import BillingService
from services.report_service import ReportService
from ui.login import create_default_admin_if_empty

class BackendBridge(QObject):
    """
    Python-JS Bridge Object exposed to QWebEngineView via QWebChannel.
    A single generic slot receives JSON payloads, executes the request,
    and returns JSON responses back to JavaScript.
    """
    def __init__(self, main_window):
        super().__init__()
        self.win = main_window

    @pyqtSlot(str, str, result=str)
    def execute(self, action, payload_json):
        try:
            payload = json.loads(payload_json) if payload_json else {}
            result = self.route_action(action, payload)
            return json.dumps(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"success": False, "message": str(e)})

    def route_action(self, action, payload):
        # 1. USER AUTH & ACCOUNTS
        if action == "login":
            username = payload.get("username")
            password = payload.get("password")
            create_default_admin_if_empty()
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?;", (username,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row['password'] == password:
                return {
                    "success": True, 
                    "user": {"username": row['username'], "role": row['role']}
                }
            return {"success": False, "message": "Invalid username or password."}
            
        elif action == "get_users":
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, role FROM users;")
            rows = cursor.fetchall()
            conn.close()
            users = [{"username": r['username'], "role": r['role']} for r in rows]
            return {"success": True, "users": users}
            
        elif action == "add_user":
            u = payload.get("username")
            p = payload.get("password")
            r = payload.get("role")
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?);", (u, p, r))
                conn.commit()
                return {"success": True}
            except sqlite3.IntegrityError:
                return {"success": False, "message": "Username already exists."}
            except Exception as e:
                return {"success": False, "message": str(e)}
            finally:
                conn.close()
                
        elif action == "delete_user":
            u = payload.get("username")
            if u == 'admin':
                return {"success": False, "message": "Primary admin cannot be deleted."}
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?;", (u,))
            conn.commit()
            conn.close()
            return {"success": True}

        # 2. DASHBOARD KPI METRICS
        elif action == "get_dashboard_metrics":
            metrics = ReportService.get_dashboard_metrics()
            low_stock = ReportService.get_low_stock_alerts()
            trend = ReportService.get_weekly_trend()
            return {
                "success": True, 
                "metrics": metrics, 
                "low_stock": low_stock, 
                "trend": trend
            }

        # 3. PRODUCTS CATALOG CRUD
        elif action == "get_products":
            prod_mgr = Product()
            products = prod_mgr.get_all_products()
            prod_list = []
            for p in products:
                prod_list.append({
                    "id": p[0],
                    "barcode": p[1],
                    "product_name": p[2],
                    "brand": p[3],
                    "category": p[4],
                    "purchase_price": p[5],
                    "selling_price": p[6],
                    "quantity": p[7]
                })
            return {"success": True, "products": prod_list}
            
        elif action == "add_product":
            brand = payload.get("brand")
            name = payload.get("product_name")
            cat = payload.get("category")
            cost = float(payload.get("purchase_price", 0))
            price = float(payload.get("selling_price", 0))
            qty = int(payload.get("quantity", 0))
            
            res = Product().create_product_with_barcode(brand, name, cat, cost, price, qty)
            return res
            
        elif action == "update_product":
            p_id = int(payload.get("product_id"))
            barcode = payload.get("barcode")
            brand = payload.get("brand")
            name = payload.get("product_name")
            cat = payload.get("category")
            cost = float(payload.get("purchase_price", 0))
            price = float(payload.get("selling_price", 0))
            qty = int(payload.get("quantity", 0))
            
            success = Product().update_product(p_id, barcode, name, brand, cat, cost, price, qty)
            return {"success": success}
            
        elif action == "delete_product":
            p_id = int(payload.get("product_id"))
            success = Product().delete_product(p_id)
            return {"success": success}
            
        elif action == "regenerate_barcode":
            p_id = int(payload.get("product_id"))
            res = Product().regenerate_barcode(p_id)
            return res
            
        elif action == "print_barcode":
            barcode_val = payload.get("barcode")
            product_name = payload.get("product_name")
            price = float(payload.get("price", 0))
            return self.print_sticker_label(barcode_val, product_name, price)

        # 4. STOCK ADJUSTMENTS & IMEIs
        elif action == "get_inventory_logs":
            tab = payload.get("tab")
            if tab in ['available', 'sold']:
                raw_logs = Imei.get_all(tab)
                normalized_logs = []
                for r in raw_logs:
                    log_date = r['added_date'] if tab == 'available' else (r['sold_date'] or r['added_date'])
                    reason = "Available Device" if tab == 'available' else f"Sold via Invoice {r['sale_id']}"
                    normalized_logs.append({
                        "date": log_date,
                        "brand": r['brand'],
                        "model": r['model'],
                        "type": r['status'],  # 'available' or 'sold'
                        "quantity": 1,
                        "reason": reason,
                        "imei": r['imei']
                    })
                return {"success": True, "logs": normalized_logs}
            else:
                logs = Product.get_inventory_log()
                return {"success": True, "logs": logs}
                
        elif action == "adjust_stock":
            p_id = int(payload.get("product_id"))
            tx_type = payload.get("type")
            qty = int(payload.get("quantity"))
            reason = payload.get("reason")
            date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            Product.add_inventory_tx(p_id, tx_type, qty, reason, date_str)
            return {"success": True}
            
        elif action == "get_imeis":
            p_id = int(payload.get("product_id"))
            status = payload.get("status")
            imeis = Imei.get_by_product(p_id, status)
            return {"success": True, "imeis": imeis}
            
        elif action == "add_imei":
            p_id = int(payload.get("product_id"))
            imei = payload.get("imei")
            date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            success = Imei.add(imei, p_id, date_str)
            if success:
                return {"success": True}
            return {"success": False, "message": "Failed to add IMEI. Device serial may already exist."}
            
        elif action == "get_imei_details":
            imei = payload.get("imei")
            details = Imei.get_details(imei)
            if details:
                return {"success": True, "details": details}
            return {"success": False, "message": "Details not found."}

        # 5. CUSTOMERS MANAGEMENT
        elif action == "get_customers":
            cust_mgr = Customer()
            customers = cust_mgr.get_all_customers()
            cust_list = []
            for c in customers:
                cust_list.append({
                    "id": c[0],
                    "customer_name": c[1],
                    "phone": c[2],
                    "address": c[3],
                    "created_at": c[4]
                })
            return {"success": True, "customers": cust_list}
            
        elif action == "add_customer":
            name = payload.get("customer_name")
            phone = payload.get("phone")
            addr = payload.get("address", "")
            res = BillingService().create_customer(name, phone, addr)
            return res
            
        elif action == "update_customer":
            c_id = int(payload.get("customer_id"))
            name = payload.get("customer_name")
            phone = payload.get("phone")
            addr = payload.get("address", "")
            success = Customer().update_customer(c_id, name, phone, addr)
            return {"success": success}
            
        elif action == "delete_customer":
            c_id = int(payload.get("customer_id"))
            success, msg = Customer().delete_customer(c_id)
            return {"success": success, "message": msg}
            
        elif action == "get_customer_history":
            c_id = int(payload.get("customer_id"))
            purchases = Customer.get_purchases(c_id)
            
            # Binds warranties correctly using sale_date column from SQLite
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.barcode as imei, p.brand, p.product_name as model, s.sale_date
                FROM products p
                JOIN sale_items si ON p.id = si.product_id
                JOIN sales s ON si.sale_id = s.id
                WHERE s.customer_id = ? AND length(p.barcode) >= 8;
                """,
                (c_id,)
            )
            rows = cursor.fetchall()
            conn.close()
            
            warranties = []
            for r in rows:
                sale_dt = datetime.datetime.strptime(r['sale_date'], '%Y-%m-%d %H:%M:%S')
                expiry = sale_dt + datetime.timedelta(days=365)
                is_active = datetime.datetime.now() < expiry
                w_status = "Active" if is_active else "Expired"
                warranties.append({
                    "imei": r['imei'],
                    "model": f"{r['brand']} {r['model']}",
                    "period": f"{r['sale_date'][:10]} to {expiry.strftime('%Y-%m-%d')}",
                    "status": w_status
                })
            return {"success": True, "purchases": purchases, "warranties": warranties}

        # 6. BILLING REGISTER
        elif action == "scan_barcode":
            barcode = payload.get("barcode")
            res = BillingService().scan_barcode(barcode)
            return res
            
        elif action == "create_invoice":
            customer_id = payload.get("customer_id")
            cart_items = payload.get("cart_items")
            discount = float(payload.get("discount", 0))
            pay_method = payload.get("payment_method")
            res = BillingService().create_invoice(customer_id, cart_items, discount, pay_method)
            return res
            
        elif action == "reprint_receipt":
            invoice_no = payload.get("invoice_no")
            success = BillingService.reprint_receipt_file(invoice_no)
            return {"success": success}

        # 7. METRICS & REPORTS
        elif action == "get_financial_reports":
            range_type = payload.get("range", "today")
            data = ReportService.get_financial_reports(range_type)
            mapped_bestsellers = []
            for b in data['bestsellers']:
                mapped_bestsellers.append({
                    "brand": b['brand'],
                    "model": b['model'],
                    "units": b['units'],
                    "rev": b['rev']
                })
            data['bestsellers'] = mapped_bestsellers
            return {"success": True, "data": data}
            
        elif action == "export_excel_report":
            rep_type = payload.get("type")
            filepath = None
            if rep_type == "sales":
                filepath = ReportService().export_sales_excel()
            elif rep_type == "inventory":
                filepath = ReportService().export_inventory_excel()
            elif rep_type == "customers":
                filepath = ReportService().export_customer_excel()
            if filepath:
                return {"success": True, "filepath": filepath}
            return {"success": False, "message": "Excel Export operation failed."}

        # 8. CONFIGS & BACKUPS
        elif action == "get_settings":
            settings = BillingService.get_shop_settings()
            return {"success": True, "settings": settings}
            
        elif action == "save_settings":
            settings = payload.get("settings")
            success = BillingService.save_shop_settings(settings)
            if success:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopName';", (settings.get('shopName'),))
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopPhone';", (settings.get('shopPhone'),))
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopEmail';", (settings.get('shopEmail'),))
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'taxRate';", (str(settings.get('taxRate')),))
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopAddress';", (settings.get('shopAddress'),))
                conn.commit()
                conn.close()
            return {"success": success}
            
        elif action == "export_backup":
            return self.backup_export_file()
            
        elif action == "import_backup":
            return self.backup_restore_file()

        return {"success": False, "message": f"Action '{action}' not recognized."}

    def print_sticker_label(self, barcode_val, product_name, price):
        """Native printer engine for barcode printing tags"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            img_path = os.path.join(base_dir, "barcodes", f"{barcode_val}.png")
            if not os.path.exists(img_path):
                from services.barcode_service import BarcodeService
                BarcodeService().create_barcode(barcode_val)
                
            if not os.path.exists(img_path):
                return {"success": False, "message": f"Barcode image not found: {img_path}"}

            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPainter, QPixmap, QFont
            from PyQt6.QtCore import QRectF, QPointF, Qt

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer)
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                painter = QPainter(printer)
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                width = page_rect.width()
                
                # Title Product name
                font_title = QFont("Arial", 10, QFont.Weight.Bold)
                painter.setFont(font_title)
                painter.drawText(QRectF(10, 10, width - 20, 30), Qt.AlignmentFlag.AlignCenter, product_name)

                # Barcode Image
                pixmap = QPixmap(img_path)
                scaled_pixmap = pixmap.scaledToWidth(int(width * 0.8), Qt.TransformationMode.SmoothTransformation)
                x = (width - scaled_pixmap.width()) / 2
                y = 45
                painter.drawPixmap(QPointF(x, y), scaled_pixmap)

                # Code Text
                font_text = QFont("Arial", 8)
                painter.setFont(font_text)
                y_text = y + scaled_pixmap.height() + 10
                painter.drawText(QRectF(10, y_text, width - 20, 20), Qt.AlignmentFlag.AlignCenter, barcode_val)

                # Price Label
                if price > 0:
                    font_price = QFont("Arial", 10, QFont.Weight.Bold)
                    painter.setFont(font_price)
                    y_price = y_text + 20
                    painter.drawText(QRectF(10, y_price, width - 20, 30), Qt.AlignmentFlag.AlignCenter, f"Price: Rs. {price:.2f}")

                painter.end()
                return {"success": True}
            return {"success": False, "message": "Printing cancelled."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def backup_export_file(self):
        """Native JSON Export dialogue trigger"""
        filepath, _ = QFileDialog.getSaveFileName(
            None, "Export Database Backup", "backups/phoneshop_backup.json", "JSON Files (*.json)"
        )
        if not filepath:
            return {"success": False, "message": "Dialog cancelled."}
            
        try:
            tables = ['users', 'products', 'inventory', 'imeis', 'sales', 'sale_items', 'customers', 'settings']
            data = {}
            conn = get_connection()
            cursor = conn.cursor()
            for t in tables:
                cursor.execute(f"SELECT * FROM {t};")
                rows = cursor.fetchall()
                data[t] = [dict(r) for r in rows]
            conn.close()
            
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def backup_restore_file(self):
        """Native JSON Restore dialogue trigger"""
        filepath, _ = QFileDialog.getOpenFileName(
            None, "Restore Database Backup", "backups", "JSON Files (*.json)"
        )
        if not filepath:
            return {"success": False, "message": "Dialog cancelled."}
            
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                
            required = ['users', 'products', 'inventory', 'imeis', 'sales', 'sale_items', 'customers', 'settings']
            if not all(k in data for k in required):
                return {"success": False, "message": "Invalid backup file structure."}

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            for t in required:
                cursor.execute(f"DELETE FROM {t};")
                
            for t in required:
                if not data[t]:
                    continue
                columns = data[t][0].keys()
                query = f"INSERT INTO {t} ({', '.join(columns)}) VALUES ({', '.join(['?']*len(columns))});"
                for row in data[t]:
                    cursor.execute(query, tuple(row.values()))
                    
            cursor.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
            conn.close()
            
            # Force restart of the application
            QMessageBox.information(None, "Success", "Restore complete! Restarting terminal now.")
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}


class PhoneShopApp(QMainWindow):
    """
    Main QMainWindow layout hosting the browser viewport QWebEngineView.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phone Shop POS System (Offline Terminal)")
        self.resize(1150, 750)
        self.setMinimumSize(1050, 680)

        # 1. Initialize DB and Folders
        init_db()
        self.init_directories()

        # 2. Setup WebView
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)

        # Allow local content to access file links and other local files
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

        # 3. Setup WebChannel Bridge
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = BackendBridge(self)
        self.channel.registerObject("backend", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load Local index.html
        base_dir = os.path.dirname(os.path.abspath(__file__))
        index_url = QUrl.fromLocalFile(os.path.join(base_dir, "ui", "web", "index.html"))
        self.web_view.setUrl(index_url)

    def init_directories(self):
        folders = ['barcodes', 'receipts', 'reports', 'backups']
        for f in folders:
            if not os.path.exists(f):
                os.makedirs(f)


if __name__ == "__main__":
    # Create Application Instance
    app = QApplication(sys.argv)
    
    # Run
    window = PhoneShopApp()
    window.show()
    sys.exit(app.exec())
