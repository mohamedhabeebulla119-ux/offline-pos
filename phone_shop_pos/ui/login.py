# ui/login.py
import os
import sqlite3
import tkinter as tk
from tkinter import messagebox as tk_messagebox

# Import DatabaseManager
from database.db import get_connection, DatabaseManager

# Import PyQt6 components
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal

# Keep existing Tkinter theme for backwards compatibility
THEME = {
    'bg_main': '#0F172A',
    'bg_card': '#1E293B',
    'border': '#334155',
    'text_main': '#F8FAFC',
    'text_muted': '#94A3B8',
    'primary': '#6366F1',
    'primary_hover': '#4F46E5',
    'success': '#10B981',
    'danger': '#EF4444'
}

def create_default_admin_if_empty():
    """
    Checks if the users table is empty and creates a default admin user.
    """
    try:
        db = DatabaseManager()
        cursor = db.get_cursor()
        cursor.execute("SELECT COUNT(*) FROM users;")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?);",
                ("admin", "admin123", "admin")
            )
            db.commit()
        db.close()
    except Exception as e:
        print(f"Error checking/creating default admin user: {e}")

# --- LEGACY TKINTER LOGIN FRAME FOR BACKWARD COMPATIBILITY ---
class LoginFrame(tk.Frame):
    def __init__(self, parent, on_login_success):
        super().__init__(parent, bg=THEME['bg_main'])
        self.on_login_success = on_login_success
        create_default_admin_if_empty()
        self.create_widgets()

    def create_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = tk.Frame(self, bg=THEME['bg_card'], padx=40, pady=40, highlightbackground=THEME['border'], highlightthickness=1)
        card.grid(row=0, column=0)

        logo_label = tk.Label(
            card, text="P", bg=THEME['primary'], fg='#ffffff',
            font=("Helvetica", 24, "bold"), width=3, height=1
        )
        logo_label.pack(pady=(0, 15))

        title = tk.Label(
            card, text="Phone Shop POS", bg=THEME['bg_card'], fg=THEME['text_main'],
            font=("Helvetica", 18, "bold")
        )
        title.pack()

        subtitle = tk.Label(
            card, text="Offline Billing Terminal", bg=THEME['bg_card'], fg=THEME['text_muted'],
            font=("Helvetica", 10)
        )
        subtitle.pack(pady=(0, 30))

        tk.Label(card, text="USERNAME", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_username = tk.Entry(
            card, bg='#090D16', fg='#ffffff', insertbackground='#ffffff',
            font=("Helvetica", 12), bd=0, highlightthickness=1, highlightbackground=THEME['border'], highlightcolor=THEME['primary']
        )
        self.ent_username.pack(fill='x', ipady=8, pady=(4, 20))
        self.ent_username.focus_set()

        tk.Label(card, text="PASSWORD", bg=THEME['bg_card'], fg=THEME['text_muted'], font=("Helvetica", 9, "bold")).pack(anchor='w')
        self.ent_password = tk.Entry(
            card, show="*", bg='#090D16', fg='#ffffff', insertbackground='#ffffff',
            font=("Helvetica", 12), bd=0, highlightthickness=1, highlightbackground=THEME['border'], highlightcolor=THEME['primary']
        )
        self.ent_password.pack(fill='x', ipady=8, pady=(4, 25))

        self.btn_login = tk.Button(
            card, text="SIGN IN", bg=THEME['primary'], fg='#ffffff', activebackground=THEME['primary_hover'], activeforeground='#ffffff',
            font=("Helvetica", 11, "bold"), bd=0, relief="flat", cursor="hand2", command=self.handle_login
        )
        self.btn_login.pack(fill='x', ipady=10)

        self.ent_username.bind("<Return>", lambda e: self.ent_password.focus_set())
        self.ent_password.bind("<Return>", lambda e: self.handle_login())

        self.btn_login.bind("<Enter>", lambda e: self.btn_login.config(bg=THEME['primary_hover']))
        self.btn_login.bind("<Leave>", lambda e: self.btn_login.config(bg=THEME['primary']))

    def handle_login(self):
        username = self.ent_username.get().strip()
        password = self.ent_password.get().strip()

        if not username or not password:
            tk_messagebox.showwarning("Validation Error", "Please fill in all fields.")
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?;", (username,))
        user_row = cursor.fetchone()
        conn.close()

        if user_row and user_row['password'] == password:
            user_data = {
                'username': user_row['username'],
                'role': user_row['role']
            }
            self.ent_username.delete(0, 'end')
            self.ent_password.delete(0, 'end')
            self.on_login_success(user_data)
        else:
            tk_messagebox.showerror("Auth Error", "Invalid username or password.")


# --- NEW MODERN PYQT6 LOGIN WINDOW ---
QSS = """
QMainWindow {
    background-color: #FFFFFF;
}
QLabel#titleLabel {
    font-size: 24px;
    font-weight: bold;
    color: #1E293B;
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
}
QLabel#subtitleLabel {
    font-size: 13px;
    color: #64748B;
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
}
QLabel#versionLabel {
    font-size: 11px;
    color: #94A3B8;
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
}
QLineEdit {
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    color: #1E293B;
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
}
QLineEdit:focus {
    border: 2px solid #6366F1;
    background-color: #FFFFFF;
}
QPushButton#loginBtn {
    background-color: #6366F1;
    color: white;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
}
QPushButton#loginBtn:hover {
    background-color: #4F46E5;
}
QPushButton#exitBtn {
    background-color: #F1F5F9;
    color: #475569;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
}
QPushButton#exitBtn:hover {
    background-color: #E2E8F0;
}
"""

class LoginWindow(QMainWindow):
    """
    Modern PyQt6 login window for the Phone Shop POS system.
    """
    # Signal emitted on successful authentication
    login_success = pyqtSignal(dict)

    def __init__(self, parent=None, on_login_success=None):
        super().__init__(parent)
        self.on_login_success = on_login_success
        self.logged_in = False
        self.user_data = None

        # Ensure default admin account is populated if DB is blank
        create_default_admin_if_empty()

        # Window configuration
        self.setWindowTitle("Phone Shop POS - Login")
        self.setFixedSize(500, 350)
        self.setStyleSheet(QSS)

        # Main Central Widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # UI Layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(45, 30, 45, 20)
        main_layout.setSpacing(12)

        # 1. Shop Logo Circular Badge (Indigo color with "P" symbol)
        logo_container = QHBoxLayout()
        logo_container.addStretch()
        
        logo_label = QLabel("P")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            background-color: #6366F1;
            color: #FFFFFF;
            border-radius: 22px;
            font-weight: bold;
            font-size: 22px;
            min-width: 44px;
            max-width: 44px;
            min-height: 44px;
            max-height: 44px;
            font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
        """)
        logo_container.addWidget(logo_label)
        logo_container.addStretch()
        main_layout.addLayout(logo_container)

        # 2. Large Title
        title_label = QLabel("Phone Shop POS")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 3. Subtitle
        subtitle_label = QLabel("Offline Billing & Inventory System")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle_label)

        main_layout.addSpacing(10)

        # 4. Username Field
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setObjectName("usernameInput")
        main_layout.addWidget(self.username_input)

        # 5. Password Field (Hidden input)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setObjectName("passwordInput")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        main_layout.addWidget(self.password_input)

        main_layout.addSpacing(10)

        # 6. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.exit_btn = QPushButton("Exit")
        self.exit_btn.setObjectName("exitBtn")
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.exit_btn)

        self.login_btn = QPushButton("Login")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self.handle_login)
        self.login_btn.setDefault(True)
        btn_layout.addWidget(self.login_btn)

        main_layout.addLayout(btn_layout)

        main_layout.addStretch()

        # 7. Version Label
        version_label = QLabel("v1.0")
        version_label.setObjectName("versionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(version_label)

    def authenticate_user(self, username, password):
        """
        Validates username and password credentials against SQLite table.
        
        Args:
            username (str): Entered username.
            password (str): Entered password.
            
        Returns:
            tuple: (True, user_data) if authenticated, or (False, error_msg) if not.
        """
        try:
            db = DatabaseManager()
            cursor = db.get_cursor()
            cursor.execute("SELECT username, role, password FROM users WHERE username = ?;", (username,))
            row = cursor.fetchone()
            db.close()

            if not row:
                return False, "Invalid username or password."

            db_username, db_role, db_password = row
            if db_password == password:
                user_data = {
                    "username": db_username,
                    "role": db_role
                }
                return True, user_data
            else:
                return False, "Invalid username or password."
        except Exception as e:
            return False, f"Database authentication error: {str(e)}"

    def handle_login(self):
        """
        Form submission handler triggered by the Login button click or Enter key.
        """
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        # Feature 1: Validate empty fields
        if not username or not password:
            QMessageBox.warning(self, "Validation Error", "Please fill in all fields.")
            return False, "Empty fields"

        # Feature 3: Authenticate
        success, result = self.authenticate_user(username, password)
        if success:
            self.logged_in = True
            self.user_data = result

            # Emit PyQt Signal
            self.login_success.emit(self.user_data)

            # Invoke Callback
            if self.on_login_success:
                self.on_login_success(self.user_data)

            # Close Login Window
            self.close()
            return True, self.user_data
        else:
            # Feature 2 & 7: Failed login shows QMessageBox error
            QMessageBox.critical(self, "Auth Error", result)
            return False, result

if __name__ == "__main__":
    import sys
    from database.db import init_db
    
    # Initialize database
    init_db()

    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
