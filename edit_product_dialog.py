from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QDialogButtonBox, QFormLayout, QMessageBox

class EditProductDialog(QDialog):
    def __init__(self, product_details, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Edit Product")
        
        self.tracking_id = product_details[1]
        self.asset_name_input = QLineEdit(product_details[2])
        self.asset_code_input = QLineEdit(product_details[3])
        self.branch_name_input = QLineEdit(product_details[4])
        self.serial_number_input = QLineEdit(product_details[5])
        
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
