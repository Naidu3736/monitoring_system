import json
import hashlib
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_USUARIOS = BASE_DIR / "config" / "usuarios.json"

MAX_INTENTOS = 4
SEGUNDOS_BLOQUEO = 15


def hash_password(password: str) -> str:
    salted = f"SAPPHIRE_SOC_BUAP::{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def repolir_widget(widget: QWidget) -> None:
    st = widget.style()
    if st is not None:
        st.unpolish(widget)
        st.polish(widget)


class VistaLogin(QWidget):
    """Pantalla de inicio de sesión integrada en la ventana principal."""

    autenticado = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LoginRoot")
        self.intentos_fallidos = 0
        self._bloqueo_restante = 0

        self._timer_bloqueo = QTimer(self)
        self._timer_bloqueo.timeout.connect(self._tick_bloqueo)

        self._armar_interfaz()

    def _armar_interfaz(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch(1)

        center_row = QHBoxLayout()
        center_row.addStretch(1)

        shell = QFrame()
        shell.setObjectName("LoginShell")
        shell.setMinimumSize(760, 440)
        shell.setMaximumSize(880, 500)

        shell_lay = QHBoxLayout(shell)
        shell_lay.setContentsMargins(0, 0, 0, 0)
        shell_lay.setSpacing(0)

        # =====================================================================
        # PANEL IZQUIERDO: IDENTIDAD Y CONTEXTO DEL SISTEMA
        # =====================================================================
        brand = QFrame()
        brand.setObjectName("LoginBrandPanel")
        brand.setFixedWidth(365)
        b_lay = QVBoxLayout(brand)
        b_lay.setContentsMargins(32, 34, 28, 30)
        b_lay.setSpacing(12)

        pill_row = QHBoxLayout()
        lbl_pill = QLabel("FCC  •  BUAP")
        lbl_pill.setProperty("class", "login-pill")
        pill_row.addWidget(lbl_pill)
        pill_row.addStretch()
        b_lay.addLayout(pill_row)

        b_lay.addSpacing(6)

        lbl_logo = QLabel("SAPPHIRE SOC")
        lbl_logo.setProperty("class", "login-brand-title")
        b_lay.addWidget(lbl_logo)

        lbl_sub = QLabel("Centro de Monitoreo de Seguridad de Hardware")
        lbl_sub.setProperty("class", "login-brand-sub")
        lbl_sub.setWordWrap(True)
        b_lay.addWidget(lbl_sub)

        b_lay.addSpacing(14)

        separador = QFrame()
        separador.setObjectName("LoginDivider")
        separador.setFixedHeight(1)
        b_lay.addWidget(separador)

        b_lay.addSpacing(10)

        caracteristicas = [
            "●  Supervisión en tiempo real de periféricos conectados en laboratorio.",
            "●  Recepción centralizada vía Hub TCP para agentes Windows y Linux.",
            "●  Despacho directo de alertas por Telegram, SMTP y bitácora forense.",
        ]
        for texto in caracteristicas:
            lbl_f = QLabel(texto)
            lbl_f.setProperty("class", "login-feature")
            lbl_f.setWordWrap(True)
            b_lay.addWidget(lbl_f)

        b_lay.addStretch(1)

        lbl_pie = QLabel("Acceso exclusivo para operadores autorizados")
        lbl_pie.setProperty("class", "muted-hint")
        b_lay.addWidget(lbl_pie)

        shell_lay.addWidget(brand)

        # =====================================================================
        # PANEL DERECHO: FORMULARIO DE AUTENTICACIÓN
        # =====================================================================
        form = QFrame()
        form.setObjectName("LoginFormPanel")
        f_lay = QVBoxLayout(form)
        f_lay.setContentsMargins(38, 36, 38, 32)
        f_lay.setSpacing(10)

        lbl_titulo = QLabel("Iniciar sesión")
        lbl_titulo.setProperty("class", "page-title")
        f_lay.addWidget(lbl_titulo)

        lbl_desc = QLabel(
            "Ingresa tus credenciales de operador para abrir el panel de monitoreo."
        )
        lbl_desc.setProperty("class", "page-subtitle")
        lbl_desc.setWordWrap(True)
        f_lay.addWidget(lbl_desc)

        f_lay.addSpacing(10)

        lbl_user = QLabel("Operador")
        lbl_user.setProperty("class", "field-label")
        f_lay.addWidget(lbl_user)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Nombre de usuario autorizado")
        self.input_user.returnPressed.connect(self._ir_a_password)
        f_lay.addWidget(self.input_user)

        f_lay.addSpacing(4)

        lbl_pass = QLabel("Contraseña")
        lbl_pass.setProperty("class", "field-label")
        f_lay.addWidget(lbl_pass)

        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText("Clave de acceso")
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pass.returnPressed.connect(self._verificar_login)
        f_lay.addWidget(self.input_pass)

        opts_row = QHBoxLayout()
        self.chk_mostrar = QCheckBox("Mostrar contraseña")
        self.chk_mostrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_mostrar.toggled.connect(self._toggle_mostrar_password)
        opts_row.addWidget(self.chk_mostrar)
        opts_row.addStretch()
        f_lay.addLayout(opts_row)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setObjectName("StatusBanner")
        self.lbl_estado.setWordWrap(True)
        self.lbl_estado.setVisible(False)
        f_lay.addWidget(self.lbl_estado)

        f_lay.addSpacing(8)

        self.btn_login = QPushButton("Ingresar al Panel")
        self.btn_login.setProperty("class", "btn-primary")
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._verificar_login)
        f_lay.addWidget(self.btn_login)

        f_lay.addStretch(1)

        lbl_ayuda = QLabel(
            "Si desconoces tus credenciales, contacta al administrador del sistema."
        )
        lbl_ayuda.setProperty("class", "muted-hint")
        lbl_ayuda.setWordWrap(True)
        f_lay.addWidget(lbl_ayuda)

        shell_lay.addWidget(form, stretch=1)

        center_row.addWidget(shell)
        center_row.addStretch(1)
        outer.addLayout(center_row)
        outer.addStretch(1)

    def reiniciar_formulario(self) -> None:
        self._timer_bloqueo.stop()
        self.intentos_fallidos = 0
        self._bloqueo_restante = 0
        self.input_user.clear()
        self.input_pass.clear()
        self.chk_mostrar.setChecked(False)
        self.input_user.setEnabled(True)
        self.input_pass.setEnabled(True)
        self.btn_login.setEnabled(True)
        self.lbl_estado.setVisible(False)
        self.input_user.setFocus()

    def _ir_a_password(self) -> None:
        if self.input_pass.text().strip():
            self._verificar_login()
        else:
            self.input_pass.setFocus()

    def _toggle_mostrar_password(self, visible: bool) -> None:
        self.input_pass.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    def _mostrar_aviso(self, mensaje: str, kind: str = "warn") -> None:
        self.lbl_estado.setText(mensaje)
        self.lbl_estado.setProperty("kind", kind)
        self.lbl_estado.setVisible(True)
        repolir_widget(self.lbl_estado)

    def _cargar_usuarios(self) -> dict[str, str]:
        RUTA_USUARIOS.parent.mkdir(parents=True, exist_ok=True)
        if not RUTA_USUARIOS.exists():
            default_users = {"admin": hash_password("admin123")}
            with open(RUTA_USUARIOS, "w", encoding="utf-8") as f:
                json.dump(default_users, f, indent=4)
            return default_users
        with open(RUTA_USUARIOS, "r", encoding="utf-8") as f:
            return json.load(f)

    def _verificar_login(self) -> None:
        if self._bloqueo_restante > 0:
            return

        user = self.input_user.text().strip()
        pwd = self.input_pass.text().strip()

        if not user or not pwd:
            self._mostrar_aviso("Ingresa tu usuario y contraseña para continuar.", "warn")
            if not user:
                self.input_user.setFocus()
            else:
                self.input_pass.setFocus()
            return

        usuarios = self._cargar_usuarios()
        hash_legacy = hashlib.sha256(pwd.encode("utf-8")).hexdigest()
        hash_actual = hash_password(pwd)

        if user in usuarios and usuarios[user] in (hash_actual, hash_legacy):
            self.intentos_fallidos = 0
            self.lbl_estado.setVisible(False)
            self.input_pass.clear()
            self.autenticado.emit(user)
            return

        self.intentos_fallidos += 1
        self.input_pass.clear()
        self.input_pass.setFocus()

        if self.intentos_fallidos >= MAX_INTENTOS:
            self._iniciar_bloqueo()
        else:
            restantes = MAX_INTENTOS - self.intentos_fallidos
            self._mostrar_aviso(
                f"Credenciales inválidas. Intentos restantes: {restantes}.",
                "error",
            )

    def _iniciar_bloqueo(self) -> None:
        self._bloqueo_restante = SEGUNDOS_BLOQUEO
        self.input_user.setEnabled(False)
        self.input_pass.setEnabled(False)
        self.btn_login.setEnabled(False)
        self._mostrar_aviso(
            f"Demasiados intentos fallidos. Espera {self._bloqueo_restante}s para volver a intentar.",
            "error",
        )
        self._timer_bloqueo.start(1000)

    def _tick_bloqueo(self) -> None:
        self._bloqueo_restante -= 1
        if self._bloqueo_restante <= 0:
            self._timer_bloqueo.stop()
            self.intentos_fallidos = 0
            self.input_user.setEnabled(True)
            self.input_pass.setEnabled(True)
            self.btn_login.setEnabled(True)
            self._mostrar_aviso("Bloqueo finalizado. Puedes intentar de nuevo.", "info")
            self.input_user.setFocus()
        else:
            self._mostrar_aviso(
                f"Demasiados intentos fallidos. Espera {self._bloqueo_restante}s para volver a intentar.",
                "error",
            )
