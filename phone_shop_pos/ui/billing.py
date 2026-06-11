# ui/billing.py
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import sqlite3
from database.db import get_connection
from models.product import Product
from models.customer import Customer
from models.sale import Imei
from services.billing_service import BillingService

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

class BillingFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=20, pady=20)
        self.user_data = user_data
        self.products = []
        self.customers = []
        self.cart = [] # List of dicts: {'product': Product, 'quantity': int, 'price': float, 'cost': float, 'imeis': list}
        self.tax_rate = 18.0
        self.create_widgets()

    def create_widgets(self):
        # Grid layout: left panel vs right panel
        self.grid_columnconfigure(0, weight=4)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # ================= LEFT SIDE: CATALOG & SCANNER =================
        left_panel = tk.Frame(self, bg=THEME['bg_main'])
        left_panel.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        left_panel.grid_rowconfigure(2, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        # Scanner textbox
        scan_card = tk.Frame(left_panel, bg=THEME['bg_card'], padx=12, pady=12, highlightbackground=THEME['border'], highlightthickness=1)
        scan_card.pack(fill='x', pady=(0, 15))
        
        tk.Label(scan_card, text="Scan Barcode or enter SKU / IMEI *", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 10, "bold")).pack(anchor='w')
        
        scan_row = tk.Frame(scan_card, bg=THEME['bg_card'])
        scan_row.pack(fill='x', pady=(6, 0))
        
        self.ent_scan = tk.Entry(scan_row, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 12), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_scan.pack(side='left', fill='x', expand=True, ipady=6, padx=(0, 10))
        self.ent_scan.bind("<Return>", self.handle_barcode_enter)
        self.ent_scan.focus_set()

        make_hover_btn(scan_row, "Add Code", THEME['primary'], '#ffffff', lambda: self.handle_barcode_enter(None), width=12).pack(side='right')

        # Product Catalog list Table
        catalog_card = tk.Frame(left_panel, bg=THEME['bg_card'], padx=15, pady=15, highlightbackground=THEME['border'], highlightthickness=1)
        catalog_card.pack(fill='both', expand=True)
        
        tk.Label(catalog_card, text="Product Inventory Catalog", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 13, "bold")).pack(anchor='w', pady=(0, 10))

        self.catalog_tree = ttk.Treeview(catalog_card, columns=("sku", "name", "price", "stock"), show="headings", height=10)
        self.catalog_tree.heading("sku", text="Barcode / SKU")
        self.catalog_tree.heading("name", text="Product / Brand Model")
        self.catalog_tree.heading("price", text="Price")
        self.catalog_tree.heading("stock", text="Stock")
        
        self.catalog_tree.column("sku", width=100, anchor='center')
        self.catalog_tree.column("name", width=180, anchor='w')
        self.catalog_tree.column("price", width=80, anchor='e')
        self.catalog_tree.column("stock", width=60, anchor='center')

        sb_c = ttk.Scrollbar(catalog_card, orient="vertical", command=self.catalog_tree.yview)
        self.catalog_tree.configure(yscrollcommand=sb_c.set)
        
        self.catalog_tree.pack(side='left', fill='both', expand=True)
        sb_c.pack(side='right', fill='y')

        # Double click to add product
        self.catalog_tree.bind("<Double-1>", self.on_double_click_catalog)

        # ================= RIGHT SIDE: CART & TOTALS =================
        right_panel = tk.Frame(self, bg=THEME['bg_card'], padx=15, pady=15, highlightbackground=THEME['border'], highlightthickness=1)
        right_panel.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        right_panel.grid_rowconfigure(2, weight=1)

        # Customer selection
        cust_row = tk.Frame(right_panel, bg=THEME['bg_card'])
        cust_row.pack(fill='x', pady=(0, 12))
        
        self.cb_customer = ttk.Combobox(cust_row, state="readonly")
        self.cb_customer.pack(side='left', fill='x', expand=True, padx=(0, 8))
        
        make_hover_btn(cust_row, "+ New Customer", THEME['primary'], '#ffffff', self.open_quick_customer_modal, width=15).pack(side='right')

        # Cart Table
        cart_header = tk.Frame(right_panel, bg=THEME['bg_card'])
        cart_header.pack(fill='x', pady=(0, 8))
        tk.Label(cart_header, text="Checkout Register Cart", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 11, "bold")).pack(side='left')

        self.cart_tree = ttk.Treeview(right_panel, columns=("name", "qty", "total"), show="headings", height=8)
        self.cart_tree.heading("name", text="Item details")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("total", text="Total")
        self.cart_tree.column("name", width=180, anchor='w')
        self.cart_tree.column("qty", width=40, anchor='center')
        self.cart_tree.column("total", width=80, anchor='e')
        self.cart_tree.pack(fill='both', expand=True, pady=(0, 12))

        # Totals Panel
        totals_card = tk.Frame(right_panel, bg='#0D131F', padx=12, pady=12, highlightbackground=THEME['border'], highlightthickness=1)
        totals_card.pack(fill='x', pady=(0, 15))

        # Subtotal
        tk.Label(totals_card, text="Subtotal:", bg='#0D131F', fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky='w')
        self.lbl_subtotal = tk.Label(totals_card, text="Rs. 0.00", bg='#0D131F', fg=THEME['text_main'], font=("Helvetica", 10, "bold"))
        self.lbl_subtotal.grid(row=0, column=1, sticky='e')

        # Discount
        tk.Label(totals_card, text="Discount (Rs.):", bg='#0D131F', fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky='w', pady=4)
        self.ent_discount = tk.Entry(totals_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 10), bd=0, width=10, justify='right')
        self.ent_discount.grid(row=1, column=1, sticky='e', pady=4)
        self.ent_discount.insert(0, "0")
        self.ent_discount.bind("<KeyRelease>", lambda e: self.calculate_totals())

        # Tax
        self.lbl_tax_title = tk.Label(totals_card, text="GST (18.0%):", bg='#0D131F', fg=THEME['text_muted'], font=("Helvetica", 9, "bold"))
        self.lbl_tax_title.grid(row=2, column=0, sticky='w')
        self.lbl_tax = tk.Label(totals_card, text="Rs. 0.00", bg='#0D131F', fg=THEME['text_main'], font=("Helvetica", 10, "bold"))
        self.lbl_tax.grid(row=2, column=1, sticky='e')

        # Grand Total
        tk.Label(totals_card, text="GRAND TOTAL:", bg='#0D131F', fg=THEME['success'], font=("Helvetica", 11, "bold")).grid(row=3, column=0, sticky='w', pady=(8, 0))
        self.lbl_total = tk.Label(totals_card, text="Rs. 0.00", bg='#0D131F', fg=THEME['success'], font=("Helvetica", 14, "bold"))
        self.lbl_total.grid(row=3, column=1, sticky='e', pady=(8, 0))

        # Actions buttons
        act_row = tk.Frame(right_panel, bg=THEME['bg_card'])
        act_row.pack(fill='x')
        
        make_hover_btn(act_row, "CLEAR CART", THEME['danger'], '#ffffff', self.clear_cart, width=12).pack(side='left', padx=2)
        make_hover_btn(act_row, "PAY & CHECKOUT", THEME['success'], '#ffffff', self.open_checkout_modal, width=20).pack(side='right', padx=2)

        self.refresh()

    def refresh(self):
        self.products = Product.get_all()
        self.customers = Customer.get_all()
        
        # Load tax settings
        settings = BillingService.get_shop_settings()
        self.tax_rate = float(settings.get('taxRate', 18.0))
        self.lbl_tax_title.config(text=f"GST ({self.tax_rate}%):")

        # Customers combo
        c_names = ["-- Guest Customer --"] + [f"{c.customer_name} ({c.phone})" for c in self.customers]
        self.cb_customer.config(values=c_names)
        self.cb_customer.set("-- Guest Customer --")

        # Redraw Catalog (Only show template models or items with qty > 0)
        # Unique products with barcode = IMEI are template instances
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)
        for p in self.products:
            stock = Product.get_stock(p.id)
            if stock > 0:
                self.catalog_tree.insert("", "end", iid=p.id, values=(p.barcode, f"{p.brand} {p.product_name}", f"Rs. {p.selling_price:.2f}", f"{stock} left"))

    def handle_barcode_enter(self, event):
        code = self.ent_scan.get().strip()
        if not code: return
        self.ent_scan.delete(0, 'end')

        # 1. Search by SKU / Barcode / IMEI directly
        p = Product.get_by_barcode(code)
        if p and p.quantity > 0:
            self.add_product_to_cart(p)
            return

        messagebox.showwarning("Warning", f"No available product or serial code matching: '{code}'")

    def on_double_click_catalog(self, event):
        selected = self.catalog_tree.focus()
        if not selected: return
        p_id = int(selected)
        p = Product.get_by_id(p_id)
        if p:
            self.add_product_to_cart(p)

    def add_product_to_cart(self, product, auto_imei=None):
        # Fetch registered available IMEIs for this product type
        imeis_rows = Imei.get_by_product(product.id, 'available')
        avail_imeis = [r['imei'] for r in imeis_rows]
        
        requires_imei = len(avail_imeis) > 0
        
        # Check if already in cart
        existing = next((item for item in self.cart if item['product'].id == product.id), None)
        
        if requires_imei:
            if auto_imei and auto_imei in avail_imeis:
                self.add_imei_to_cart_item(product, auto_imei, existing)
            else:
                self.open_imei_selection_modal(product, avail_imeis, existing)
        else:
            # Standard item
            stock = Product.get_stock(product.id)
            curr_qty = existing['quantity'] if existing else 0
            if curr_qty + 1 > stock:
                messagebox.showerror("Error", f"Only {stock} items available in stock.")
                return

            if existing:
                existing['quantity'] += 1
            else:
                self.cart.append({
                    'product': product, 'quantity': 1, 'price': product.selling_price, 'cost': product.purchase_price, 'imeis': []
                })
            self.render_cart()

    def add_imei_to_cart_item(self, product, imei, existing):
        # Resolve specific physical product instance matching selected IMEI barcode
        p_instance = Product.get_by_barcode(imei)
        if not p_instance or p_instance.quantity <= 0:
            messagebox.showerror("Error", "Selected device is no longer available.")
            return

        # Verify not already in checkout cart
        already_in_cart = any(item['product'].id == p_instance.id for item in self.cart)
        if already_in_cart:
            messagebox.showwarning("Warning", "Device with this IMEI is already in checkout cart.")
            return

        # Add physical phone instance to checkout cart (quantity is always 1)
        self.cart.append({
            'product': p_instance, 'quantity': 1, 'price': p_instance.selling_price, 'cost': p_instance.purchase_price, 'imeis': [imei]
        })
        
        self.render_cart()
        messagebox.showinfo("Linked", f"Linked IMEI '{imei}' to cart.")

    def open_imei_selection_modal(self, product, avail_imeis, existing):
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title(f"Select IMEI: {product.brand} {product.product_name}")
        modal.geometry("300x320")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Hardware Serial Numbers", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 12, "bold")).pack(pady=12)
        
        # Frame with Listbox
        list_frame = tk.Frame(modal, bg=THEME['bg_card'])
        list_frame.pack(fill='both', expand=True, padx=20, pady=5)

        lb = tk.Listbox(list_frame, selectmode='single', bg='#090D16', fg='#ffffff', font=("Courier", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        lb.pack(side='left', fill='both', expand=True)
        sb = tk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')

        # Populate listbox
        for imei in avail_imeis:
            lb.insert('end', imei)

        def save():
            selections = lb.curselection()
            if not selections:
                messagebox.showwarning("Warning", "Select at least 1 IMEI to add product.", parent=modal)
                return
                
            selected_imei = lb.get(selections[0])
            modal.destroy()
            
            # Add specific device product instance to cart
            self.add_imei_to_cart_item(product, selected_imei, existing)

        make_hover_btn(modal, "ADD SELECTED IMEI", THEME['primary'], '#ffffff', save, width=20).pack(pady=15)

    def render_cart(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
            
        for idx, item in enumerate(self.cart):
            p = item['product']
            name = f"{p.brand} {p.product_name}"
            if item['imeis']:
                name += f" (IMEI: {item['imeis'][0]})"
                
            total = item['price'] * item['quantity']
            self.cart_tree.insert("", "end", iid=idx, values=(name, item['quantity'], f"{total:.2f}"))
            
        self.calculate_totals()

    def calculate_totals(self):
        subtotal = sum(i['price'] * i['quantity'] for i in self.cart)
        
        discount_str = self.ent_discount.get().strip()
        try:
            discount = float(discount_str) if discount_str else 0.0
            if discount < 0: raise ValueError
        except ValueError:
            discount = 0.0
            
        net = max(0.0, subtotal - discount)
        tax = net * (self.tax_rate / 100.0)
        total = net + tax

        self.lbl_subtotal.config(text=f"Rs. {subtotal:.2f}")
        self.lbl_tax.config(text=f"Rs. {tax:.2f}")
        self.lbl_total.config(text=f"Rs. {total:.2f}")

    def clear_cart(self):
        if self.cart and messagebox.askyesno("Confirm", "Are you sure you want to reset the shopping cart?"):
            self.cart = []
            self.render_cart()

    def open_quick_customer_modal(self):
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title("Add New Customer")
        modal.geometry("320x300")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Customer Profile", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=15)

        tk.Label(modal, text="Customer Name *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=20)
        ent_name = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_name.pack(fill='x', ipady=6, padx=20, pady=(4, 12))

        tk.Label(modal, text="Phone Number *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=20)
        ent_phone = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_phone.pack(fill='x', ipady=6, padx=20, pady=(4, 20))

        def submit():
            n = ent_name.get().strip()
            ph = ent_phone.get().strip()
            if not n or not ph:
                messagebox.showwarning("Warning", "All fields are required.", parent=modal)
                return
                
            new_c = Customer(customer_name=n, phone=ph, created_at=datetime.date.today().isoformat())
            if new_c.save():
                messagebox.showinfo("Success", "Customer registered successfully.", parent=modal)
                modal.destroy()
                self.refresh()
                self.cb_customer.set(f"{n} ({ph})")
            else:
                messagebox.showerror("Error", "Phone number already exists in registry.", parent=modal)

        make_hover_btn(modal, "SAVE PROFILE", THEME['primary'], '#ffffff', submit, width=18).pack(pady=10)

    def open_checkout_modal(self):
        if not self.cart:
            messagebox.showwarning("Warning", "Add products to shopping cart to checkout.")
            return

        # Prepare final total calculations
        subtotal = sum(i['price'] * i['quantity'] for i in self.cart)
        
        discount_str = self.ent_discount.get().strip()
        try: discount = float(discount_str) if discount_str else 0.0
        except ValueError: discount = 0.0
        
        net = max(0.0, subtotal - discount)
        tax = net * (self.tax_rate / 100.0)
        total = net + tax

        # Load selected customer
        cust_val = self.cb_customer.get()
        customer_id = None
        if cust_val != "-- Guest Customer --":
            phone = cust_val.split("(")[-1].replace(")", "").strip()
            c = Customer.get_by_phone(phone)
            if c: customer_id = c.id

        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title("Finalize Checkout Order")
        modal.geometry("340x300")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Finalize Order Payment", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=15)

        tk.Label(modal, text="Select Payment Mode *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        cb_pay = ttk.Combobox(modal, values=["Cash", "UPI / QR Code", "Debit/Credit Card"], state="readonly")
        cb_pay.pack(fill='x', padx=25, pady=(4, 15))
        cb_pay.set("Cash")

        tk.Label(modal, text=f"Total Invoice Amount: Rs. {total:.2f}", bg=THEME['bg_card'], fg=THEME['success'], font=("Helvetica", 12, "bold")).pack(pady=10)

        def finalize():
            pay_method = cb_pay.get()
            cashier = self.user_data['username']
            
            success, inv_no = BillingService.checkout(
                self.cart, subtotal, discount, tax, total, pay_method, customer_id, cashier
            )
            if success:
                messagebox.showinfo("Success", f"Checkout successful!\nInvoice {inv_no} created in receipts/ folder.")
                modal.destroy()
                self.cart = []
                self.ent_discount.delete(0, 'end')
                self.ent_discount.insert(0, "0")
                self.render_cart()
                self.refresh()
                
                # Reprint ticket file immediately
                BillingService.reprint_receipt_file(inv_no)
            else:
                messagebox.showerror("Error", "Billing transaction failed.", parent=modal)

        make_hover_btn(modal, "PAY & OPEN RECEIPT", THEME['success'], '#ffffff', finalize, width=22).pack(pady=10)


class CustomersFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.customers = []
        self.create_widgets()

    def create_widgets(self):
        # Header Row
        header = tk.Frame(self, bg=THEME['bg_main'])
        header.pack(fill='x', pady=(0, 20))
        
        tk.Label(header, text="Customer Registry Profiles", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(side='left')
        
        make_hover_btn(header, "+ Register Customer", THEME['primary'], '#ffffff', self.open_customer_modal, width=18).pack(side='right')

        # Search Bar
        search_card = tk.Frame(self, bg=THEME['bg_card'], padx=15, pady=15, highlightbackground=THEME['border'], highlightthickness=1)
        search_card.pack(fill='x', pady=(0, 20))
        
        tk.Label(search_card, text="Search Directory:", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 10, "bold")).pack(side='left', padx=(0, 10))
        
        self.ent_search = tk.Entry(search_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_search.pack(side='left', fill='x', expand=True, ipady=6, padx=(0, 10))
        self.ent_search.bind("<KeyRelease>", lambda e: self.filter_customers())

        make_hover_btn(search_card, "Reset Filters", THEME['bg_main'], THEME['text_main'], self.clear_filters, width=12).pack(side='right')

        # Table Treeview
        table_frame = tk.Frame(self, bg=THEME['bg_main'])
        table_frame.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(table_frame, columns=("name", "phone", "address", "registered"), show="headings", height=10)
        self.tree.heading("name", text="Full Name")
        self.tree.heading("phone", text="Phone Number")
        self.tree.heading("address", text="Address")
        self.tree.heading("registered", text="Date Added")
        
        self.tree.column("name", width=140, anchor='w')
        self.tree.column("phone", width=100, anchor='center')
        self.tree.column("address", width=200, anchor='w')
        self.tree.column("registered", width=100, anchor='center')

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # Bottom actions row
        controls = tk.Frame(self, bg=THEME['bg_main'])
        controls.pack(fill='x', pady=(15, 0))

        make_hover_btn(controls, "Purchase & Warranty Logs", THEME['bg_card'], THEME['text_main'], self.view_customer_ledger, width=22).pack(side='left', padx=4)
        make_hover_btn(controls, "Edit Customer Profile", THEME['bg_card'], THEME['text_main'], self.edit_selected, width=18).pack(side='left', padx=4)

        self.refresh()

    def refresh(self):
        self.customers = Customer.get_all()
        self.filter_customers()

    def filter_customers(self):
        q = self.ent_search.get().strip().lower()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for c in self.customers:
            if q and not (q in c.customer_name.lower() or q in c.phone or (c.address and q in c.address.lower())):
                continue
            self.tree.insert("", "end", iid=c.id, values=(c.customer_name, c.phone, c.address or 'N/A', c.created_at))

    def clear_filters(self):
        self.ent_search.delete(0, 'end')
        self.filter_customers()

    def edit_selected(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a customer to edit.")
            return
        c = Customer.get_by_id(int(selected))
        if c:
            self.open_customer_modal(c)

    def open_customer_modal(self, customer=None):
        is_edit = customer is not None
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title("Edit Customer Profile" if is_edit else "Register Customer Profile")
        modal.geometry("380x365")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Customer Account", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=15)

        # Fields
        tk.Label(modal, text="Full Name *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        ent_name = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_name.pack(fill='x', ipady=5, padx=25, pady=(4, 10))
        if is_edit: ent_name.insert(0, customer.customer_name)

        tk.Label(modal, text="Phone Number *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        ent_phone = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_phone.pack(fill='x', ipady=5, padx=25, pady=(4, 10))
        if is_edit: ent_phone.insert(0, customer.phone)

        tk.Label(modal, text="Billing Address", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=25)
        txt_addr = tk.Text(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, height=3, highlightthickness=1, highlightbackground=THEME['border'])
        txt_addr.pack(fill='x', padx=25, pady=(4, 15))
        if is_edit and customer.address: txt_addr.insert("1.0", customer.address)

        def save():
            n = ent_name.get().strip()
            ph = ent_phone.get().strip()
            addr = txt_addr.get("1.0", "end-1c").strip()
            
            if not n or not ph:
                messagebox.showwarning("Validation Error", "Name and Phone values are required.", parent=modal)
                return
                
            if is_edit:
                customer.customer_name = n
                customer.phone = ph
                customer.address = addr
                if customer.save():
                    messagebox.showinfo("Success", "Customer profile updated.", parent=modal)
                    modal.destroy()
                    self.refresh()
                else:
                    messagebox.showerror("Error", "Phone number matches an existing profile.", parent=modal)
            else:
                new_c = Customer(customer_name=n, phone=ph, address=addr, created_at=datetime.date.today().isoformat())
                if new_c.save():
                    messagebox.showinfo("Success", f"Customer profile created successfully.", parent=modal)
                    modal.destroy()
                    self.refresh()
                else:
                    messagebox.showerror("Error", "Phone number already exists in registry.", parent=modal)

        make_hover_btn(modal, "SAVE CHANGES", THEME['primary'], '#ffffff', save, width=18).pack(pady=10)

    def view_customer_ledger(self):
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a customer to view ledger history.")
            return
            
        c = Customer.get_by_id(int(selected))
        if not c: return
        
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title(f"Ledger: {c.customer_name}")
        modal.geometry("450x450")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text=f"Customer History: {c.customer_name}", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 12, "bold")).pack(pady=10)
        
        # 1. Purchase Invoices List
        tk.Label(modal, text="Sales Invoice Logs", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 10, "bold")).pack(anchor='w', padx=20, pady=(5, 5))
        
        inv_tree = ttk.Treeview(modal, columns=("invoice", "date", "pay", "total"), show="headings", height=5)
        inv_tree.heading("invoice", text="Invoice")
        inv_tree.heading("date", text="Date")
        inv_tree.heading("pay", text="Pay Mode")
        inv_tree.heading("total", text="Grand Total")
        
        inv_tree.column("invoice", width=100, anchor='center')
        inv_tree.column("date", width=110, anchor='center')
        inv_tree.column("pay", width=100, anchor='center')
        inv_tree.column("total", width=90, anchor='e')
        inv_tree.pack(fill='x', padx=20, pady=(0, 15))

        purchases = Customer.get_purchases(c.id)
        for r in purchases:
            inv_tree.insert("", "end", values=(r['invoice_no'], r['sale_date'][:10], r['payment_method'], f"Rs. {r['total_amount']:.2f}"))

        # Bind reprint view double click
        inv_tree.bind("<Double-1>", lambda e: BillingService.reprint_receipt_file(inv_tree.item(inv_tree.focus())['values'][0]) if inv_tree.focus() else None)

        # 2. Warranty serial list
        tk.Label(modal, text="Hardware Warranties (1-Yr Coverage)", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 10, "bold")).pack(anchor='w', padx=20, pady=(5, 5))
        
        w_tree = ttk.Treeview(modal, columns=("imei", "model", "term", "status"), show="headings", height=5)
        w_tree.heading("imei", text="IMEI Code")
        w_tree.heading("model", text="Phone model")
        w_tree.heading("term", text="Warranty Term")
        w_tree.heading("status", text="Status")
        
        w_tree.column("imei", width=110, anchor='center')
        w_tree.column("model", width=120, anchor='w')
        w_tree.column("term", width=110, anchor='center')
        w_tree.column("status", width=70, anchor='center')
        w_tree.pack(fill='x', padx=20, pady=(0, 15))

        # Calculate warranties
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.barcode as imei, p.brand, p.product_name as model, s.date
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.customer_id = ? AND length(p.barcode) >= 8;
            """,
            (c.id,)
        )
        w_rows = cursor.fetchall()
        conn.close()

        for w in w_rows:
            sale_dt = datetime.datetime.strptime(w['date'], '%Y-%m-%d %H:%M:%S')
            expiry = sale_dt + datetime.timedelta(days=365)
            is_active = datetime.datetime.now() < expiry
            w_status = "Active" if is_active else "Expired"
            
            w_tree.insert(
                "", "end", 
                values=(w['imei'], f"{w['brand']} {w['model']}", f"{w['date'][:10]} to {expiry.strftime('%Y-%m-%d')}", w_status)
            )

        make_hover_btn(modal, "CLOSE LEDGER", THEME['primary'], '#ffffff', modal.destroy, width=15).pack()
