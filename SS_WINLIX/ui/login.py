import json
import hashlib
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_USUARIOS = BASE_DIR / "config" / "usuarios.json"

def hash_password(password: str) -> str:
   
    salted = f"SAPPHIRE_SOC_BUAP::{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()

class VentanaLogin(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Autenticación de Seguridad")
        self.setFixedSize(380, 320)
        self.usuario_autenticado = None
        self.intentos_fallidos = 0
        self.usuarios = self._cargar_usuarios()

        self.setStyleSheet("""
            QDialog { background-color: #07090e; color: #e2e8f0; }
            QFrame#CardLogin {
                background-color: #0b0e17;
                border: 1px solid #1a2234;
                border-radius: 10px;
            }
            QLabel { color: #cbd5e1; }
            QLineEdit {
                background-color: #111624; border: 1px solid #243049;
                border-radius: 6px; padding: 9px; color: #f8fafc; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #00e5ff; }
            QPushButton {
                padding: 10px; border-radius: 6px; font-weight: bold; font-size: 13px;
                background-color: #0284c7; color: white; border: none;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setObjectName("CardLogin")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl_titulo = QLabel("Inicio de Sesión")
        lbl_titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel("Si desconoce las credenciales, \ncontacte al administrador del sistema.")
        lbl_sub.setStyleSheet("color: #64748b; font-size: 11px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)
        layout.addSpacing(8)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Operador autorizado")
        layout.addWidget(self.input_user)

        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText("Clave de acceso")
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pass.returnPressed.connect(self._verificar_login)
        layout.addWidget(self.input_pass)

        layout.addSpacing(7)
        self.btn_login = QPushButton("AUTORIZAR ACCESO")
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._verificar_login)
        layout.addWidget(self.btn_login)

    
        root_layout.addWidget(card)

    def _cargar_usuarios(self):
        RUTA_USUARIOS.parent.mkdir(parents=True, exist_ok=True)
        if not RUTA_USUARIOS.exists():
            default_users = {"admin": hash_password("admin123")}
            with open(RUTA_USUARIOS, "w", encoding="utf-8") as f:
                json.dump(default_users, f, indent=4)
            return default_users
        with open(RUTA_USUARIOS, "r", encoding="utf-8") as f:
            return json.load(f)

    def _verificar_login(self):
        user = self.input_user.text().strip()
        pwd = self.input_pass.text().strip()

        # Compatibilidad con hash anterior sin salt o con el nuevo hash con salt
        hash_legacy = hashlib.sha256(pwd.encode("utf-8")).hexdigest()
        hash_actual = hash_password(pwd)

        if user in self.usuarios and self.usuarios[user] in (hash_actual, hash_legacy):
            self.usuario_autenticado = user
            self.accept()
        else:
            self.intentos_fallidos += 1
            if self.intentos_fallidos >= 4:
                QMessageBox.critical(
                    self, "Bloqueo de Seguridad",
                    "Demasiados intentos fallidos. El incidente ha sido registrado."
                )
                self.reject()
            else:
                QMessageBox.warning(
                    self, "Acceso Denegado",
                    f"Credenciales inválidas. Intentos restantes: {4 - self.intentos_fallidos}"
                )