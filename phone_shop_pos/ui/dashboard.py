# ui/dashboard.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sqlite3
from database.db import get_connection
from services.report_service import ReportService
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

def make_hover_btn(parent, text, bg, fg, command, width=15, font_size=10):
    btn = tk.Button(
        parent, text=text, bg=bg, fg=fg, activebackground=THEME['primary_hover'], activeforeground='#ffffff',
        font=("Helvetica", font_size, "bold"), bd=0, relief="flat", cursor="hand2", command=command, width=width
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=THEME['primary_hover'] if bg == THEME['primary'] else '#2A3B50'))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn

class DashboardFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.create_widgets()

    def create_widgets(self):
        # 1. Header
        header_frame = tk.Frame(self, bg=THEME['bg_main'])
        header_frame.pack(fill='x', pady=(0, 20))
        
        tk.Label(
            header_frame, text="Dashboard Overview", bg=THEME['bg_main'], fg=THEME['text_main'],
            font=("Helvetica", 20, "bold")
        ).pack(side='left')
        
        self.lbl_date = tk.Label(
            header_frame, text="", bg=THEME['bg_main'], fg=THEME['text_muted'],
            font=("Helvetica", 11, "bold")
        ).pack(side='right')

        # 2. KPI Cards Row
        kpi_frame = tk.Frame(self, bg=THEME['bg_main'])
        kpi_frame.pack(fill='x', pady=(0, 25))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.cards = {}
        labels = [
            ("Today's Revenue", 'success', 'rev'),
            ("Today's Transactions", 'primary', 'tx'),
            ("Today's Profit", 'success', 'profit'),
            ("Total Stock Count", 'warning', 'stock')
        ]

        for idx, (label, color, key) in enumerate(labels):
            card = tk.Frame(kpi_frame, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
            card.grid(row=0, column=idx, padx=8, sticky='nsew')
            
            tk.Label(card, text=label, bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
            
            val_lbl = tk.Label(card, text="0", bg=THEME['bg_card'], fg=THEME[color], font=("Helvetica", 22, "bold"))
            val_lbl.pack(anchor='w', pady=(8, 0))
            self.cards[key] = val_lbl

        # 3. Main content splits: Chart (left) & Low Stock Alerts (right)
        splits = tk.Frame(self, bg=THEME['bg_main'])
        splits.pack(fill='both', expand=True)
        splits.grid_columnconfigure(0, weight=3)
        splits.grid_columnconfigure(1, weight=2)
        splits.grid_rowconfigure(0, weight=1)

        # Weekly Trend Chart Frame
        chart_card = tk.Frame(splits, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        chart_card.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        
        tk.Label(chart_card, text="Weekly Sales Trend", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(anchor='w', pady=(0, 15))
        
        self.canvas = tk.Canvas(chart_card, bg='#0D131F', bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.canvas.pack(fill='both', expand=True)

        # Low Stock Alerts Frame
        alerts_card = tk.Frame(splits, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        alerts_card.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        
        tk.Label(alerts_card, text="Low Stock Alerts", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(anchor='w', pady=(0, 15))
        
        # Alerts Table
        table_frame = tk.Frame(alerts_card, bg=THEME['bg_card'])
        table_frame.pack(fill='both', expand=True)
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=THEME['bg_card'], fieldbackground=THEME['bg_card'], foreground=THEME['text_main'], borderwidth=0, font=("Helvetica", 10))
        style.configure("Treeview.Heading", background='#0F172A', foreground=THEME['text_muted'], font=("Helvetica", 9, "bold"))
        style.map("Treeview", background=[('selected', THEME['primary'])])

        self.tree = ttk.Treeview(table_frame, columns=("product", "stock"), show="headings", height=8)
        self.tree.heading("product", text="Product / Model")
        self.tree.heading("stock", text="Stock")
        self.tree.column("product", width=180, anchor='w')
        self.tree.column("stock", width=70, anchor='center')
        
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.refresh()

    def refresh(self):
        # Refresh KPI cards
        metrics = ReportService.get_dashboard_metrics()
        self.cards['rev'].config(text=f"Rs. {metrics['today_revenue']:.2f}")
        self.cards['tx'].config(text=str(metrics['today_transactions']))
        self.cards['profit'].config(text=f"Rs. {metrics['today_profit']:.2f}")
        self.cards['stock'].config(text=str(metrics['total_stock']))

        # Populate low stock alerts table
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        alerts = ReportService.get_low_stock_alerts()
        for a in alerts:
            self.tree.insert("", "end", values=(a['name'], f"{a['stock']} left"))

        # Redraw week chart
        self.draw_weekly_chart()

    def draw_weekly_chart(self):
        self.canvas.update()
        self.canvas.delete("all")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return
            
        pad_l = 45
        pad_r = 20
        pad_t = 20
        pad_b = 30
        
        trend = ReportService.get_weekly_trend()
        max_val = max([t[1] for t in trend] + [1000.0]) * 1.15
        
        step_x = (w - pad_l - pad_r) / 6
        points = []
        
        # Draw background grids
        grid_lines = 4
        for i in range(grid_lines + 1):
            val = (max_val / grid_lines) * i
            y = h - pad_b - (i / grid_lines) * (h - pad_t - pad_b)
            self.canvas.create_line(pad_l, y, w - pad_r, y, fill=THEME['border'], dash=(3, 3))
            
            lbl_val = f"Rs.{val/1000:.1f}k" if val >= 1000 else f"Rs.{val:.0f}"
            self.canvas.create_text(pad_l - 8, y, text=lbl_val, fill=THEME['text_muted'], anchor='e', font=("Helvetica", 8))

        # Plot trend coordinates
        for idx, (day, val) in enumerate(trend):
            x = pad_l + idx * step_x
            y = h - pad_b - (val / max_val) * (h - pad_t - pad_b)
            points.append((x, y, val))
            
            # X day tags
            self.canvas.create_text(x, h - 12, text=day, fill=THEME['text_muted'], font=("Helvetica", 9))

        # Draw line & fill polygon area
        poly_points = [pad_l, h - pad_b]
        for p in points:
            poly_points.extend([p[0], p[1]])
        poly_points.extend([w - pad_r, h - pad_b])
        
        # Flat area fill
        self.canvas.create_polygon(poly_points, fill='#1B254B', outline="")
        
        # Connect trend line
        for i in range(len(points) - 1):
            self.canvas.create_line(
                points[i][0], points[i][1], points[i+1][0], points[i+1][1], 
                fill=THEME['primary'], width=3, capstyle='round'
            )
            
        # Draw nodes
        for p in points:
            self.canvas.create_oval(
                p[0]-4, p[1]-4, p[0]+4, p[1]+4, 
                fill=THEME['primary'], outline='#0D131F', width=2
            )


class ReportsFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.active_range = 'today'
        self.create_widgets()

    def create_widgets(self):
        # Header & Filter
        header = tk.Frame(self, bg=THEME['bg_main'])
        header.pack(fill='x', pady=(0, 20))
        
        tk.Label(header, text="Sales & Profit Reports", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(side='left')
        
        filter_bar = tk.Frame(header, bg=THEME['bg_main'])
        filter_bar.pack(side='right')
        
        self.btn_today = make_hover_btn(filter_bar, "Today", THEME['primary'], '#ffffff', lambda: self.set_range('today'), width=10)
        self.btn_today.pack(side='left', padx=4)
        
        self.btn_month = make_hover_btn(filter_bar, "This Month", THEME['bg_card'], THEME['text_main'], lambda: self.set_range('month'), width=12)
        self.btn_month.pack(side='left', padx=4)

        self.btn_all = make_hover_btn(filter_bar, "All-Time", THEME['bg_card'], THEME['text_main'], lambda: self.set_range('all'), width=10)
        self.btn_all.pack(side='left', padx=4)

        # Financial summaries
        summary = tk.Frame(self, bg=THEME['bg_main'])
        summary.pack(fill='x', pady=(0, 25))
        summary.grid_columnconfigure((0, 1, 2), weight=1)
        
        labels = [("Gross Revenue", 'success', 'rev'), ("Cost of Goods (COGS)", 'primary', 'cogs'), ("Net Profit Margin", 'success', 'profit')]
        self.summaries = {}
        for idx, (lbl, color, key) in enumerate(labels):
            card = tk.Frame(summary, bg=THEME['bg_card'], padx=15, pady=15, highlightbackground=THEME['border'], highlightthickness=1)
            card.grid(row=0, column=idx, padx=6, sticky='nsew')
            tk.Label(card, text=lbl, bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
            val = tk.Label(card, text="Rs. 0.00", bg=THEME['bg_card'], fg=THEME[color], font=("Helvetica", 18, "bold"))
            val.pack(anchor='w', pady=(5, 0))
            self.summaries[key] = val

        # Bottom content split tables
        split = tk.Frame(self, bg=THEME['bg_main'])
        split.pack(fill='both', expand=True)
        split.grid_columnconfigure(0, weight=3)
        split.grid_columnconfigure(1, weight=2)
        split.grid_rowconfigure(0, weight=1)

        # Sales List (left)
        sales_card = tk.Frame(split, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        sales_card.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        
        tk.Label(sales_card, text="Sales Log invoices", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 13, "bold")).pack(anchor='w', pady=(0, 10))
        
        self.sales_tree = ttk.Treeview(sales_card, columns=("invoice", "date", "customer", "amount", "profit"), show="headings", height=8)
        self.sales_tree.heading("invoice", text="Invoice")
        self.sales_tree.heading("date", text="Date")
        self.sales_tree.heading("customer", text="Customer")
        self.sales_tree.heading("amount", text="Total")
        self.sales_tree.heading("profit", text="Profit")
        
        self.sales_tree.column("invoice", width=100, anchor='center')
        self.sales_tree.column("date", width=120, anchor='center')
        self.sales_tree.column("customer", width=120, anchor='w')
        self.sales_tree.column("amount", width=80, anchor='e')
        self.sales_tree.column("profit", width=80, anchor='e')
        
        sb_s = ttk.Scrollbar(sales_card, orient="vertical", command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=sb_s.set)
        self.sales_tree.pack(side='left', fill='both', expand=True)
        sb_s.pack(side='right', fill='y')

        # Double click to view text receipt
        self.sales_tree.bind("<Double-1>", self.on_double_click_invoice)

        # Best sellers ranking (right)
        ranking_card = tk.Frame(split, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        ranking_card.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        
        tk.Label(ranking_card, text="Top Selling Products", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 13, "bold")).pack(anchor='w', pady=(0, 10))
        
        self.rank_tree = ttk.Treeview(ranking_card, columns=("product", "qty", "revenue"), show="headings", height=8)
        self.rank_tree.heading("product", text="Model")
        self.rank_tree.heading("qty", text="Sold Qty")
        self.rank_tree.heading("revenue", text="Revenue")
        self.rank_tree.column("product", width=160, anchor='w')
        self.rank_tree.column("qty", width=60, anchor='center')
        self.rank_tree.column("revenue", width=90, anchor='e')
        
        sb_r = ttk.Scrollbar(ranking_card, orient="vertical", command=self.rank_tree.yview)
        self.rank_tree.configure(yscrollcommand=sb_r.set)
        self.rank_tree.pack(side='left', fill='both', expand=True)
        sb_r.pack(side='right', fill='y')

        self.refresh()

    def set_range(self, val):
        self.active_range = val
        self.btn_today.config(bg=THEME['primary'] if val == 'today' else THEME['bg_card'])
        self.btn_month.config(bg=THEME['primary'] if val == 'month' else THEME['bg_card'])
        self.btn_all.config(bg=THEME['primary'] if val == 'all' else THEME['bg_card'])
        self.refresh()

    def refresh(self):
        data = ReportService.get_financial_reports(self.active_range)
        self.summaries['rev'].config(text=f"Rs. {data['total_revenue']:.2f}")
        self.summaries['cogs'].config(text=f"Rs. {data['total_cogs']:.2f}")
        self.summaries['profit'].config(text=f"Rs. {data['net_profit']:.2f}")

        # populate sales logs
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        for s in data['invoices']:
            self.sales_tree.insert(
                "", "end", 
                values=(s['invoice'], s['date'], s['customer'], f"{s['amount']:.2f}", f"{s['profit']:.2f}")
            )

        # populate best sellers
        for item in self.rank_tree.get_children():
            self.rank_tree.delete(item)
        for r in data['bestsellers']:
            self.rank_tree.insert("", "end", values=(f"{r['brand']} {r['model']}", r['units'], f"{r['rev']:.2f}"))

    def on_double_click_invoice(self, event):
        selected = self.sales_tree.focus()
        if not selected:
            return
        inv_no = self.sales_tree.item(selected)['values'][0]
        if not BillingService.reprint_receipt_file(inv_no):
            messagebox.showerror("Error", f"Could not find receipt file for {inv_no}.")


class SettingsFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.create_widgets()

    def create_widgets(self):
        # Header
        tk.Label(self, text="Store Settings", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(anchor='w', pady=(0, 20))

        splits = tk.Frame(self, bg=THEME['bg_main'])
        splits.pack(fill='both', expand=True)
        splits.grid_columnconfigure(0, weight=3)
        splits.grid_columnconfigure(1, weight=2)
        splits.grid_rowconfigure(0, weight=1)

        # Left: Shop Meta Settings Form
        form_card = tk.Frame(splits, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        form_card.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        
        tk.Label(form_card, text="Shop Configurations", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(anchor='w', pady=(0, 15))

        # Fields
        tk.Label(form_card, text="Store Name *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_name = tk.Entry(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_name.pack(fill='x', ipady=6, pady=(4, 12))

        tk.Label(form_card, text="Contact Phone *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_phone = tk.Entry(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_phone.pack(fill='x', ipady=6, pady=(4, 12))

        tk.Label(form_card, text="Contact Email Address", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_email = tk.Entry(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_email.pack(fill='x', ipady=6, pady=(4, 12))

        tk.Label(form_card, text="Sales GST Tax Rate (%) *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_tax = tk.Entry(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        self.ent_tax.pack(fill='x', ipady=6, pady=(4, 12))

        tk.Label(form_card, text="Store Billing Address *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.txt_address = tk.Text(form_card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, height=2, highlightthickness=1, highlightbackground=THEME['border'])
        self.txt_address.pack(fill='x', pady=(4, 20))

        make_hover_btn(form_card, "SAVE SHOP DETAILS", THEME['primary'], '#ffffff', self.save_configurations, width=22).pack(anchor='w')

        # Right: User Access Controls (Admin only view list)
        user_card = tk.Frame(splits, bg=THEME['bg_card'], padx=20, pady=20, highlightbackground=THEME['border'], highlightthickness=1)
        user_card.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        
        user_header = tk.Frame(user_card, bg=THEME['bg_card'])
        user_header.pack(fill='x', pady=(0, 15))
        tk.Label(user_header, text="User Accounts", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(side='left')
        make_hover_btn(user_header, "+ Add User", THEME['primary'], '#ffffff', self.open_user_modal, width=12, font_size=8).pack(side='right')

        # User List table
        self.user_tree = ttk.Treeview(user_card, columns=("username", "role"), show="headings", height=8)
        self.user_tree.heading("username", text="Username")
        self.user_tree.heading("role", text="Role")
        self.user_tree.column("username", width=120, anchor='w')
        self.user_tree.column("role", width=80, anchor='center')
        self.user_tree.pack(fill='both', expand=True, pady=(0, 10))

        make_hover_btn(user_card, "DELETE SELECTED USER", THEME['danger'], '#ffffff', self.delete_selected_user, width=22).pack(fill='x')

        self.refresh()

    def refresh(self):
        # Load details
        settings = BillingService.get_shop_settings()
        self.ent_name.delete(0, 'end')
        self.ent_name.insert(0, settings.get('shopName', ''))
        
        self.ent_phone.delete(0, 'end')
        self.ent_phone.insert(0, settings.get('shopPhone', ''))
        
        self.ent_email.delete(0, 'end')
        self.ent_email.insert(0, settings.get('shopEmail', ''))
        
        self.ent_tax.delete(0, 'end')
        self.ent_tax.insert(0, settings.get('taxRate', '18.0'))
        
        self.txt_address.delete("1.0", 'end')
        self.txt_address.insert("1.0", settings.get('shopAddress', ''))

        # Load users list
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users;")
        users = cursor.fetchall()
        conn.close()
        
        for u in users:
            self.user_tree.insert("", "end", values=(u['username'], u['role']))

    def save_configurations(self):
        name = self.ent_name.get().strip()
        phone = self.ent_phone.get().strip()
        email = self.ent_email.get().strip()
        tax = self.ent_tax.get().strip()
        address = self.txt_address.get("1.0", "end-1c").strip()

        if not name or not phone or not tax or not address:
            messagebox.showwarning("Validation Error", "All fields marked with (*) are required.")
            return

        try:
            float(tax)
        except ValueError:
            messagebox.showerror("Error", "Tax rate must be a valid number.")
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopName';", (name,))
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopPhone';", (phone,))
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopEmail';", (email,))
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'taxRate';", (tax,))
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'shopAddress';", (address,))
        conn.commit()
        conn.close()
        
        messagebox.showinfo("Success", "Shop settings updated successfully.")
        self.refresh()

    def open_user_modal(self):
        modal = tk.Toplevel(self, bg=THEME['bg_card'])
        modal.title("Add New User")
        modal.geometry("320x340")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        tk.Label(modal, text="Create User Account", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=15)

        # Fields
        tk.Label(modal, text="Username *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=20)
        ent_u = tk.Entry(modal, bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_u.pack(fill='x', ipady=6, padx=20, pady=(4, 10))

        tk.Label(modal, text="Password *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=20)
        ent_p = tk.Entry(modal, show="*", bg='#090D16', fg='#ffffff', insertbackground='#ffffff', font=("Helvetica", 11), bd=0, highlightthickness=1, highlightbackground=THEME['border'])
        ent_p.pack(fill='x', ipady=6, padx=20, pady=(4, 10))

        tk.Label(modal, text="Role *", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w', padx=20)
        cb_role = ttk.Combobox(modal, values=["cashier", "admin"], state="readonly")
        cb_role.pack(fill='x', padx=20, pady=(4, 20))
        cb_role.set("cashier")

        def submit():
            u = ent_u.get().strip()
            p = ent_p.get().strip()
            r = cb_role.get()
            
            if not u or not p:
                messagebox.showwarning("Validation Error", "All fields are required.", parent=modal)
                return
                
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?);", (u, p, r))
                conn.commit()
                messagebox.showinfo("Success", f"User '{u}' registered successfully.", parent=modal)
                modal.destroy()
                self.refresh()
            except sqlite3.IntegrityError:
                messagebox.showerror("Auth Error", "Username already exists.", parent=modal)
            finally:
                conn.close()

        make_hover_btn(modal, "CREATE ACCOUNT", THEME['primary'], '#ffffff', submit, width=20).pack(pady=10)

    def delete_selected_user(self):
        selected = self.user_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a user to delete first.")
            return
            
        username = self.user_tree.item(selected)['values'][0]
        if username == 'admin':
            messagebox.showerror("Locked", "The primary system 'admin' account cannot be deleted.")
            return
            
        if confirm(f"Are you sure you want to delete user '{username}'?"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?;", (username,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "User account deleted.")
            self.refresh()


class BackupFrame(tk.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, bg=THEME['bg_main'], padx=25, pady=25)
        self.user_data = user_data
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="Backup & Restore", bg=THEME['bg_main'], fg=THEME['text_main'], font=("Helvetica", 20, "bold")).pack(anchor='w', pady=(0, 20))

        grid = tk.Frame(self, bg=THEME['bg_main'])
        grid.pack(fill='both', expand=True)
        grid.grid_columnconfigure((0, 1), weight=1)
        grid.grid_rowconfigure(0, weight=1)

        # Export (left)
        ex_card = tk.Frame(grid, bg=THEME['bg_card'], padx=30, pady=45, highlightbackground=THEME['border'], highlightthickness=1)
        ex_card.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        
        tk.Label(ex_card, text="Export Database", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=(0, 10))
        tk.Label(
            ex_card, text="Saves a copy of your products, stock counts, customers, sales receipts, and system configurations. Downloads a single JSON backup file.",
            bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9), wraplength=260, justify='center'
        ).pack(pady=(0, 30))
        
        make_hover_btn(ex_card, "EXPORT DATA NOW", THEME['success'], '#ffffff', self.export_backup, width=22).pack()

        # Import (right)
        im_card = tk.Frame(grid, bg=THEME['bg_card'], padx=30, pady=45, highlightbackground=THEME['border'], highlightthickness=1)
        im_card.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        
        tk.Label(im_card, text="Import Restore", bg=THEME['bg_card'], fg=THEME['text_main'], font=("Helvetica", 14, "bold")).pack(pady=(0, 10))
        tk.Label(
            im_card, text="Restore your workspace configurations from an existing JSON file. Warning: This action overwrites all current system records.",
            bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9), wraplength=260, justify='center'
        ).pack(pady=(0, 30))
        
        make_hover_btn(im_card, "RUN RESTORE OPERATION", THEME['danger'], '#ffffff', self.import_backup, width=22).pack()

    def export_backup(self):
        tables = ['users', 'products', 'inventory', 'imeis', 'sales', 'sale_items', 'customers', 'settings']
        data = {}
        
        conn = get_connection()
        cursor = conn.cursor()
        for t in tables:
            cursor.execute(f"SELECT * FROM {t};")
            rows = cursor.fetchall()
            data[t] = [dict(r) for r in rows]
        conn.close()

        # Make backup directory
        if not os.path.exists("backups"):
            os.makedirs("backups")
            
        date_str = datetime.date.today().strftime('%Y-%m-%d')
        default_file = os.path.join("backups", f"phoneshop_backup_{date_str}.json")
        
        filepath = filedialog.asksaveasfilename(
            initialfile=os.path.basename(default_file),
            initialdir="backups",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        
        if filepath:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Success", "Backup generated and saved successfully.")

    def import_backup(self):
        filepath = filedialog.askopenfilename(
            initialdir="backups",
            filetypes=[("JSON Files", "*.json")]
        )
        if not filepath:
            return
            
        if not confirm("Are you sure you want to perform a restore? Current products, inventory counts, and invoices will be deleted. This cannot be undone."):
            return
            
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                
            required = ['users', 'products', 'inventory', 'imeis', 'sales', 'sale_items', 'customers', 'settings']
            if not all(k in data for k in required):
                messagebox.showerror("Error", "Invalid backup file structure.")
                return

            conn = get_connection()
            cursor = conn.cursor()
            
            # Disable foreign keys temporarily during truncate/inserts
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            # Clear all
            for t in required:
                cursor.execute(f"DELETE FROM {t};")
                
            # Insert data
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
            
            messagebox.showinfo("Success", "System data restored successfully! The application requires restarting.")
            os._exit(0) # Terminate to force clean reload
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore: {str(e)}")


def confirm(msg):
    return messagebox.askyesno("Confirm Action", msg)
