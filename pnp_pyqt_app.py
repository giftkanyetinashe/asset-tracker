# pnp_pyqt_app.py (Final Version with Edit Functionality)
import sys
import os
import sqlite3
import datetime
import random
import string
import hashlib
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDialog, QMessageBox, QTableWidgetItem, 
                             QWidget, QVBoxLayout, QDialogButtonBox, QLabel, QLineEdit, QFormLayout, 
                             QPushButton, QTabWidget, QComboBox, QTableWidget, QDateEdit, QHBoxLayout)
from PyQt6.QtGui import QPainter, QPixmap, QPen, QImage, QIcon
from PyQt6.QtCore import Qt, QPoint, QDate
from PyQt6 import uic

# --- Database Class (With Dispatch and Update Methods) ---
class Database:
    def __init__(self, db_file="inventory.db"):
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def create_tables(self):
        # Create users table
        self.cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, signature_path TEXT)")
        
        # Create products table with all required columns
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY, 
            tracking_id TEXT UNIQUE, 
            asset_name TEXT, 
            asset_code TEXT,
            serial_number TEXT, 
            branch_name TEXT, 
            date_received TEXT, 
            current_status TEXT, 
            date_dispatched TEXT, 
            received_by_user_id INTEGER, 
            received_by_signature_path TEXT, 
            dispatched_by_user_id INTEGER, 
            dispatched_by_signature_path TEXT
        )""")
        
        self.check_and_update_schema()
        self.conn.commit()

    def check_and_update_schema(self):
        self.cursor.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in self.cursor.fetchall()]
        
        required_columns = ["date_dispatched", "dispatched_by_user_id", "dispatched_by_signature_path"]
        
        for column in required_columns:
            if column not in columns:
                if column == "date_dispatched": self.cursor.execute(f"ALTER TABLE products ADD COLUMN {column} TEXT")
                elif column.endswith("_id"): self.cursor.execute(f"ALTER TABLE products ADD COLUMN {column} INTEGER")
                else: self.cursor.execute(f"ALTER TABLE products ADD COLUMN {column} TEXT")
        
        self.conn.commit()

    def delete_product(self, tracking_id):
        """Delete a product from the database by tracking ID."""
        self.cursor.execute("DELETE FROM products WHERE tracking_id = ?", (tracking_id,))
        self.conn.commit()
        return "Product deleted successfully.", True

    def create_user(self, username, password, signature_path):
        if not all([username, password, signature_path]): return "All fields including signature are required.", False
        if self.cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone(): return "Username already exists.", False
        self.cursor.execute("INSERT INTO users (username, password_hash, signature_path) VALUES (?, ?, ?)",
                            (username, self.hash_password(password), signature_path))
        self.conn.commit()
        return "User created successfully.", True

    def check_user(self, username, password):
        user = self.cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if user and user[1] == self.hash_password(password): return user[0], username
        return None, None
    
    def get_user_details(self, user_id):
        if not user_id: return ("Unknown", None)
        result = self.cursor.execute("SELECT username, signature_path FROM users WHERE id = ?", (user_id,)).fetchone()
        return result if result else ("Deleted/Invalid User", None)

    def update_user_profile(self, user_id, new_username, new_password_hash, new_signature_path):
        if new_username:
            if self.cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (new_username, user_id)).fetchone(): return "Username is already taken.", False
        updates, params = [], []
        if new_username: updates.append("username = ?"); params.append(new_username)
        if new_password_hash: updates.append("password_hash = ?"); params.append(new_password_hash)
        if new_signature_path: updates.append("signature_path = ?"); params.append(new_signature_path)
        if not updates: return "No changes provided.", False
        params.append(user_id)
        self.cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
        self.conn.commit()
        return "Profile updated.", True

    def get_user_signature_path(self, user_id):
        result = self.cursor.execute("SELECT signature_path FROM users WHERE id = ?", (user_id,)).fetchone()
        return result[0] if result else None
        
    def generate_tracking_id(self):
        while True:
            tracking_id = 'PNP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if self.cursor.execute("SELECT 1 FROM products WHERE tracking_id = ?", (tracking_id,)).fetchone() is None: return tracking_id

    def add_product(self, data, user_id, signature_path):
        tracking_id = self.generate_tracking_id()
        sql = "INSERT INTO products (tracking_id, asset_name, asset_code, serial_number, branch_name, date_received, current_status, received_by_user_id, received_by_signature_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        self.cursor.execute(sql, (tracking_id, data['asset_name'], data['asset_code'], data['serial_number'], data['branch_name'], data['date'], "Received at HQ", user_id, signature_path))
        self.conn.commit()
        return tracking_id

    # --- NEW METHOD to update a product's details ---
    def update_product(self, tracking_id, data):
        sql = """UPDATE products SET 
                    asset_name = ?, 
                    asset_code = ?, 
                    branch_name = ?, 
                    serial_number = ? 
                 WHERE tracking_id = ?"""
        try:
            self.cursor.execute(sql, (
                data['asset_name'],
                data['asset_code'],
                data['branch_name'],
                data['serial_number'],
                tracking_id
            ))
            self.conn.commit()
            return "Product updated successfully.", True
        except Exception as e:
            return f"Failed to update product: {e}", False

    def dispatch_product(self, product_id, dispatcher_id):
        dispatcher_signature_path = self.get_user_signature_path(dispatcher_id)
        if not dispatcher_signature_path: return "Dispatcher signature not found.", False
        date_dispatched = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_status = "Dispatched to Branch"
        sql = "UPDATE products SET current_status=?, date_dispatched=?, dispatched_by_user_id=?, dispatched_by_signature_path=? WHERE id = ?"
        self.cursor.execute(sql, (new_status, date_dispatched, dispatcher_id, dispatcher_signature_path, product_id))
        self.conn.commit()
        return "Asset dispatched successfully.", True

    def get_all_active_products(self):
        sql = """SELECT p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, p.date_received, u.username
                 FROM products p JOIN users u ON p.received_by_user_id = u.id 
                 WHERE p.dispatched_by_user_id IS NULL ORDER BY p.date_received DESC"""
        return self.cursor.execute(sql).fetchall()
    
    def get_all_dispatched_products(self):
        sql = """SELECT p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, 
                        p.date_received, p.date_dispatched, u1.username as received_by, u2.username as dispatched_by
                 FROM products p 
                 JOIN users u1 ON p.received_by_user_id = u1.id 
                 LEFT JOIN users u2 ON p.dispatched_by_user_id = u2.id 
                 WHERE p.dispatched_by_user_id IS NOT NULL 
                 ORDER BY p.date_dispatched DESC"""
        return self.cursor.execute(sql).fetchall()
    
    def search_products(self, term, category, dispatched=False):
        column_map = {"Tracking ID": "p.tracking_id", "Asset Name": "p.asset_name", "Asset Code": "p.asset_code", 
                      "Branch Name": "p.branch_name", "Date Received": "p.date_received", "Date Dispatched": "p.date_dispatched"}
        db_column = column_map.get(category)
        if not db_column: return []
        search_term = f"%{term}%" if category not in ["Date Received", "Date Dispatched"] else term
        if dispatched:
            sql = f"""SELECT p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, 
                             p.date_received, p.date_dispatched, u1.username as received_by, u2.username as dispatched_by
                      FROM products p JOIN users u1 ON p.received_by_user_id = u1.id LEFT JOIN users u2 ON p.dispatched_by_user_id = u2.id 
                      WHERE {db_column} LIKE ? AND p.dispatched_by_user_id IS NOT NULL ORDER BY p.date_dispatched DESC"""
        else:
            sql = f"""SELECT p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, p.date_received, u.username
                      FROM products p JOIN users u ON p.received_by_user_id = u.id 
                      WHERE {db_column} LIKE ? AND p.dispatched_by_user_id IS NULL ORDER BY p.date_received DESC"""
        return self.cursor.execute(sql, (search_term,)).fetchall()

    def get_product_details(self, tracking_id):
        return self.cursor.execute("SELECT * FROM products WHERE tracking_id = ?", (tracking_id,)).fetchone()

# --- Reusable Signature Pad Widget ---
class SignaturePad(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(400, 150)
        self.image = QPixmap(self.size()); self.image.fill(Qt.GlobalColor.white)
        self.drawing = False; self.last_point = QPoint()
    def paintEvent(self, event): painter = QPainter(self); painter.drawPixmap(self.rect(), self.image)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.drawing = True; self.last_point = event.pos()
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drawing:
            painter = QPainter(self.image); painter.setPen(QPen(Qt.GlobalColor.black, 2)); painter.drawLine(self.last_point, event.pos())
            self.last_point = event.pos(); self.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.drawing = False
    def clear_signature(self): self.image.fill(Qt.GlobalColor.white); self.update()
    def save_signature(self, path): self.image.toImage().save(path, "PNG")
    def is_signed(self):
        img = self.image.toImage().convertToFormat(QImage.Format.Format_RGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixel(x, y) != 0xFFFFFFFF: return True
        return False

# --- Dialog Windows ---
class LoginDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent); self.db = db; self.setWindowTitle("User Login")
        self.username_input = QLineEdit(); self.password_input = QLineEdit(); self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        self.signup_button = buttons.addButton("Sign Up", QDialogButtonBox.ButtonRole.ActionRole); self.signup_button.clicked.connect(self.handle_signup)
        layout = QFormLayout(); layout.addRow("Username:", self.username_input); layout.addRow("Password:", self.password_input); layout.addWidget(buttons)
        self.setLayout(layout); self.user = None
    def handle_signup(self): SignUpDialog(self.db, self).exec()
    def accept(self):
        user_id, username = self.db.check_user(self.username_input.text(), self.password_input.text())
        if user_id: self.user = (user_id, username); super().accept()
        else: QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

class SignUpDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent); self.db = db; self.setWindowTitle("Create Account")
        self.username_input = QLineEdit(); self.password_input = QLineEdit(); self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit(); self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.signature_pad = SignaturePad(self)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout = QFormLayout(); layout.addRow("Username:", self.username_input); layout.addRow("Password:", self.password_input)
        layout.addRow("Confirm Password:", self.confirm_password_input); layout.addRow("Draw Signature:", self.signature_pad); layout.addWidget(buttons)
        self.setLayout(layout)
    def accept(self):
        if self.password_input.text() != self.confirm_password_input.text(): QMessageBox.warning(self, "Error", "Passwords do not match."); return
        if not self.signature_pad.is_signed(): QMessageBox.warning(self, "Error", "A signature is required."); return
        username = self.username_input.text()
        signature_path = os.path.join("signatures", f"user_{username}.png")
        self.signature_pad.save_signature(signature_path)
        message, success = self.db.create_user(username, self.password_input.text(), signature_path)
        if success: QMessageBox.information(self, "Success", message); super().accept()
        else: QMessageBox.warning(self, "Error", message); os.remove(signature_path)

class ProfileEditorDialog(QDialog):
    def __init__(self, user_id, db, parent=None):
        super().__init__(parent); self.setWindowTitle("Edit Your Profile")
        self.user_id = user_id; self.db = db
        user_details = self.db.get_user_details(self.user_id); current_username, self.current_signature_path = user_details[0], user_details[1]
        self.username_input = QLineEdit(current_username); self.current_password_input = QLineEdit(); self.current_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input = QLineEdit(); self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit(); self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.signature_pad = SignaturePad(self); self.current_signature_label = QLabel()
        if self.current_signature_path and os.path.exists(self.current_signature_path):
            self.current_signature_label.setPixmap(QPixmap(self.current_signature_path).scaled(200, 75, Qt.AspectRatioMode.KeepAspectRatio))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout = QFormLayout(); layout.addRow("Username:", self.username_input); layout.addRow(QLabel("---"))
        layout.addRow("<b>Current Password (Required to save changes):</b>", self.current_password_input); layout.addRow(QLabel("---"))
        layout.addRow("New Password (leave blank to keep current):", self.new_password_input); layout.addRow("Confirm New Password:", self.confirm_password_input)
        layout.addRow(QLabel("---")); layout.addRow("Current Signature:", self.current_signature_label); layout.addRow("Draw New Signature (optional):", self.signature_pad)
        layout.addWidget(buttons); self.setLayout(layout)
    def accept(self):
        current_password = self.current_password_input.text()
        if not current_password: QMessageBox.warning(self, "Error", "You must enter your current password to save changes."); return
        original_username = self.db.get_user_details(self.user_id)[0]
        if not self.db.check_user(original_username, current_password)[0]: QMessageBox.warning(self, "Authentication Failed", "The 'Current Password' you entered is incorrect."); return
        new_username = self.username_input.text(); new_password = self.new_password_input.text(); new_password_hash = None
        if new_password:
            if new_password != self.confirm_password_input.text(): QMessageBox.warning(self, "Error", "New passwords do not match."); return
            new_password_hash = self.db.hash_password(new_password)
        new_signature_path = None
        if self.signature_pad.is_signed():
            new_signature_path = os.path.join("signatures", f"user_{new_username}.png"); self.signature_pad.save_signature(new_signature_path)
        message, success = self.db.update_user_profile(self.user_id, new_username, new_password_hash, new_signature_path)
        if success: QMessageBox.information(self, "Success", message); super().accept()
        else: QMessageBox.warning(self, "Update Failed", message)

# --- NEW DIALOG for editing products ---
class EditProductDialog(QDialog):
    def __init__(self, product_details, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Edit Product")
        
        self.tracking_id = product_details[1]
        self.asset_name_input = QLineEdit(product_details[2])
        self.asset_code_input = QLineEdit(product_details[3])
        self.serial_number_input = QLineEdit(product_details[4])
        self.branch_name_input = QLineEdit(product_details[5])
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout = QFormLayout()
        layout.addRow("Tracking ID:", QLabel(self.tracking_id))
        layout.addRow("Asset Name:", self.asset_name_input)
        layout.addRow("Asset Code:", self.asset_code_input)
        layout.addRow("Branch Name:", self.branch_name_input)
        layout.addRow("Serial Number:", self.serial_number_input)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
    def accept(self):
        updated_data = {
            "asset_name": self.asset_name_input.text().strip(),
            "asset_code": self.asset_code_input.text().strip(),
            "branch_name": self.branch_name_input.text().strip(),
            "serial_number": self.serial_number_input.text().strip()
        }
        
        if not all(updated_data.values()):
            QMessageBox.warning(self, "Input Error", "All fields are required.")
            return
        
        message, success = self.db.update_product(self.tracking_id, updated_data)
        if success:
            QMessageBox.information(self, "Success", message)
            super().accept()
        else:
            QMessageBox.warning(self, "Error", message)

class ProductDetailsDialog(QDialog):
    def __init__(self, tracking_id, db, parent=None):
        super().__init__(parent); self.parent = parent; self.setWindowTitle(f"Details for {tracking_id}"); self.db = db
        self.product_data = self.db.get_product_details(tracking_id)
        layout = QVBoxLayout()
        if not self.product_data: layout.addWidget(QLabel("Product not found.")); self.setLayout(layout); return
        self.product_id = self.product_data[0]
        form_layout = QFormLayout()
        details_map = {"Tracking ID": self.product_data[1], "Asset Name": self.product_data[2], "Asset Code": self.product_data[3], "Serial Number": self.product_data[4],
                       "Branch Name": self.product_data[5], "Date Received": self.product_data[6], "Current Status": self.product_data[7]}
        for label, value in details_map.items(): form_layout.addRow(QLabel(f"<b>{label}:</b>"), QLabel(str(value or "N/A")))
        reception_user_details = self.db.get_user_details(self.product_data[9]); reception_user = reception_user_details[0] if reception_user_details else "Unknown"
        form_layout.addRow(QLabel(f"<b>Received By:</b>"), QLabel(reception_user)); layout.addLayout(form_layout)
        signature_path = self.product_data[10]
        if signature_path and os.path.exists(signature_path):
            sig_image_label = QLabel(); pixmap = QPixmap(signature_path)
            sig_image_label.setPixmap(pixmap.scaled(400, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(QLabel("<b>Reception Signature:</b>")); layout.addWidget(sig_image_label)
        layout.addWidget(QLabel("<hr>"))
        dispatched_user_id = self.product_data[11]
        if dispatched_user_id:
            dispatch_form_layout = QFormLayout()
            dispatch_user_details = self.db.get_user_details(dispatched_user_id); dispatch_user = dispatch_user_details[0] if dispatch_user_details else "Unknown"
            dispatch_form_layout.addRow(QLabel("<b>Date Dispatched:</b>"), QLabel(self.product_data[8] or "N/A"))
            dispatch_form_layout.addRow(QLabel("<b>Dispatched By:</b>"), QLabel(dispatch_user)); layout.addLayout(dispatch_form_layout)
            dispatch_sig_path = self.product_data[12]
            if dispatch_sig_path and os.path.exists(dispatch_sig_path):
                dispatch_sig_image = QLabel(); pixmap = QPixmap(dispatch_sig_path)
                dispatch_sig_image.setPixmap(pixmap.scaled(400, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                layout.addWidget(QLabel("<b>Dispatch Signature:</b>")); layout.addWidget(dispatch_sig_image)
        else:
            button_layout = QHBoxLayout()
            self.edit_button = QPushButton("Edit Details")
            self.edit_button.clicked.connect(self.handle_edit)
            button_layout.addWidget(self.edit_button)
            self.dispatch_button = QPushButton("Dispatch This Asset")
            self.dispatch_button.clicked.connect(self.handle_dispatch)
            button_layout.addWidget(self.dispatch_button)
            layout.addLayout(button_layout)
        self.setLayout(layout)

    def handle_edit(self):
        edit_dialog = EditProductDialog(self.product_data, self.db, self)
        if edit_dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent.refresh_active_products()
            self.accept()

    def handle_dispatch(self):
        reply = QMessageBox.question(self, 'Confirm Dispatch', "Are you sure you want to dispatch this asset?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            current_user_id = self.parent.user[0]
            message, success = self.db.dispatch_product(self.product_id, current_user_id)
            if success:
                QMessageBox.information(self, "Success", message)
                self.parent.refresh_active_products(); self.parent.refresh_dispatched_products(); self.accept()
            else: QMessageBox.critical(self, "Error", message)

# --- Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self, user, db):
        super().__init__(); self.user = user; self.db = db; self.logout_triggered = False
        uic.loadUi("main_window.ui", self); self.statusbar.showMessage(f"Logged in as: {self.user[1]}")
        self.tab_widget = self.findChild(QTabWidget, "tabWidget")
        self.receive_tab_widget = QWidget(); uic.loadUi("receive_tab.ui", self.receive_tab_widget); self.tab_widget.addTab(self.receive_tab_widget, "Receive Asset")
        self.active_tab_widget = QWidget(); uic.loadUi("active_tab.ui", self.active_tab_widget); self.tab_widget.addTab(self.active_tab_widget, "Active Assets")
        self.dispatched_tab_widget = QWidget(); uic.loadUi("dispatched_tab.ui", self.dispatched_tab_widget); self.tab_widget.addTab(self.dispatched_tab_widget, "Dispatched Assets")
        
        self.active_search_categories = ["Tracking ID", "Asset Name", "Asset Code", "Branch Name", "Date Received"]
        self.active_searchCategoryComboBox = self.active_tab_widget.findChild(QComboBox, "searchCategoryComboBox"); self.active_searchCategoryComboBox.addItems(self.active_search_categories)
        self.active_searchInput = self.active_tab_widget.findChild(QLineEdit, "searchInput"); self.active_searchDateEdit = self.active_tab_widget.findChild(QDateEdit, "searchDateEdit"); self.active_searchDateEdit.setVisible(False)
        self.active_searchButton = self.active_tab_widget.findChild(QPushButton, "searchButton"); self.active_refreshButton = self.active_tab_widget.findChild(QPushButton, "refreshButton")
        self.active_productTable = self.active_tab_widget.findChild(QTableWidget, "productTable")
        
        self.dispatched_search_categories = ["Tracking ID", "Asset Name", "Asset Code", "Branch Name", "Date Received", "Date Dispatched"]
        self.dispatched_searchCategoryComboBox = self.dispatched_tab_widget.findChild(QComboBox, "searchCategoryComboBox"); self.dispatched_searchCategoryComboBox.addItems(self.dispatched_search_categories)
        self.dispatched_searchInput = self.dispatched_tab_widget.findChild(QLineEdit, "searchInput"); self.dispatched_searchDateEdit = self.dispatched_tab_widget.findChild(QDateEdit, "searchDateEdit"); self.dispatched_searchDateEdit.setVisible(False)
        self.dispatched_searchButton = self.dispatched_tab_widget.findChild(QPushButton, "searchButton"); self.dispatched_refreshButton = self.dispatched_tab_widget.findChild(QPushButton, "refreshButton")
        self.dispatched_productTable = self.dispatched_tab_widget.findChild(QTableWidget, "productTable")
        
        self.dateEdit = self.receive_tab_widget.findChild(QDateEdit, "dateEdit"); self.branchNameInput = self.receive_tab_widget.findChild(QLineEdit, "branchNameInput")
        self.assetNameInput = self.receive_tab_widget.findChild(QLineEdit, "assetNameInput"); self.assetCodeInput = self.receive_tab_widget.findChild(QLineEdit, "assetCodeInput")
        self.serialNumberInput = self.receive_tab_widget.findChild(QLineEdit, "serialNumberInput"); self.saveButton = self.receive_tab_widget.findChild(QPushButton, "saveButton")
        
        self.dateEdit.setDate(QDate.currentDate())
        if os.path.exists("logic_league_logo.ico"): self.setWindowIcon(QIcon("logic_league_logo.ico"))
        self.setup_connections()
        self.refresh_active_products(); self.refresh_dispatched_products()
        
    def setup_connections(self):
        self.actionEdit_Profile.triggered.connect(self.open_profile_editor); self.actionLogout.triggered.connect(self.logout); self.actionExit.triggered.connect(self.close)
        self.saveButton.clicked.connect(self.save_asset)
        self.active_refreshButton.clicked.connect(self.refresh_active_products); self.active_searchButton.clicked.connect(self.execute_active_search)
        self.active_searchCategoryComboBox.currentTextChanged.connect(lambda: self.on_search_category_changed(self.active_searchCategoryComboBox, self.active_searchDateEdit, self.active_searchInput))
        self.active_productTable.doubleClicked.connect(lambda: self.on_table_double_click(self.active_productTable))
        self.dispatched_refreshButton.clicked.connect(self.refresh_dispatched_products); self.dispatched_searchButton.clicked.connect(self.execute_dispatched_search)
        self.dispatched_searchCategoryComboBox.currentTextChanged.connect(lambda: self.on_search_category_changed(self.dispatched_searchCategoryComboBox, self.dispatched_searchDateEdit, self.dispatched_searchInput))
        self.active_tab_widget.findChild(QPushButton, "deleteButton").clicked.connect(self.delete_active_product)
        self.dispatched_tab_widget.findChild(QPushButton, "deleteButton").clicked.connect(self.delete_dispatched_product)
        self.active_tab_widget.findChild(QPushButton, "editButton").clicked.connect(self.edit_active_product)
        self.dispatched_tab_widget.findChild(QPushButton, "editButton").clicked.connect(self.edit_dispatched_product)
        self.dispatched_productTable.doubleClicked.connect(lambda: self.on_table_double_click(self.dispatched_productTable))
        
    def open_profile_editor(self):
        ProfileEditorDialog(self.user[0], self.db, self).exec()
        new_details = self.db.get_user_details(self.user[0]); self.user = (self.user[0], new_details[0])
        self.statusbar.showMessage(f"Logged in as: {self.user[1]}")
    
    def logout(self): self.logout_triggered = True; self.close()
    
    def on_search_category_changed(self, combo_box, date_edit, search_input):
        category = combo_box.currentText()
        date_edit.setVisible(category in ["Date Received", "Date Dispatched"]); search_input.setVisible(category not in ["Date Received", "Date Dispatched"])
    
    def on_table_double_click(self, table):
        if (index := table.currentIndex()).isValid(): ProductDetailsDialog(table.item(index.row(), 0).text(), self.db, self).exec()
    
    def refresh_active_products(self): self.active_searchInput.clear(); self.display_products(self.db.get_all_active_products(), self.active_productTable, False)
    def refresh_dispatched_products(self): self.dispatched_searchInput.clear(); self.display_products(self.db.get_all_dispatched_products(), self.dispatched_productTable, True)
    
    def delete_active_product(self):
        selected_row = self.active_productTable.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Error", "No product selected.")
            return
        tracking_id = self.active_productTable.item(selected_row, 0).text()
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Are you sure you want to delete the product with Tracking ID: {tracking_id}?", 
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            message, success = self.db.delete_product(tracking_id)
            if success:
                QMessageBox.information(self, "Success", message)
                self.refresh_active_products()
            else:
                QMessageBox.critical(self, "Error", message)

    def delete_dispatched_product(self):
        selected_row = self.dispatched_productTable.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Error", "No product selected.")
            return
        tracking_id = self.dispatched_productTable.item(selected_row, 0).text()
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Are you sure you want to delete the product with Tracking ID: {tracking_id}?", 
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            message, success = self.db.delete_product(tracking_id)
            if success:
                QMessageBox.information(self, "Success", message)
                self.refresh_dispatched_products()
            else:
                QMessageBox.critical(self, "Error", message)

    def edit_active_product(self):
        selected_row = self.active_productTable.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Error", "No product selected.")
            return
        tracking_id = self.active_productTable.item(selected_row, 0).text()
        product_details = self.db.get_product_details(tracking_id)
        if product_details:
            edit_dialog = EditProductDialog(product_details, self.db, self)
            if edit_dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh_active_products()
        else:
            QMessageBox.warning(self, "Error", "Could not find product details.")

    def edit_dispatched_product(self):
        selected_row = self.dispatched_productTable.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Error", "No product selected.")
            return
        tracking_id = self.dispatched_productTable.item(selected_row, 0).text()
        product_details = self.db.get_product_details(tracking_id)
        if product_details:
            edit_dialog = EditProductDialog(product_details, self.db, self)
            if edit_dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh_dispatched_products()
        else:
            QMessageBox.warning(self, "Error", "Could not find product details.")
    
    def display_products(self, products, table, dispatched=False):
        table.setRowCount(0)
        for row_num, product in enumerate(products):
            table.insertRow(row_num)
            for col_num, data in enumerate(product): table.setItem(row_num, col_num, QTableWidgetItem(str(data)))
        table.resizeColumnsToContents()
    
    def execute_active_search(self):
        category = self.active_searchCategoryComboBox.currentText()
        term = self.active_searchDateEdit.date().toString("yyyy-MM-dd") if category == "Date Received" else self.active_searchInput.text().strip()
        if not term: QMessageBox.warning(self, "Search Error", "Please enter a search term."); return
        results = self.db.search_products(term, category, False)
        if not results: QMessageBox.information(self, "No Results", "No products found.")
        self.display_products(results, self.active_productTable, False)
    
    def execute_dispatched_search(self):
        category = self.dispatched_searchCategoryComboBox.currentText()
        term = self.dispatched_searchDateEdit.date().toString("yyyy-MM-dd") if category in ["Date Received", "Date Dispatched"] else self.dispatched_searchInput.text().strip()
        if not term: QMessageBox.warning(self, "Search Error", "Please enter a search term."); return
        results = self.db.search_products(term, category, True)
        if not results: QMessageBox.information(self, "No Results", "No products found.")
        self.display_products(results, self.dispatched_productTable, True)
    
    def save_asset(self):
        data = {"date": self.dateEdit.date().toString("yyyy-MM-dd"), "branch_name": self.branchNameInput.text().strip(), 
                "asset_name": self.assetNameInput.text().strip(), "asset_code": self.assetCodeInput.text().strip(), "serial_number": self.serialNumberInput.text().strip()}
        if not all([data["branch_name"], data["asset_name"]]): QMessageBox.warning(self, "Input Error", "Branch Name and Asset Name are required."); return
        user_signature_path = self.db.get_user_signature_path(self.user[0])
        if not user_signature_path: QMessageBox.critical(self, "Error", "Could not find signature for the current user."); return
        new_tracking_id = self.db.add_product(data, self.user[0], user_signature_path)
        QMessageBox.information(self, "Success", f"Asset successfully saved.\nNew Tracking ID: {new_tracking_id}")
        self.clear_receive_form(); self.refresh_active_products()
    
    def clear_receive_form(self):
        self.branchNameInput.clear(); self.assetNameInput.clear(); self.assetCodeInput.clear(); self.serialNumberInput.clear()

if __name__ == '__main__':
    if not os.path.exists("signatures"): os.makedirs("signatures")
    db = Database(); app = QApplication(sys.argv)
    try:
        with open("style.qss", "r") as f: app.setStyleSheet(f.read())
    except FileNotFoundError: print("Warning: style.qss not found. Using default application style.")
    while True:
        login_dialog = LoginDialog(db)
        if login_dialog.exec() == QDialog.DialogCode.Accepted:
            main_win = MainWindow(login_dialog.user, db)
            main_win.show(); app.exec()
            if main_win.logout_triggered: continue
            else: break
        else: break
    sys.exit(0)