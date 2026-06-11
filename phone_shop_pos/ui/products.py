# ui/products.py
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import sqlite3
from database.db import get_connection
from models.product import Product
from models.sale import Imei
from services.barcode_service import BarcodeService

THEME = {
    'bg_main': '#0F172A',
    'bg_card': '#1E293B',
    'border': '#334155',
    'text_main': '#F8FAFC',
    'text_muted': '#94A3B8',
    'primary': '#6366F1',
    'primary_hover': '#4F46E5',
    'success': '#10B981',
    'warning': '#F59E0B',
    'danger': '#EF4444'
}

def make_hover_btn(parent, text, bg, fg, command, width=15):
    btn = tk.Button(
        parent, text=text, bg=bg, fg=fg, activebackground=THEME['primary_hover'], activeforeground='#ffffff',
        font=("Helvetica", 9, "bold"), bd=0, relief="flat", cursor="hand2", command=command, width=width
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=THEME['primary_hover'] if bg == THEME['primary'] else '#2A3B50'))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn

class ProductsFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.products = []
        self.create_widgets()

    def create_widgets(self):
        # Header Row
        header = tk.Frame(self, bg=THEME['bg_main'])
        header.pack(fill='x', pady=(0, 20))
        
        tk.Label(header, text="Products Catalog", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(side='left')
        
        if self.user_data['role'] == 'admin':
            make_hover_btn(header, "+ Add Product", THEME['primary'], '#ffffff', lambda: self.open_product_modal(), width=15).pack(side='right')

        # Search Panel
        search_card = tk.Frame(self, bg=THEME['bg_card'], padx=15, pady=15, highlightbackground=THEME['border'], highlightthickness=1)
        search_card.pack(fill='x', pady=(0, 20))
        
        tk.Label(search_card, text="Search Products:", bg=search_card['bg'], fg=THEME['text_muted'], font=("Helvetica", 10, "bold")).pack(side='left', padx=(0, 10))
        
        self.ent_search = tk.Entry(search_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_search.pack(side='left', fill='x', expand=True, ipady=6, padx=(0, 10))
        self.ent_search.bind("<KeyRelease>", lambda e: self.filter_products())

        make_hover_btn(search_card, "Reset Filters", THEME['bg_main'], THEME['text_main'], self.clear_filters, width=12).pack(side='right')

        # Treeview catalog table
        table_frame = tk.Frame(self, bg=THEME['bg_main'])
        table_frame.pack(fill='both', expand=True)
        
        self.tree = ttk.Treeview(table_frame, columns=("barcode", "brand", "name", "category", "qty", "cost", "price"), show="headings", height=12)
        self.tree.heading("barcode", text="Barcode")
        self.tree.heading("brand", text="Brand")
        self.tree.heading("name", text="Product Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("qty", text="Qty")
        self.tree.heading("cost", text="Purchase Price")
        self.tree.heading("price", text="Selling Price")
        
        self.tree.column("barcode", width=110, anchor='center')
        self.tree.column("brand", width=110, anchor='w')
        self.tree.column("name", width=180, anchor='w')
        self.tree.column("category", width=90, anchor='center')
        self.tree.column("qty", width=70, anchor='center')
        self.tree.column("cost", width=100, anchor='e')
        self.tree.column("price", width=100, anchor='e')

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.tree.bind("<Button-3>", self.show_context_menu)

        # Controls panel below table
        controls = tk.Frame(self, bg=THEME['bg_main'])
        controls.pack(fill='x', pady=(15, 0))

        make_hover_btn(controls, "Print Barcode", THEME['bg_card'], THEME['text_main'], self.print_barcode, width=15).pack(side='left', padx=4)
        
        if self.user_data['role'] == 'admin':
            make_hover_btn(controls, "Edit Product", THEME['bg_card'], THEME['text_main'], self.edit_selected, width=15).pack(side='left', padx=4)
            make_hover_btn(controls, "Delete Product", THEME['danger'], '#ffffff', self.delete_selected, width=15).pack(side='left', padx=4)

        self.refresh()

    def refresh(self):
        self.products = Product.get_all()
        self.filter_products()

    def filter_products(self):
        q = self.ent_search.get().strip().lower()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for p in self.products:
            name = f"{p.brand} {p.product_name}"
            if q and not (q in p.barcode.lower() or q in name.lower() or q in p.category.lower()):
                continue
                
            stock = Product.get_stock(p.id)
            
            self.tree.insert(
                "", "end", iid=p.id, 
                values=(p.barcode, p.brand, p.product_name, p.category, f"{stock} units", f"Rs. {p.purchase_price:.2f}", f"Rs. {p.selling_price:.2f}")
            )

    def clear_filters(self):
        self.ent_search.delete(0, 'end')
        self.filter_products()

    def print_barcode(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a product to print label.")
            return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            self.run_pyqt6_print(p.barcode, f"{p.brand} {p.product_name}", p.selling_price, f"barcodes/{p.barcode}.png")

    def delete_selected(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a product to delete.")
            return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            if messagebox.askyesno("Confirm", f"Are you sure you want to delete {p.brand} {p.product_name}?"):
                if Product.delete(p_id):
                    messagebox.showinfo("Success", "Product deleted.")
                    self.refresh()
                else:
                    messagebox.showerror("Error", "Could not delete product. It may have dependency logs.")

    def edit_selected(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a product to edit.")
            return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            self.open_product_modal(p)

    def open_product_modal(self, product=None):
        is_edit = product is not None
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title("Edit Product" if is_edit else "Add New Product")
        modal.geometry("400x520")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Product Information", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=15)

        # Fields
        tk.Label(modal, text="Barcode", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        ent_sku = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_sku.pack(fill='x', ipady=5, padx=25, pady=(4, 10))
        if is_edit:
            ent_sku.insert(0, product.barcode)
            ent_sku.config(state='disabled')
        else:
            ent_sku.insert(0, "[AUTO GENERATED AFTER SAVE]")
            ent_sku.config(state='disabled', fg=THEME['text_muted'])

        tk.Label(modal, text="Brand Name *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        ent_brand = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_brand.pack(fill='x', ipady=5, padx=25, pady=(4, 10))
        if is_edit: ent_brand.insert(0, product.brand)

        tk.Label(modal, text="Product Name *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        ent_model = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_model.pack(fill='x', ipady=5, padx=25, pady=(4, 10))
        if is_edit: ent_model.insert(0, product.product_name)

        # Category and Qty row
        cat_frame = tk.Frame(modal, bg=THEME['bg_card'])
        cat_frame.pack(fill='x', padx=25, pady=(4, 10))
        
        f_cat = tk.Frame(cat_frame, bg=THEME['bg_card'])
        f_cat.pack(side='left', fill='x', expand=True, padx=(0, 10))
        tk.Label(f_cat, text="Category *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        cb_cat = ttk.Combobox(f_cat, values=["Phones", "Accessories", "Tablets", "Smartwatches", "Other"], state="readonly")
        cb_cat.pack(fill='x', pady=(4, 0))
        cb_cat.set(product.category if is_edit else "Phones")

        f_qty = tk.Frame(cat_frame, bg=THEME['bg_card'])
        f_qty.pack(side='right', fill='x', expand=True)
        tk.Label(f_qty, text="Quantity (Initial) *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        ent_qty = tk.Entry(f_qty, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_qty.pack(fill='x', ipady=5, pady=(4, 0))
        ent_qty.insert(0, str(product.quantity) if is_edit else "0")
        if is_edit:
            ent_qty.config(state='disabled')

        # Cost and Price row
        prices_frame = tk.Frame(modal, bg=THEME['bg_card'])
        prices_frame.pack(fill='x', padx=25, pady=(4, 15))
        
        f1 = tk.Frame(prices_frame, bg=THEME['bg_card'])
        f1.pack(side='left', fill='x', expand=True, padx=(0, 10))
        tk.Label(f1, text="Purchase Cost (Rs.) *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        ent_cost = tk.Entry(f1, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_cost.pack(fill='x', ipady=5, pady=(4, 0))
        if is_edit: ent_cost.insert(0, str(product.purchase_price))

        f2 = tk.Frame(prices_frame, bg=THEME['bg_card'])
        f2.pack(side='right', fill='x', expand=True)
        tk.Label(f2, text="Selling Price (Rs.) *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        ent_price = tk.Entry(f2, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_price.pack(fill='x', ipady=5, pady=(4, 0))
        if is_edit: ent_price.insert(0, str(product.selling_price))

        def save():
            brand = ent_brand.get().strip()
            model = ent_model.get().strip()
            cat = cb_cat.get()
            cost_str = ent_cost.get().strip()
            price_str = ent_price.get().strip()
            qty_str = ent_qty.get().strip()
            
            if not brand or not model or not cost_str or not price_str or not qty_str:
                messagebox.showwarning("Validation Error", "All fields marked with (*) are required.", parent=modal)
                return
                
            try:
                c = float(cost_str)
                p = float(price_str)
                q = int(qty_str)
            except ValueError:
                messagebox.showerror("Error", "Prices and quantity values must be numbers.", parent=modal)
                return
                
            # Warnings
            if p < c:
                if not messagebox.askyesno("Warning", "Selling price is lower than purchase cost. Save anyway?", parent=modal):
                    return
                    
            if is_edit:
                product.brand = brand
                product.product_name = model
                product.category = cat
                product.purchase_price = c
                product.selling_price = p
                if product.save():
                    messagebox.showinfo("Success", "Product details updated successfully.", parent=modal)
                    modal.destroy()
                    self.refresh()
                else:
                    messagebox.showerror("Error", "Failed to update product details.", parent=modal)
            else:
                prod_mgr = Product()
                res = prod_mgr.create_product_with_barcode(
                    brand=brand,
                    product_name=model,
                    category=cat,
                    purchase_price=c,
                    selling_price=p,
                    quantity=q
                )
                if res.get("success"):
                    barcode_val = res["barcode"]
                    barcode_img = res["barcode_image"]
                    modal.destroy()
                    self.refresh()
                    self.show_save_success_dialog(brand, model, p, barcode_val, barcode_img)
                else:
                    messagebox.showerror("Error", f"Failed to save product: {res.get('message')}", parent=modal)

        make_hover_btn(modal, "SAVE DETAILS", THEME['primary'], '#ffffff', save, width=20).pack(pady=10)

    def show_save_success_dialog(self, brand, model, price, barcode_val, barcode_img):
        """Displays success modal after automatic barcode generation."""
        success_modal = tk.Toplevel(self, bg=THEME['bg_card'])
        success_modal.title("Success")
        success_modal.geometry("420x300")
        success_modal.resizable(False, False)
        success_modal.transient(self)
        success_modal.grab_set()

        tk.Label(success_modal, text="Product Saved Successfully", bg=THEME['bg_card'], fg=THEME['success'], font=("Helvetica", 14, "bold")).pack(pady=15)

        details_frame = tk.Frame(success_modal, bg=THEME['bg_card'])
        details_frame.pack(pady=10)

        tk.Label(details_frame, text=f"Product: {brand} {model}", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 10)).pack(anchor='w')
        tk.Label(details_frame, text=f"Barcode: {barcode_val}", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 11, "bold")).pack(anchor='w', pady=5)
        tk.Label(details_frame, text=f"Barcode Image: {barcode_img}", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9)).pack(anchor='w')

        btn_frame = tk.Frame(success_modal, bg=THEME['bg_card'])
        btn_frame.pack(pady=20)

        make_hover_btn(btn_frame, "Preview Barcode", THEME['primary'], '#ffffff', lambda: self.show_barcode_preview(brand, model, barcode_val, barcode_img), width=15).pack(side='left', padx=5)
        make_hover_btn(btn_frame, "Print Barcode", THEME['primary'], '#ffffff', lambda: self.run_pyqt6_print(barcode_val, f"{brand} {model}", price, barcode_img), width=15).pack(side='left', padx=5)
        make_hover_btn(btn_frame, "Close", THEME['bg_main'], THEME['text_main'], success_modal.destroy, width=10).pack(side='left', padx=5)

    def show_barcode_preview(self, brand, model, barcode_val, barcode_img):
        """Presents barcode preview modal with image display."""
        import os
        from PIL import Image, ImageTk
        
        preview_modal = tk.Toplevel(self, bg='#ffffff')
        preview_modal.title(f"Barcode Preview: {barcode_val}")
        preview_modal.geometry("400x300")
        preview_modal.resizable(False, False)
        preview_modal.transient(self)
        preview_modal.grab_set()

        tk.Label(preview_modal, text=f"{brand} {model}", bg='#ffffff', fg='#1E293B', font=("Helvetica", 12, "bold")).pack(pady=(15, 5))

        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            img_path = os.path.join(base_dir, barcode_img)
            if not os.path.exists(img_path):
                img_path = barcode_img
                
            img = Image.open(img_path)
            img = img.resize((300, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            img_label = tk.Label(preview_modal, image=photo, bg='#ffffff')
            img_label.image = photo
            img_label.pack(pady=10)
        except Exception as e:
            tk.Label(preview_modal, text=f"[Image Load Error: {e}]", bg='#ffffff', fg='#EF4444').pack(pady=10)

        tk.Label(preview_modal, text=barcode_val, bg='#ffffff', fg='#1E293B', font=("Courier", 12, "bold")).pack(pady=5)

        btn_close = tk.Button(preview_modal, text="Close", command=preview_modal.destroy, bg='#F1F5F9', fg='#475569', font=("Helvetica", 10, "bold"), bd=0, padx=15, pady=5, cursor="hand2")
        btn_close.pack(pady=15)

    def run_pyqt6_print(self, barcode_val, product_name, price, barcode_img):
        """Uses PyQt6 to execute printer sticker layout page printing."""
        import os
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            img_path = os.path.join(base_dir, barcode_img)
            if not os.path.exists(img_path):
                img_path = barcode_img
                
            if not os.path.exists(img_path):
                messagebox.showerror("Error", f"Barcode image not found: {img_path}")
                return

            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPainter, QPixmap, QFont
            from PyQt6.QtCore import QRectF, QPointF, Qt

            app = QApplication.instance()
            if not app:
                app = QApplication([])

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer)
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                painter = QPainter(printer)
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                width = page_rect.width()
                
                # Title
                font_title = QFont("Arial", 10, QFont.Weight.Bold)
                painter.setFont(font_title)
                painter.drawText(QRectF(10, 10, width - 20, 30), Qt.AlignmentFlag.AlignCenter, product_name)

                # Image
                pixmap = QPixmap(img_path)
                scaled_pixmap = pixmap.scaledToWidth(int(width * 0.8), Qt.TransformationMode.SmoothTransformation)
                x = (width - scaled_pixmap.width()) / 2
                y = 45
                painter.drawPixmap(QPointF(x, y), scaled_pixmap)

                # Text Code
                font_text = QFont("Arial", 8)
                painter.setFont(font_text)
                y_text = y + scaled_pixmap.height() + 10
                painter.drawText(QRectF(10, y_text, width - 20, 20), Qt.AlignmentFlag.AlignCenter, barcode_val)

                # Price Label
                font_price = QFont("Arial", 10, QFont.Weight.Bold)
                painter.setFont(font_price)
                y_price = y_text + 20
                painter.drawText(QRectF(10, y_price, width - 20, 30), Qt.AlignmentFlag.AlignCenter, f"Price: Rs. {price:.2f}")

                painter.end()
                messagebox.showinfo("Success", f"Sticker label for {product_name} printed.")
        except Exception as e:
            messagebox.showerror("Print Error", f"PyQt6 print failed: {e}")

    def show_context_menu(self, event):
        """Popup menu display for right click operations."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.focus(item)
            self.tree.selection_set(item)
            
            menu = tk.Menu(self, tearoff=0, bg=THEME['bg_card'], fg=THEME['text_main'])
            menu.add_command(label="Preview Barcode", command=self.preview_selected)
            menu.add_command(label="Print Barcode", command=self.print_selected)
            if self.user_data['role'] == 'admin':
                menu.add_command(label="Regenerate Barcode", command=self.regenerate_selected_barcode)
                
            menu.post(event.x_root, event.y_root)

    def preview_selected(self):
        selected = self.tree.focus()
        if not selected: return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            self.show_barcode_preview(p.brand, p.product_name, p.barcode, f"barcodes/{p.barcode}.png")

    def print_selected(self):
        selected = self.tree.focus()
        if not selected: return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            self.run_pyqt6_print(p.barcode, f"{p.brand} {p.product_name}", p.selling_price, f"barcodes/{p.barcode}.png")

    def regenerate_selected_barcode(self):
        selected = self.tree.focus()
        if not selected: return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            if messagebox.askyesno("Regenerate Barcode", f"Are you sure you want to generate a new barcode for {p.brand} {p.product_name}?\nThis will delete the old PNG and assign a new barcode ID."):
                res = Product().regenerate_barcode(p_id)
                if res.get("success"):
                    new_barcode = res["barcode"]
                    messagebox.showinfo("Success", f"Barcode regenerated successfully.\nNew Barcode: {new_barcode}")
                    self.refresh()
                else:
                    messagebox.showerror("Error", f"Failed to regenerate barcode: {res.get('message')}")


class InventoryFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.products = []
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="Inventory Stock Adjustments", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(anchor='w', pady=(0, 20))

        grid = tk.Frame(self, bg=THEME['bg_main'])
        grid.pack(fill='both', expand=True)
        grid.grid_columnconfigure(0, weight=2)
        grid.grid_columnconfigure(1, weight=3)
        grid.grid_rowconfigure(0, weight=1)

        # Left: Adjust Stock Card Form
        form_card = tk.Frame(grid, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        form_card.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        
        tk.Label(form_card, text="Log Transaction", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(anchor='w', pady=(0, 15))

        tk.Label(form_card, text="Scan Barcode / SKU", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_scan = tk.Entry(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_scan.pack(fill='x', ipady=6, pady=(4, 12))
        self.ent_scan.bind("<Return>", self.handle_scanner_enter)

        tk.Label(form_card, text="Or Select Phone Product *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.cb_prod = ttk.Combobox(form_card, state="readonly")
        self.cb_prod.pack(fill='x', pady=(4, 12))

        # Adjust action and qty
        split_row = tk.Frame(form_card, bg=THEME['bg_card'])
        split_row.pack(fill='x', pady=(0, 12))
        
        f1 = tk.Frame(split_row, bg=THEME['bg_card'])
        f1.pack(side='left', fill='x', expand=True, padx=(0, 10))
        tk.Label(f1, text="Action *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.cb_type = ttk.Combobox(f1, values=["in", "out"], state="readonly")
        self.cb_type.pack(fill='x', pady=(4, 0))
        self.cb_type.set("in")

        f2 = tk.Frame(split_row, bg=THEME['bg_card'])
        f2.pack(side='right', fill='x', expand=True)
        tk.Label(f2, text="Quantity *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_qty = tk.Entry(f2, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_qty.pack(fill='x', ipady=5, pady=(4, 0))
        self.ent_qty.insert(0, "1")

        tk.Label(form_card, text="Adjustment Reason *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.cb_reason = ttk.Combobox(
            form_card, values=["Purchase Order", "Supplier Return", "Damaged Device", "Stock Correction", "Other / Demo"],
            state="readonly"
        )
        self.cb_reason.pack(fill='x', pady=(4, 20))
        self.cb_reason.set("Purchase Order")

        make_hover_btn(form_card, "COMMIT ADJUSTMENT", THEME['primary'], '#ffffff', self.submit_transaction, width=22).pack(anchor='w')

        # Right: Log History Card
        log_card = tk.Frame(grid, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        log_card.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        
        tk.Label(log_card, text="Adjustment Transaction Log", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 13, "bold")).pack(anchor='w', pady=(0, 10))

        # Logs treeview
        self.log_tree = ttk.Treeview(log_card, columns=("date", "product", "action", "qty", "reason"), show="headings", height=10)
        self.log_tree.heading("date", text="Date")
        self.log_tree.heading("product", text="Product details")
        self.log_tree.heading("action", text="Action")
        self.log_tree.heading("qty", text="Qty")
        self.log_tree.heading("reason", text="Reason")
        
        self.log_tree.column("date", width=110, anchor='center')
        self.log_tree.column("product", width=140, anchor='w')
        self.log_tree.column("action", width=60, anchor='center')
        self.log_tree.column("qty", width=40, anchor='center')
        self.log_tree.column("reason", width=120, anchor='w')

        sb_l = ttk.Scrollbar(log_card, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=sb_l.set)
        
        self.log_tree.pack(side='left', fill='both', expand=True)
        sb_l.pack(side='right', fill='y')

        self.refresh()

    def refresh(self):
        self.products = Product.get_all()
        
        # Populate combobox
        p_names = [f"{p.brand} {p.product_name} ({p.barcode})" for p in self.products]
        self.cb_prod.config(values=p_names)
        
        # Populate log table
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
            
        logs = Product.get_inventory_log()
        for r in logs:
            self.log_tree.insert(
                "", "end", 
                values=(r['date'], f"{r['brand']} {r['model']}", r['type'].upper(), r['quantity'], r['reason'])
            )

    def handle_scanner_enter(self, event):
        sku = self.ent_scan.get().strip()
        if not sku: return
        
        p = Product.get_by_sku(sku)
        if p:
            fullname = f"{p.brand} {p.product_name} ({p.barcode})"
            self.cb_prod.set(fullname)
            self.ent_scan.delete(0, 'end')
        else:
            messagebox.showwarning("Warning", f"No product catalog item found for Barcode: {sku}")

    def submit_transaction(self):
        prod_val = self.cb_prod.get()
        tx_type = self.cb_type.get()
        qty_str = self.ent_qty.get().strip()
        reason = self.cb_reason.get()

        if not prod_val or not qty_str or not reason:
            messagebox.showwarning("Warning", "Please complete all mandatory fields.")
            return

        try:
            qty = int(qty_str)
            if qty <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Quantity must be a positive integer.")
            return

        # Identify product ID
        sku = prod_val.split("(")[-1].replace(")", "").strip()
        p = Product.get_by_sku(sku)
        if not p:
            messagebox.showerror("Error", "Product resolution mismatch.")
            return

        # Verification stock out
        if tx_type == 'out':
            stock = Product.get_stock(p.id)
            if stock < qty:
                if not messagebox.askyesno("Warning", f"Current stock is {stock}. Subtracting {qty} creates negative inventory. Continue?"):
                    return

        date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        Product.add_inventory_tx(p.id, tx_type, qty, reason, date_str)
        messagebox.showinfo("Success", "Inventory ledger updated successfully.")
        
        self.cb_prod.set("")
        self.ent_qty.delete(0, 'end')
        self.ent_qty.insert(0, "1")
        self.refresh()


class ImeiFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.active_tab = 'available'
        self.products = []
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="IMEI Inventory Records", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(anchor='w', pady=(0, 20))

        grid = tk.Frame(self, bg=THEME['bg_main'])
        grid.pack(fill='both', expand=True)
        grid.grid_columnconfigure(0, weight=2)
        grid.grid_columnconfigure(1, weight=3)
        grid.grid_rowconfigure(0, weight=1)

        # Left: Register IMEI Card Form
        form_card = tk.Frame(grid, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        form_card.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        
        tk.Label(form_card, text="Register Unique IMEI", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(anchor='w', pady=(0, 15))

        tk.Label(form_card, text="Select Phone Model *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.cb_prod = ttk.Combobox(form_card, state="readonly")
        self.cb_prod.pack(fill='x', pady=(4, 12))

        tk.Label(form_card, text="IMEI / Hardware Serial Code *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_imei = tk.Entry(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_imei.pack(fill='x', ipady=6, pady=(4, 20))

        make_hover_btn(form_card, "REGISTER DEVICE IMEI", THEME['primary'], '#ffffff', self.submit_imei, width=22).pack(anchor='w')

        # Right: IMEI lists and search logs
        list_card = tk.Frame(grid, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        list_card.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        
        list_header = tk.Frame(list_card, bg=THEME['bg_card'])
        list_header.pack(fill='x', pady=(0, 10))
        
        # Search bar
        self.ent_search = tk.Entry(list_header, bg='#090D16', fg='#ffffff', font=("Helvetica", 10), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_search.pack(side='right', fill='x', expand=True, ipady=4, padx=(10, 0))
        self.ent_search.insert(0, "Search IMEI/Phone...")
        self.ent_search.bind("<FocusIn>", lambda e: self.ent_search.delete(0, 'end') if self.ent_search.get() == "Search IMEI/Phone..." else None)
        self.ent_search.bind("<KeyRelease>", lambda e: self.filter_imeis())

        # Tabs available vs sold
        self.btn_avail = make_hover_btn(list_header, "Available", THEME['primary'], '#ffffff', lambda: self.set_tab('available'), width=10)
        self.btn_avail.pack(side='left', padx=2)
        
        self.btn_sold = make_hover_btn(list_header, "Sold Logs", THEME['bg_card'], THEME['text_main'], lambda: self.set_tab('sold'), width=10)
        self.btn_sold.pack(side='left', padx=2)

        # Treeview table
        table_frame = tk.Frame(list_card, bg=THEME['bg_main'])
        table_frame.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(table_frame, columns=("imei", "model", "extra"), show="headings", height=8)
        self.tree.heading("imei", text="IMEI / Serial")
        self.tree.heading("model", text="Phone model")
        self.tree.heading("extra", text="Date / Sale Ref")
        
        self.tree.column("imei", width=130, anchor='center')
        self.tree.column("model", width=140, anchor='w')
        self.tree.column("extra", width=120, anchor='center')

        sb_i = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb_i.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        sb_i.pack(side='right', fill='y')

        # Double click to view details (invoices, client details, warranty expiry)
        self.tree.bind("<Double-1>", self.on_double_click_imei)

        self.refresh()

    def set_tab(self, status):
        self.active_tab = status
        self.btn_avail.config(bg=THEME['primary'] if status == 'available' else THEME['bg_card'])
        self.btn_sold.config(bg=THEME['primary'] if status == 'sold' else THEME['bg_card'])
        self.filter_imeis()

    def refresh(self):
        self.products = Product.get_all()
        # Only list products whose category is "Phones" for the registration dropdown template selection
        phone_products = [p for p in self.products if p.category.lower() == "phones"]
        p_names = [f"{p.brand} {p.product_name} ({p.barcode})" for p in phone_products]
        self.cb_prod.config(values=p_names)
        self.filter_imeis()

    def filter_imeis(self):
        q = self.ent_search.get().strip().lower()
        if q == "search imei/phone...":
            q = ""

        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = Imei.get_all(self.active_tab)
        for r in rows:
            name = f"{r['brand']} {r['model']}"
            if q and not (q in r['imei'].lower() or q in name.lower()):
                continue

            extra_lbl = r['added_date'][:10] if self.active_tab == 'available' else r['sale_id']
            self.tree.insert("", "end", values=(r['imei'], name, extra_lbl))

    def submit_imei(self):
        prod_val = self.cb_prod.get()
        imei = self.ent_imei.get().strip()

        if not prod_val or not imei:
            messagebox.showwarning("Warning", "Please complete all mandatory fields.")
            return

        # Find product template
        sku = prod_val.split("(")[-1].replace(")", "").strip()
        p = Product.get_by_barcode(sku)
        if not p:
            messagebox.showerror("Error", "Product template resolution mismatch.")
            return

        date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if Imei.add(imei, p.id, date_str):
            messagebox.showinfo("Success", f"IMEI '{imei}' registered successfully.")
            self.ent_imei.delete(0, 'end')
            self.cb_prod.set("")
            self.refresh()
        else:
            messagebox.showerror("Error", f"IMEI '{imei}' already exists inside the database.")

    def on_double_click_imei(self, event):
        selected = self.tree.focus()
        if not selected: return
        
        imei_val = self.tree.item(selected)['values'][0]
        row = Imei.get_details(str(imei_val))
        if not row: return
        
        # Details modal
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title(f"Details: {imei_val}")
        modal.geometry("380x300")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text=f"IMEI Code: {imei_val}", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 12, "bold")).pack(pady=15)
        
        details = [
            f"Phone Name: {row['brand']} {row['model']}",
            f"Barcode Code: {row['sku']}",
            f"Status: {row['status'].upper()}",
            f"Registration Date: {row['added_date']}"
        ]
        
        if row['status'] == 'sold':
            details.append(f"Invoice Reference: {row['sale_id']}")
            details.append(f"Client Account: {row['customer_name'] or 'Walk-in Guest'}")
            details.append(f"Sale Timestamp: {row['sale_date']}")
            
            # calculate warranty
            sale_dt = datetime.datetime.strptime(row['sale_date'], '%Y-%m-%d %H:%M:%S')
            expiry = sale_dt + datetime.timedelta(days=365)
            is_active = datetime.datetime.now() < expiry
            w_status = "ACTIVE" if is_active else "EXPIRED"
            details.append(f"Warranty Status (1-Yr): {w_status} (until {expiry.strftime('%Y-%m-%d')})")
            
        for line in details:
            tk.Label(modal, text=line, bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 10)).pack(anchor='w', padx=25, pady=3)

        make_hover_btn(modal, "CLOSE", THEME['primary'], '#ffffff', modal.destroy, width=12).pack(pady=15)
