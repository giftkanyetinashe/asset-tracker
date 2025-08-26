# pnp_pyqt_app.py (Final Networked Version with Public Repo Updater)
import sys
import os
import mysql.connector
import configparser
import requests
import webbrowser
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


# Helper function to find asset files for PyInstaller
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- APPLICATION VERSION ---
# Update this when you create a new release on GitHub
APP_VERSION = "1.2.0" 

# --- GitHub Update Checker (for Public Repo) ---
def check_for_updates():
    # This URL points directly to your public repository's API endpoint
    repo_url = "https://api.github.com/repos/giftkanyetinashe/asset-tracker/releases/latest"
    
    try:
        response = requests.get(repo_url, timeout=5)
        response.raise_for_status() # Will raise an error for 4xx/5xx responses
        
        latest_release = response.json()
        latest_version = latest_release.get("tag_name", "0.0.0").lstrip('v')
        download_url = latest_release.get("html_url")

        if latest_version and download_url and latest_version > APP_VERSION:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(f"A new version ({latest_version}) is available!")
            msg.setInformativeText("Would you like to go to the download page?")
            msg.setWindowTitle("Update Available")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                webbrowser.open(download_url)

    except Exception as e:
        # This will catch network errors or if no releases are found
        print(f"Could not check for updates: {e}")


# --- Database Class (Connects to MySQL Server) ---
# [ This class remains unchanged. It is perfect. ]
class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            db_config = config['database']
            
            self.conn = mysql.connector.connect(**db_config)
            self.cursor = self.conn.cursor(buffered=True) 
            self.create_tables()
        except Exception as e:
            QMessageBox.critical(None, "Database Connection Error", 
                                 f"Could not connect to the database server.\n"
                                 f"Check your network and config.ini settings.\n\nError: {e}")
            sys.exit(1)

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS `users` (
            `id` INT AUTO_INCREMENT PRIMARY KEY, `username` VARCHAR(255) UNIQUE, 
            `password_hash` VARCHAR(255), `signature_path` VARCHAR(255)
        ) ENGINE=InnoDB;""")
        
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS `products` (
            `id` INT AUTO_INCREMENT PRIMARY KEY, `tracking_id` VARCHAR(255) UNIQUE, 
            `asset_name` VARCHAR(255), `asset_code` VARCHAR(255), `serial_number` VARCHAR(255), 
            `branch_name` VARCHAR(255), `date_received` VARCHAR(255), `current_status` VARCHAR(255), 
            `date_dispatched` VARCHAR(255), `received_by_user_id` INT, `received_by_signature_path` VARCHAR(255), 
            `dispatched_by_user_id` INT, `dispatched_by_signature_path` VARCHAR(255)
        ) ENGINE=InnoDB;""")
        self.conn.commit()

    def delete_product(self, tracking_id):
        self.cursor.execute("DELETE FROM products WHERE tracking_id = %s", (tracking_id,))
        self.conn.commit(); return "Product deleted successfully.", True

    def create_user(self, username, password, signature_path):
        if not all([username, password, signature_path]): return "All fields are required.", False
        self.cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if self.cursor.fetchone(): return "Username already exists.", False
        self.cursor.execute("INSERT INTO users (username, password_hash, signature_path) VALUES (%s, %s, %s)",
                            (username, self.hash_password(password), signature_path))
        self.conn.commit(); return "User created successfully.", True

    def check_user(self, username, password):
        self.cursor.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
        user = self.cursor.fetchone()
        if user and user[1] == self.hash_password(password): return user[0], username
        return None, None
    
    def get_user_details(self, user_id):
        if not user_id: return ("Unknown", None)
        self.cursor.execute("SELECT username, signature_path FROM users WHERE id = %s", (user_id,))
        return self.cursor.fetchone() or ("Deleted/Invalid User", None)

    def update_user_profile(self, user_id, new_username, new_password_hash, new_signature_path):
        if new_username:
            self.cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
            if self.cursor.fetchone(): return "Username is already taken.", False
        updates, params = [], []
        if new_username: updates.append("username = %s"); params.append(new_username)
        if new_password_hash: updates.append("password_hash = %s"); params.append(new_password_hash)
        if new_signature_path: updates.append("signature_path = %s"); params.append(new_signature_path)
        if not updates: return "No changes provided.", False
        params.append(user_id)
        self.cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", tuple(params))
        self.conn.commit(); return "Profile updated.", True

    def get_user_signature_path(self, user_id):
        self.cursor.execute("SELECT signature_path FROM users WHERE id = %s", (user_id,))
        result = self.cursor.fetchone(); return result[0] if result else None
        
    def generate_tracking_id(self):
        while True:
            tracking_id = 'PNP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.cursor.execute("SELECT 1 FROM products WHERE tracking_id = %s", (tracking_id,))
            if self.cursor.fetchone() is None: return tracking_id

    def add_product(self, data, user_id, signature_path):
        tracking_id = self.generate_tracking_id()
        sql = "INSERT INTO products (tracking_id, asset_name, asset_code, serial_number, branch_name, date_received, current_status, received_by_user_id, received_by_signature_path) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        self.cursor.execute(sql, (tracking_id, data['asset_name'], data['asset_code'], data['serial_number'], data['branch_name'], data['date'], "Received at HQ", user_id, signature_path))
        self.conn.commit(); return tracking_id

    def update_product(self, tracking_id, data):
        sql = "UPDATE products SET asset_name = %s, asset_code = %s, branch_name = %s, serial_number = %s WHERE tracking_id = %s"
        self.cursor.execute(sql, (data['asset_name'], data['asset_code'], data['branch_name'], data['serial_number'], tracking_id))
        self.conn.commit(); return "Product updated successfully.", True

    def dispatch_product(self, product_id, dispatcher_id):
        dispatcher_signature_path = self.get_user_signature_path(dispatcher_id)
        if not dispatcher_signature_path: return "Dispatcher signature not found.", False
        date_dispatched = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = "UPDATE products SET current_status=%s, date_dispatched=%s, dispatched_by_user_id=%s, dispatched_by_signature_path=%s WHERE id = %s"
        self.cursor.execute(sql, ("Dispatched to Branch", date_dispatched, dispatcher_id, dispatcher_signature_path, product_id))
        self.conn.commit(); return "Asset dispatched successfully.", True

    def get_all_active_products(self):
        sql = """SELECT p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, p.date_received, u.username
                 FROM products p JOIN users u ON p.received_by_user_id = u.id WHERE p.dispatched_by_user_id IS NULL ORDER BY p.date_received DESC"""
        self.cursor.execute(sql); return self.cursor.fetchall()
    
    def get_all_dispatched_products(self):
        sql = """SELECT p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, p.date_received, p.date_dispatched, u1.username as received_by, u2.username as dispatched_by
                 FROM products p JOIN users u1 ON p.received_by_user_id = u1.id LEFT JOIN users u2 ON p.dispatched_by_user_id = u2.id 
                 WHERE p.dispatched_by_user_id IS NOT NULL ORDER BY p.date_dispatched DESC"""
        self.cursor.execute(sql); return self.cursor.fetchall()
    
    def search_products(self, term, category, dispatched=False):
        column_map = {"Tracking ID": "p.tracking_id", "Asset Name": "p.asset_name", "Asset Code": "p.asset_code", "Branch Name": "p.branch_name", "Date Received": "p.date_received", "Date Dispatched": "p.date_dispatched"}
        db_column = column_map.get(category)
        if not db_column: return []
        search_term = f"%{term}%" if "Date" not in category else term
        base_sql = "FROM products p JOIN users u1 ON p.received_by_user_id = u1.id LEFT JOIN users u2 ON p.dispatched_by_user_id = u2.id"
        if dispatched:
            cols = "p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, p.date_received, p.date_dispatched, u1.username, u2.username"
            sql = f"SELECT {cols} {base_sql} WHERE {db_column} LIKE %s AND p.dispatched_by_user_id IS NOT NULL ORDER BY p.date_dispatched DESC"
        else:
            cols = "p.tracking_id, p.asset_name, p.asset_code, p.branch_name, p.current_status, p.date_received, u1.username"
            sql = f"SELECT {cols} {base_sql} WHERE {db_column} LIKE %s AND p.dispatched_by_user_id IS NULL ORDER BY p.date_received DESC"
        self.cursor.execute(sql, (search_term,)); return self.cursor.fetchall()

    def get_product_details(self, tracking_id):
        self.cursor.execute("SELECT * FROM products WHERE tracking_id = %s", (tracking_id,)); return self.cursor.fetchone()


# --- The rest of your UI code is unchanged and goes here ---
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

class EditProductDialog(QDialog):
    def __init__(self, product_details, db, parent=None):
        super().__init__(parent); self.db = db; self.setWindowTitle("Edit Product")
        self.tracking_id = product_details[1]
        self.asset_name_input = QLineEdit(product_details[2])
        self.asset_code_input = QLineEdit(product_details[3])
        self.serial_number_input = QLineEdit(product_details[4])
        self.branch_name_input = QLineEdit(product_details[5])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout = QFormLayout(); layout.addRow("Tracking ID:", QLabel(self.tracking_id)); layout.addRow("Asset Name:", self.asset_name_input)
        layout.addRow("Asset Code:", self.asset_code_input); layout.addRow("Branch Name:", self.branch_name_input)
        layout.addRow("Serial Number:", self.serial_number_input); layout.addWidget(buttons)
        self.setLayout(layout)
    def accept(self):
        updated_data = {"asset_name": self.asset_name_input.text().strip(), "asset_code": self.asset_code_input.text().strip(),
                        "branch_name": self.branch_name_input.text().strip(), "serial_number": self.serial_number_input.text().strip()}
        if not all(updated_data.values()): QMessageBox.warning(self, "Input Error", "All fields are required."); return
        message, success = self.db.update_product(self.tracking_id, updated_data)
        if success: QMessageBox.information(self, "Success", message); super().accept()
        else: QMessageBox.warning(self, "Error", message)

class ProductDetailsDialog(QDialog):
    def __init__(self, tracking_id, db, parent=None):
        super().__init__(parent); self.parent = parent; self.setWindowTitle(f"Details for {tracking_id}"); self.db = db
        self.product_data = self.db.get_product_details(tracking_id); layout = QVBoxLayout()
        if not self.product_data: layout.addWidget(QLabel("Product not found.")); self.setLayout(layout); return
        self.product_id = self.product_data[0]; form_layout = QFormLayout()
        details_map = {"Tracking ID": self.product_data[1], "Asset Name": self.product_data[2], "Asset Code": self.product_data[3], "Serial Number": self.product_data[4], "Branch Name": self.product_data[5], "Date Received": self.product_data[6], "Current Status": self.product_data[7]}
        for label, value in details_map.items(): form_layout.addRow(QLabel(f"<b>{label}:</b>"), QLabel(str(value or "N/A")))
        reception_user_details = self.db.get_user_details(self.product_data[9]); reception_user = reception_user_details[0] if reception_user_details else "Unknown"
        form_layout.addRow(QLabel(f"<b>Received By:</b>"), QLabel(reception_user)); layout.addLayout(form_layout)
        if (signature_path := self.product_data[10]) and os.path.exists(signature_path):
            sig_image_label = QLabel(); pixmap = QPixmap(signature_path)
            sig_image_label.setPixmap(pixmap.scaled(400, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(QLabel("<b>Reception Signature:</b>")); layout.addWidget(sig_image_label)
        layout.addWidget(QLabel("<hr>"))
        if dispatched_user_id := self.product_data[11]:
            dispatch_form_layout = QFormLayout(); dispatch_user_details = self.db.get_user_details(dispatched_user_id)
            dispatch_user = dispatch_user_details[0] if dispatch_user_details else "Unknown"
            dispatch_form_layout.addRow(QLabel("<b>Date Dispatched:</b>"), QLabel(self.product_data[8] or "N/A"))
            dispatch_form_layout.addRow(QLabel("<b>Dispatched By:</b>"), QLabel(dispatch_user)); layout.addLayout(dispatch_form_layout)
            if (dispatch_sig_path := self.product_data[12]) and os.path.exists(dispatch_sig_path):
                dispatch_sig_image = QLabel(); pixmap = QPixmap(dispatch_sig_path)
                dispatch_sig_image.setPixmap(pixmap.scaled(400, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                layout.addWidget(QLabel("<b>Dispatch Signature:</b>")); layout.addWidget(dispatch_sig_image)
        else:
            button_layout = QHBoxLayout(); self.edit_button = QPushButton("Edit Details"); self.edit_button.clicked.connect(self.handle_edit)
            button_layout.addWidget(self.edit_button); self.dispatch_button = QPushButton("Dispatch This Asset")
            self.dispatch_button.clicked.connect(self.handle_dispatch); button_layout.addWidget(self.dispatch_button); layout.addLayout(button_layout)
        self.setLayout(layout)
    def handle_edit(self):
        if (edit_dialog := EditProductDialog(self.product_data, self.db, self)).exec() == QDialog.DialogCode.Accepted:
            self.parent.refresh_active_products(); self.accept()
    def handle_dispatch(self):
        if QMessageBox.question(self, 'Confirm Dispatch', "Are you sure?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            message, success = self.db.dispatch_product(self.product_id, self.parent.user[0])
            if success: QMessageBox.information(self, "Success", message); self.parent.refresh_active_products(); self.parent.refresh_dispatched_products(); self.accept()
            else: QMessageBox.critical(self, "Error", message)

class MainWindow(QMainWindow):
    def __init__(self, user, db):
        super().__init__(); self.user = user; self.db = db; self.logout_triggered = False
        uic.loadUi(resource_path("main_window.ui"), self); self.statusbar.showMessage(f"Logged in as: {self.user[1]}")
        self.tab_widget = self.findChild(QTabWidget, "tabWidget")
        self.receive_tab_widget = QWidget(); uic.loadUi(resource_path("receive_tab.ui"), self.receive_tab_widget); self.tab_widget.addTab(self.receive_tab_widget, "Receive Asset")
        self.active_tab_widget = QWidget(); uic.loadUi(resource_path("active_tab.ui"), self.active_tab_widget); self.tab_widget.addTab(self.active_tab_widget, "Active Assets")
        self.dispatched_tab_widget = QWidget(); uic.loadUi(resource_path("dispatched_tab.ui"), self.dispatched_tab_widget); self.tab_widget.addTab(self.dispatched_tab_widget, "Dispatched Assets")
        
        self.active_searchCategoryComboBox = self.active_tab_widget.findChild(QComboBox, "searchCategoryComboBox"); self.active_searchCategoryComboBox.addItems(["Tracking ID", "Asset Name", "Asset Code", "Branch Name", "Date Received"])
        self.active_searchInput = self.active_tab_widget.findChild(QLineEdit, "searchInput"); self.active_searchDateEdit = self.active_tab_widget.findChild(QDateEdit, "searchDateEdit"); self.active_searchDateEdit.setVisible(False)
        self.active_searchButton = self.active_tab_widget.findChild(QPushButton, "searchButton"); self.active_refreshButton = self.active_tab_widget.findChild(QPushButton, "refreshButton")
        self.active_productTable = self.active_tab_widget.findChild(QTableWidget, "productTable")
        
        self.dispatched_searchCategoryComboBox = self.dispatched_tab_widget.findChild(QComboBox, "searchCategoryComboBox"); self.dispatched_searchCategoryComboBox.addItems(["Tracking ID", "Asset Name", "Asset Code", "Branch Name", "Date Received", "Date Dispatched"])
        self.dispatched_searchInput = self.dispatched_tab_widget.findChild(QLineEdit, "searchInput"); self.dispatched_searchDateEdit = self.dispatched_tab_widget.findChild(QDateEdit, "searchDateEdit"); self.dispatched_searchDateEdit.setVisible(False)
        self.dispatched_searchButton = self.dispatched_tab_widget.findChild(QPushButton, "searchButton"); self.dispatched_refreshButton = self.dispatched_tab_widget.findChild(QPushButton, "refreshButton")
        self.dispatched_productTable = self.dispatched_tab_widget.findChild(QTableWidget, "productTable")
        
        self.dateEdit = self.receive_tab_widget.findChild(QDateEdit, "dateEdit"); self.branchNameInput = self.receive_tab_widget.findChild(QLineEdit, "branchNameInput")
        self.assetNameInput = self.receive_tab_widget.findChild(QLineEdit, "assetNameInput"); self.assetCodeInput = self.receive_tab_widget.findChild(QLineEdit, "assetCodeInput")
        self.serialNumberInput = self.receive_tab_widget.findChild(QLineEdit, "serialNumberInput"); self.saveButton = self.receive_tab_widget.findChild(QPushButton, "saveButton")
        
        self.dateEdit.setDate(QDate.currentDate()); self.setup_connections(); self.refresh_active_products(); self.refresh_dispatched_products()
        icon_path = resource_path("logic_league_logo.ico")
        if os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        
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
        if ProfileEditorDialog(self.user[0], self.db, self).exec():
            new_details = self.db.get_user_details(self.user[0]); self.user = (self.user[0], new_details[0])
            self.statusbar.showMessage(f"Logged in as: {self.user[1]}")
    
    def logout(self): self.logout_triggered = True; self.close()
    
    def on_search_category_changed(self, combo_box, date_edit, search_input):
        category = combo_box.currentText(); date_edit.setVisible("Date" in category); search_input.setVisible("Date" not in category)
    
    def on_table_double_click(self, table):
        if (index := table.currentIndex()).isValid(): ProductDetailsDialog(table.item(index.row(), 0).text(), self.db, self).exec()
    
    def refresh_active_products(self): self.active_searchInput.clear(); self.display_products(self.db.get_all_active_products(), self.active_productTable, False)
    def refresh_dispatched_products(self): self.dispatched_searchInput.clear(); self.display_products(self.db.get_all_dispatched_products(), self.dispatched_productTable, True)
    
    def delete_product(self, table, refresh_method):
        if (selected_row := table.currentRow()) < 0: QMessageBox.warning(self, "Error", "No product selected."); return
        tracking_id = table.item(selected_row, 0).text()
        if QMessageBox.question(self, 'Confirm Deletion', f"Delete {tracking_id}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            message, success = self.db.delete_product(tracking_id)
            QMessageBox.information(self, "Success" if success else "Error", message); refresh_method()
    def delete_active_product(self): self.delete_product(self.active_productTable, self.refresh_active_products)
    def delete_dispatched_product(self): self.delete_product(self.dispatched_productTable, self.refresh_dispatched_products)

    def edit_product(self, table, refresh_method):
        if (selected_row := table.currentRow()) < 0: QMessageBox.warning(self, "Error", "No product selected."); return
        tracking_id = table.item(selected_row, 0).text()
        if (product_details := self.db.get_product_details(tracking_id)):
            if EditProductDialog(product_details, self.db, self).exec(): refresh_method()
        else: QMessageBox.warning(self, "Error", "Could not find product details.")
    def edit_active_product(self): self.edit_product(self.active_productTable, self.refresh_active_products)
    def edit_dispatched_product(self): self.edit_product(self.dispatched_productTable, self.refresh_dispatched_products)
    
    def display_products(self, products, table, dispatched=False):
        table.setRowCount(0)
        for row_num, product in enumerate(products):
            table.insertRow(row_num)
            for col_num, data in enumerate(product): table.setItem(row_num, col_num, QTableWidgetItem(str(data)))
        table.resizeColumnsToContents()
    
    def execute_active_search(self):
        category = self.active_searchCategoryComboBox.currentText(); term = self.active_searchDateEdit.date().toString("yyyy-MM-dd") if "Date" in category else self.active_searchInput.text().strip()
        if not term: QMessageBox.warning(self, "Search Error", "Please enter a search term."); return
        results = self.db.search_products(term, category, False)
        if not results: QMessageBox.information(self, "No Results", "No products found.")
        self.display_products(results, self.active_productTable, False)
    
    def execute_dispatched_search(self):
        category = self.dispatched_searchCategoryComboBox.currentText(); term = self.dispatched_searchDateEdit.date().toString("yyyy-MM-dd") if "Date" in category else self.dispatched_searchInput.text().strip()
        if not term: QMessageBox.warning(self, "Search Error", "Please enter a search term."); return
        results = self.db.search_products(term, category, True)
        if not results: QMessageBox.information(self, "No Results", "No products found.")
        self.display_products(results, self.dispatched_productTable, True)
    
    def save_asset(self):
        data = {"date": self.dateEdit.date().toString("yyyy-MM-dd"), "branch_name": self.branchNameInput.text().strip(), "asset_name": self.assetNameInput.text().strip(), "asset_code": self.assetCodeInput.text().strip(), "serial_number": self.serialNumberInput.text().strip()}
        if not all([data["branch_name"], data["asset_name"]]): QMessageBox.warning(self, "Input Error", "Branch Name and Asset Name are required."); return
        if not (user_signature_path := self.db.get_user_signature_path(self.user[0])): QMessageBox.critical(self, "Error", "Could not find signature."); return
        new_tracking_id = self.db.add_product(data, self.user[0], user_signature_path)
        QMessageBox.information(self, "Success", f"Asset saved.\nTracking ID: {new_tracking_id}")
        self.clear_receive_form(); self.refresh_active_products()
    
    def clear_receive_form(self): self.branchNameInput.clear(); self.assetNameInput.clear(); self.assetCodeInput.clear(); self.serialNumberInput.clear()


if __name__ == '__main__':
    if not os.path.exists("signatures"): os.makedirs("signatures")
    app = QApplication(sys.argv)
    
    # Check for updates directly at startup
    check_for_updates()
    
    try:
        with open(resource_path("style.qss"), "r") as f: app.setStyleSheet(f.read())
    except FileNotFoundError: print("Warning: style.qss not found.")
    
    db = Database() # Connects to the central MySQL server
    
    while True:
        login_dialog = LoginDialog(db)
        if login_dialog.exec() == QDialog.DialogCode.Accepted:
            main_win = MainWindow(login_dialog.user, db)
            main_win.show(); app.exec()
            if main_win.logout_triggered: continue
            else: break
        else: break
    sys.exit(0)