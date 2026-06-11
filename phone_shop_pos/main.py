# main.py
import sys
import os
import tkinter as tk
from tkinter import messagebox

# Startup Validation Function
def validate_packages():
    """
    Checks that core package directories and their __init__.py files exist.
    """
    required_packages = ['database', 'models', 'services', 'ui']
    missing = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for pkg in required_packages:
        pkg_path = os.path.join(base_dir, pkg)
        init_file = os.path.join(pkg_path, '__init__.py')
        if not os.path.isdir(pkg_path) or not os.path.exists(init_file):
            missing.append(pkg)
            
    if missing:
        error_msg = (
            "Startup Validation Error:\n"
            "The following required package directories or __init__.py files are missing:\n" +
            "\n".join(f"- {pkg}/" for pkg in missing) +
            "\n\nPlease ensure all project folders are valid packages and you run the application from the root phone_shop_pos/ folder."
        )
        print(error_msg, file=sys.stderr)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Startup Error", error_msg)
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

validate_packages()

# Create relative import mapping
from database.db import init_db
from ui.login import LoginFrame
from ui.dashboard import DashboardFrame, ReportsFrame, SettingsFrame, BackupFrame
from ui.products import ProductsFrame, InventoryFrame, ImeiFrame
from ui.billing import BillingFrame, CustomersFrame

THEME = {
    'bg_main': '#0F172A',
    'bg_sidebar': '#0F172A',
    'border': '#334155',
    'text_main': '#F8FAFC',
    'text_muted': '#94A3B8',
    'primary': '#6366F1',
    'primary_hover': '#4F46E5',
    'danger': '#EF4444'
}

class PhoneShopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phone Shop POS System (Offline Terminal)")
        self.geometry("1150x700")
        self.minsize(1050, 650)
        self.configure(bg=THEME['bg_main'])
        
        self.user_data = None
        self.active_btn = None
        self.content_frame = None

        # 1. Initialize Directories
        self.init_directories()

        # 2. Initialize Database Tables
        try:
            init_db()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize SQLite database:\n{str(e)}")
            self.destroy()
            return

        # 3. Mount Container
        self.container = tk.Frame(self, bg=THEME['bg_main'])
        self.container.pack(fill='both', expand=True)

        self.show_login_screen()

    def init_directories(self):
        """Creates output folders if they do not exist."""
        folders = ['barcodes', 'receipts', 'backups']
        for f in folders:
            if not os.path.exists(f):
                os.makedirs(f)

    def show_login_screen(self):
        """Displays full screen login page."""
        self.clear_container()
        self.login_view = LoginFrame(self.container, self.on_login_success)
        self.login_view.pack(fill='both', expand=True)

    def on_login_success(self, user_data):
        self.user_data = user_data
        self.show_main_workspace()

    def show_main_workspace(self):
        self.clear_container()

        # Split frame: Left Sidebar & Right Main Container
        self.workspace = tk.Frame(self.container, bg=THEME['bg_main'])
        self.workspace.pack(fill='both', expand=True)

        # 1. Sidebar Frame
        self.sidebar = tk.Frame(self.workspace, bg=THEME['bg_sidebar'], width=240, highlightbackground=THEME['border'], highlightthickness=1)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        # Brand Logo
        brand_frame = tk.Frame(self.sidebar, bg=THEME['bg_sidebar'], pady=20)
        brand_frame.pack(fill='x', side='top')
        
        logo = tk.Label(brand_frame, text="P", bg=THEME['primary'], fg='#ffffff', font=("Helvetica", 14, "bold"), width=3)
        logo.pack(side='left', padx=(20, 10))
        
        tk.Label(brand_frame, text="PhonePOS", bg=THEME['bg_sidebar'], fg=THEME['text_main'], font=("Helvetica", 13, "bold")).pack(side='left')

        tk.Frame(self.sidebar, bg=THEME['border'], height=1).pack(fill='x', side='top', pady=(0, 10))

        # Menu List Buttons
        self.menu_buttons = {}
        
        # Format: (Label, Class, AdminOnly)
        menu_items = [
            ("Dashboard", DashboardFrame, False),
            ("Billing / POS", BillingFrame, False),
            ("Products Catalog", ProductsFrame, False),
            ("Stock Adjustments", InventoryFrame, False),
            ("IMEI Management", ImeiFrame, False),
            ("Customer Registry", CustomersFrame, False),
            ("Profit Reports", ReportsFrame, True),
            ("Database Backup", BackupFrame, True),
            ("Store Settings", SettingsFrame, True)
        ]

        for label, view_class, admin_only in menu_items:
            # If user is cashier, skip rendering AdminOnly views
            if admin_only and self.user_data['role'] == 'cashier':
                continue
                
            btn = tk.Button(
                self.sidebar, text=f"  {label}", anchor='w', bg=THEME['bg_sidebar'], fg=THEME['text_muted'],
                activebackground=THEME['primary'], activeforeground='#ffffff', font=("Helvetica", 10, "bold"),
                bd=0, relief="flat", cursor="hand2", height=2
            )
            btn.pack(fill='x', padx=10, pady=2)
            
            # Action mapping
            btn.config(command=lambda b=btn, c=view_class: self.switch_view(b, c))
            
            # Hover bindings
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg='#ffffff', bg='#222E42') if b != self.active_btn else None)
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg=THEME['text_muted'], bg=THEME['bg_sidebar']) if b != self.active_btn else None)
            
            self.menu_buttons[label] = btn

        # Bottom Session frame
        session_frame = tk.Frame(self.sidebar, bg=THEME['bg_sidebar'], pady=15, highlightbackground=THEME['border'], highlightthickness=1)
        session_frame.pack(fill='x', side='bottom')
        
        info_f = tk.Frame(session_frame, bg=THEME['bg_sidebar'])
        info_f.pack(side='left', padx=15)
        
        tk.Label(info_f, text=self.user_data['username'], bg=THEME['bg_sidebar'], fg=THEME['text_main'], font=("Helvetica", 10, "bold")).pack(anchor='w')
        tk.Label(info_f, text=self.user_data['role'].upper(), bg=THEME['bg_sidebar'], fg=THEME['text_muted'], font=("Helvetica", 8, "bold")).pack(anchor='w')

        logout_btn = tk.Button(
            session_frame, text="Out", bg=THEME['danger'], fg='#ffffff', activebackground='#b91c1c', activeforeground='#ffffff',
            font=("Helvetica", 9, "bold"), bd=0, cursor="hand2", padx=10, command=self.handle_logout
        )
        logout_btn.pack(side='right', padx=15)

        # 2. Right Content Frame
        self.right_workspace = tk.Frame(self.workspace, bg=THEME['bg_main'])
        self.right_workspace.pack(side='right', fill='both', expand=True)

        # Initialize Default view to Dashboard
        first_btn = self.menu_buttons["Dashboard"]
        self.switch_view(first_btn, DashboardFrame)

    def switch_view(self, button, view_class):
        # Reset old active button visuals
        if self.active_btn:
            self.active_btn.config(bg=THEME['bg_sidebar'], fg=THEME['text_muted'])
            
        # Set new active button
        self.active_btn = button
        self.active_btn.config(bg=THEME['primary'], fg='#ffffff')

        # Clean content view
        if self.content_frame:
            self.content_frame.destroy()

        # Mount new view frame
        self.content_frame = view_class(self.right_workspace, self.user_data)
        self.content_frame.pack(fill='both', expand=True)

    def handle_logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to sign out?"):
            self.user_data = None
            self.active_btn = None
            self.content_frame = None
            self.show_login_screen()

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    app = PhoneShopApp()
    app.mainloop()
