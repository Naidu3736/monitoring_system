import json
from functools import partial
from typing import Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QButtonGroup,
    QLineEdit, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.adm_panel import WidgetTopologiaLabs
from ui.login import RUTA_USUARIOS, hash_password, repolir_widget
from services.hub_bridge import (
    DEFAULT_LOG_PATH,
    HubServerThread,
    guardar_config_env,
    leer_config_env,
)


class VistaConfiguracion(QWidget):
    """Vista integral de Configuración del Sistema con sub-pestañas claras."""

    topologia_modificada = pyqtSignal()

    def __init__(
        self,
        usuario_actual: str,
        datos_laboratorios: dict[str, dict[str, list[str]]],
        hub_thread: HubServerThread | None = None,
        log_callback: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.usuario_actual = usuario_actual
        self.datos_laboratorios = datos_laboratorios
        self.hub_thread = hub_thread
        self.log_callback = log_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        # --- Encabezado + selector de sub-pestañas ---
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        lbl_titulo = QLabel("Configuración del Sistema")
        lbl_titulo.setProperty("class", "page-title")
        title_col.addWidget(lbl_titulo)

        lbl_sub = QLabel(
            "Administra la topología de laboratorios, cuentas de operador y canales de alerta."
        )
        lbl_sub.setProperty("class", "page-subtitle")
        lbl_sub.setWordWrap(True)
        title_col.addWidget(lbl_sub)
        header_row.addLayout(title_col)
        header_row.addStretch()

        tab_bar = QFrame()
        tab_bar.setObjectName("ConfigTabBar")
        tab_lay = QHBoxLayout(tab_bar)
        tab_lay.setContentsMargins(5, 5, 5, 5)
        tab_lay.setSpacing(4)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        pestanas = [
            ("Salas y Equipos", 0),
            ("Operadores y Acceso", 1),
            ("Alertas y Hub", 2),
        ]
        for idx, (texto, stack_idx) in enumerate(pestanas):
            btn = QPushButton(texto)
            btn.setProperty("class", "config-tab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(partial(self.seleccionar_subpestana, stack_idx))
            self.tab_group.addButton(btn, stack_idx)
            tab_lay.addWidget(btn)

        header_row.addWidget(tab_bar, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header_row)

        # --- Contenido por sub-pestañas ---
        self.sub_stack = QStackedWidget()
        self.sub_stack.addWidget(self._crear_tab_topologia())   # 0
        self.sub_stack.addWidget(self._crear_tab_operadores())  # 1
        self.sub_stack.addWidget(self._crear_tab_alertas())     # 2
        root.addWidget(self.sub_stack, stretch=1)

        self._cargar_lista_operadores()
        self._cargar_valores_env()

    def _emitir_log(self, msg: str) -> None:
        if self.log_callback is not None:
            self.log_callback(msg)

    def seleccionar_subpestana(self, idx: int) -> None:
        self.sub_stack.setCurrentIndex(idx)
        btn = self.tab_group.button(idx)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)

    def actualizar_estado_canales(self, tiene_tg: bool, tiene_smtp: bool) -> None:
        self._actualizar_pill(self.pill_tg_card, "Configurado" if tiene_tg else "Sin configurar", "ok" if tiene_tg else "warn")
        self._actualizar_pill(self.pill_smtp_card, "Configurado" if tiene_smtp else "Sin configurar", "ok" if tiene_smtp else "warn")

    @staticmethod
    def _actualizar_pill(label: QLabel, texto: str, state: str) -> None:
        label.setText(texto)
        label.setProperty("state", state)
        repolir_widget(label)

    @staticmethod
    def _mostrar_banner(label: QLabel, mensaje: str, kind: str = "ok") -> None:
        label.setText(mensaje)
        label.setProperty("kind", kind)
        label.setVisible(True)
        repolir_widget(label)

    # =========================================================================
    # PESTAÑA 0: TOPOLOGÍA (SALAS, FILAS Y EQUIPOS)
    # =========================================================================
    def _crear_tab_topologia(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(0)

        self.widget_topologia = WidgetTopologiaLabs(self.datos_laboratorios, page)
        self.widget_topologia.topologia_modificada.connect(self.topologia_modificada.emit)
        lay.addWidget(self.widget_topologia)
        return page

    # =========================================================================
    # PESTAÑA 1: OPERADORES Y ACCESO
    # =========================================================================
    def _crear_tab_operadores(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        contenedor = QWidget()
        contenedor.setObjectName("ScrollContent")
        lay_root = QVBoxLayout(contenedor)
        lay_root.setContentsMargins(0, 4, 6, 4)
        lay_root.setSpacing(16)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        # --- Tarjeta Izquierda: Operadores registrados ---
        card_lista = QFrame()
        card_lista.setProperty("class", "config-card")
        lay_l = QVBoxLayout(card_lista)
        lay_l.setContentsMargins(20, 18, 20, 18)
        lay_l.setSpacing(12)

        head_l = QHBoxLayout()
        lbl_l = QLabel("Operadores Autorizados")
        lbl_l.setProperty("class", "section-title")
        head_l.addWidget(lbl_l)
        head_l.addStretch()
        self.lbl_count_ops = QLabel("0")
        self.lbl_count_ops.setProperty("class", "count-badge")
        head_l.addWidget(self.lbl_count_ops)
        lay_l.addLayout(head_l)

        hint_l = QLabel("Cuentas registradas en config/usuarios.json con acceso al sistema.")
        hint_l.setProperty("class", "muted-hint")
        hint_l.setWordWrap(True)
        lay_l.addWidget(hint_l)

        self.lista_operadores = QListWidget()
        self.lista_operadores.setMinimumHeight(230)
        self.lista_operadores.currentItemChanged.connect(self._actualizar_botones_operador)
        lay_l.addWidget(self.lista_operadores, stretch=1)

        self.banner_ops_list = QLabel("")
        self.banner_ops_list.setObjectName("StatusBanner")
        self.banner_ops_list.setWordWrap(True)
        self.banner_ops_list.setVisible(False)
        lay_l.addWidget(self.banner_ops_list)

        row_btns = QHBoxLayout()
        row_btns.setSpacing(8)
        self.btn_cambiar_pass = QPushButton("Cambiar contraseña")
        self.btn_cambiar_pass.setProperty("class", "btn-secondary")
        self.btn_cambiar_pass.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cambiar_pass.clicked.connect(self._cambiar_password_operador)
        row_btns.addWidget(self.btn_cambiar_pass)

        self.btn_eliminar_op = QPushButton("Eliminar operador")
        self.btn_eliminar_op.setProperty("class", "btn-danger-outline")
        self.btn_eliminar_op.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_eliminar_op.clicked.connect(self._eliminar_operador)
        row_btns.addWidget(self.btn_eliminar_op)
        lay_l.addLayout(row_btns)

        cols.addWidget(card_lista, stretch=5)

        # --- Tarjeta Derecha: Alta de nuevo operador ---
        card_alta = QFrame()
        card_alta.setProperty("class", "config-card")
        lay_a = QVBoxLayout(card_alta)
        lay_a.setContentsMargins(20, 18, 20, 18)
        lay_a.setSpacing(10)

        lbl_a = QLabel("Registrar Nuevo Operador")
        lbl_a.setProperty("class", "section-title")
        lay_a.addWidget(lbl_a)

        hint_a = QLabel(
            "Las contraseñas se almacenan cifradas con SHA-256 con salt."
        )
        hint_a.setProperty("class", "muted-hint")
        hint_a.setWordWrap(True)
        lay_a.addWidget(hint_a)
        lay_a.addSpacing(4)

        lbl_u = QLabel("Nombre de usuario")
        lbl_u.setProperty("class", "field-label")
        lay_a.addWidget(lbl_u)
        self.cfg_new_user = QLineEdit()
        self.cfg_new_user.setPlaceholderText("Mínimo 3 caracteres (ej. operador_buap)")
        lay_a.addWidget(self.cfg_new_user)

        lbl_p = QLabel("Contraseña")
        lbl_p.setProperty("class", "field-label")
        lay_a.addWidget(lbl_p)
        self.cfg_new_pass = QLineEdit()
        self.cfg_new_pass.setPlaceholderText("Mínimo 6 caracteres")
        self.cfg_new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        lay_a.addWidget(self.cfg_new_pass)

        lbl_p2 = QLabel("Confirmar contraseña")
        lbl_p2.setProperty("class", "field-label")
        lay_a.addWidget(lbl_p2)
        self.cfg_new_pass_confirm = QLineEdit()
        self.cfg_new_pass_confirm.setPlaceholderText("Repite la contraseña")
        self.cfg_new_pass_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_new_pass_confirm.returnPressed.connect(self._registrar_operador)
        lay_a.addWidget(self.cfg_new_pass_confirm)

        chk_ver = QCheckBox("Mostrar contraseñas")
        chk_ver.setCursor(Qt.CursorShape.PointingHandCursor)
        chk_ver.toggled.connect(self._toggle_ver_pass_operador)
        lay_a.addWidget(chk_ver)

        self.banner_ops_form = QLabel("")
        self.banner_ops_form.setObjectName("StatusBanner")
        self.banner_ops_form.setWordWrap(True)
        self.banner_ops_form.setVisible(False)
        lay_a.addWidget(self.banner_ops_form)

        lay_a.addStretch()

        btn_crear = QPushButton("Registrar Operador Autorizado")
        btn_crear.setProperty("class", "btn-primary")
        btn_crear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_crear.clicked.connect(self._registrar_operador)
        lay_a.addWidget(btn_crear)

        cols.addWidget(card_alta, stretch=5)

        lay_root.addLayout(cols)
        lay_root.addStretch()
        scroll.setWidget(contenedor)
        return scroll

    def _leer_usuarios(self) -> dict[str, str]:
        if not RUTA_USUARIOS.exists():
            return {}
        with open(RUTA_USUARIOS, "r", encoding="utf-8") as f:
            return json.load(f)

    def _guardar_usuarios(self, usuarios: dict[str, str]) -> None:
        RUTA_USUARIOS.parent.mkdir(parents=True, exist_ok=True)
        with open(RUTA_USUARIOS, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)

    def _cargar_lista_operadores(self, seleccionar: str | None = None) -> None:
        usuarios = self._leer_usuarios()
        self.lista_operadores.blockSignals(True)
        self.lista_operadores.clear()

        sel_idx = 0
        for idx, nombre in enumerate(usuarios.keys()):
            es_actual = nombre == self.usuario_actual
            texto = f"★  {nombre}   (Sesión actual)" if es_actual else f"●  {nombre}"
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, nombre)
            self.lista_operadores.addItem(item)
            if seleccionar and nombre == seleccionar:
                sel_idx = idx
            elif not seleccionar and es_actual:
                sel_idx = idx

        self.lbl_count_ops.setText(str(len(usuarios)))
        if self.lista_operadores.count() > 0:
            self.lista_operadores.setCurrentRow(sel_idx)
        self.lista_operadores.blockSignals(False)
        self._actualizar_botones_operador()

    def _operador_seleccionado(self) -> str | None:
        item = self.lista_operadores.currentItem()
        if item is None:
            return None
        val = item.data(Qt.ItemDataRole.UserRole)
        return str(val) if val else None

    def _actualizar_botones_operador(self) -> None:
        op = self._operador_seleccionado()
        total = self.lista_operadores.count()
        self.btn_cambiar_pass.setEnabled(op is not None)
        self.btn_eliminar_op.setEnabled(
            op is not None and op != self.usuario_actual and total > 1
        )

    def _toggle_ver_pass_operador(self, checked: bool) -> None:
        modo = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.cfg_new_pass.setEchoMode(modo)
        self.cfg_new_pass_confirm.setEchoMode(modo)

    def _registrar_operador(self) -> None:
        u = self.cfg_new_user.text().strip()
        p = self.cfg_new_pass.text().strip()
        p2 = self.cfg_new_pass_confirm.text().strip()

        if len(u) < 3:
            self._mostrar_banner(
                self.banner_ops_form,
                "El nombre de usuario debe tener al menos 3 caracteres.",
                "warn",
            )
            self.cfg_new_user.setFocus()
            return
        if len(p) < 6:
            self._mostrar_banner(
                self.banner_ops_form,
                "La contraseña debe tener al menos 6 caracteres.",
                "warn",
            )
            self.cfg_new_pass.setFocus()
            return
        if p != p2:
            self._mostrar_banner(
                self.banner_ops_form,
                "Las contraseñas no coinciden. Verifica e intenta de nuevo.",
                "error",
            )
            self.cfg_new_pass_confirm.setFocus()
            return

        usuarios = self._leer_usuarios()
        if u in usuarios:
            self._mostrar_banner(
                self.banner_ops_form,
                f"El operador '{u}' ya está registrado.",
                "warn",
            )
            return

        usuarios[u] = hash_password(p)
        self._guardar_usuarios(usuarios)
        self.cfg_new_user.clear()
        self.cfg_new_pass.clear()
        self.cfg_new_pass_confirm.clear()
        self._cargar_lista_operadores(seleccionar=u)
        self._mostrar_banner(
            self.banner_ops_form,
            f"Operador '{u}' registrado correctamente.",
            "ok",
        )
        self._emitir_log(f"Nuevo operador '{u}' dado de alta por '{self.usuario_actual}'.")

    def _cambiar_password_operador(self) -> None:
        op = self._operador_seleccionado()
        if not op:
            return
        nueva, ok = QInputDialog.getText(
            self,
            "Cambiar contraseña",
            f"Nueva contraseña para '{op}' (mínimo 6 caracteres):",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        nueva = nueva.strip()
        if len(nueva) < 6:
            self._mostrar_banner(
                self.banner_ops_list,
                "La nueva contraseña debe tener al menos 6 caracteres.",
                "warn",
            )
            return

        usuarios = self._leer_usuarios()
        if op not in usuarios:
            return
        usuarios[op] = hash_password(nueva)
        self._guardar_usuarios(usuarios)
        self._mostrar_banner(
            self.banner_ops_list,
            f"Contraseña actualizada para '{op}'.",
            "ok",
        )
        self._emitir_log(f"Contraseña del operador '{op}' actualizada por '{self.usuario_actual}'.")

    def _eliminar_operador(self) -> None:
        op = self._operador_seleccionado()
        if not op or op == self.usuario_actual:
            return

        resp = QMessageBox.question(
            self,
            "Eliminar operador",
            f"¿Seguro que deseas revocar el acceso y eliminar al operador '{op}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        usuarios = self._leer_usuarios()
        if len(usuarios) <= 1 or op not in usuarios:
            return
        del usuarios[op]
        self._guardar_usuarios(usuarios)
        self._cargar_lista_operadores()
        self._mostrar_banner(
            self.banner_ops_list,
            f"Operador '{op}' eliminado.",
            "info",
        )
        self._emitir_log(f"Operador '{op}' eliminado por '{self.usuario_actual}'.")

    # =========================================================================
    # PESTAÑA 2: ALERTAS (TELEGRAM / SMTP) Y SERVIDOR HUB
    # =========================================================================
    def _crear_tab_alertas(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        contenedor = QWidget()
        contenedor.setObjectName("ScrollContent")
        lay_root = QVBoxLayout(contenedor)
        lay_root.setContentsMargins(0, 4, 8, 8)
        lay_root.setSpacing(14)

        # --- Fila superior: Telegram + Hub TCP ---
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Tarjeta Telegram
        card_tg = QFrame()
        card_tg.setProperty("class", "config-card")
        lay_tg = QVBoxLayout(card_tg)
        lay_tg.setContentsMargins(20, 18, 20, 18)
        lay_tg.setSpacing(10)

        h_tg = QHBoxLayout()
        lbl_tg = QLabel("Bot de Telegram")
        lbl_tg.setProperty("class", "section-title")
        h_tg.addWidget(lbl_tg)
        h_tg.addStretch()
        self.pill_tg_card = QLabel("Sin configurar")
        self.pill_tg_card.setProperty("class", "status-pill")
        self.pill_tg_card.setProperty("state", "warn")
        h_tg.addWidget(self.pill_tg_card)
        lay_tg.addLayout(h_tg)

        hint_tg = QLabel("Envía avisos instantáneos al chat o grupo de seguridad al detectar una intrusión.")
        hint_tg.setProperty("class", "muted-hint")
        hint_tg.setWordWrap(True)
        lay_tg.addWidget(hint_tg)

        lbl_tk = QLabel("Token del Bot (TELEGRAM_BOT_TOKEN)")
        lbl_tk.setProperty("class", "field-label")
        lay_tg.addWidget(lbl_tk)
        self.env_tg_token = QLineEdit()
        self.env_tg_token.setPlaceholderText("123456:ABC-DEF...")
        self.env_tg_token.setEchoMode(QLineEdit.EchoMode.Password)
        lay_tg.addWidget(self.env_tg_token)

        lbl_cid = QLabel("Chat ID destino (TELEGRAM_CHAT_ID)")
        lbl_cid.setProperty("class", "field-label")
        lay_tg.addWidget(lbl_cid)
        self.env_tg_chat = QLineEdit()
        self.env_tg_chat.setPlaceholderText("Ej. -1001234567890")
        lay_tg.addWidget(self.env_tg_chat)

        chk_tg = QCheckBox("Mostrar token")
        chk_tg.setCursor(Qt.CursorShape.PointingHandCursor)
        chk_tg.toggled.connect(
            lambda c: self.env_tg_token.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        lay_tg.addWidget(chk_tg)
        lay_tg.addStretch()
        top_row.addWidget(card_tg, stretch=1)

        # Tarjeta Hub TCP
        card_hub = QFrame()
        card_hub.setProperty("class", "config-card")
        lay_hub = QVBoxLayout(card_hub)
        lay_hub.setContentsMargins(20, 18, 20, 18)
        lay_hub.setSpacing(10)

        h_hub = QHBoxLayout()
        lbl_hub = QLabel("Servidor Hub TCP y Bitácora")
        lbl_hub.setProperty("class", "section-title")
        h_hub.addWidget(lbl_hub)
        h_hub.addStretch()
        self.pill_hub_card = QLabel("0.0.0.0:5000")
        self.pill_hub_card.setProperty("class", "status-pill")
        self.pill_hub_card.setProperty("state", "info")
        h_hub.addWidget(self.pill_hub_card)
        lay_hub.addLayout(h_hub)

        hint_hub = QLabel("Interfaz de red donde el servidor recibe eventos de los agentes pc_monitoring.")
        hint_hub.setProperty("class", "muted-hint")
        hint_hub.setWordWrap(True)
        lay_hub.addWidget(hint_hub)

        grid_hub = QGridLayout()
        grid_hub.setHorizontalSpacing(12)
        grid_hub.setVerticalSpacing(6)

        lbl_h = QLabel("Host de escucha (HUB_HOST)")
        lbl_h.setProperty("class", "field-label")
        lbl_pt = QLabel("Puerto TCP (HUB_PORT)")
        lbl_pt.setProperty("class", "field-label")
        self.env_hub_host = QLineEdit()
        self.env_hub_host.setPlaceholderText("0.0.0.0")
        self.env_hub_port = QLineEdit()
        self.env_hub_port.setPlaceholderText("5000")

        grid_hub.addWidget(lbl_h, 0, 0)
        grid_hub.addWidget(lbl_pt, 0, 1)
        grid_hub.addWidget(self.env_hub_host, 1, 0)
        grid_hub.addWidget(self.env_hub_port, 1, 1)
        lay_hub.addLayout(grid_hub)

        lbl_log_t = QLabel("Archivo de bitácora (solo lectura)")
        lbl_log_t.setProperty("class", "field-label")
        lay_hub.addWidget(lbl_log_t)

        txt_log = QLineEdit(str(DEFAULT_LOG_PATH))
        txt_log.setReadOnly(True)
        lay_hub.addWidget(txt_log)

        nota_hub = QLabel(
            "Telegram y SMTP se aplican al instante. Cambiar Host o Puerto del Hub surte efecto al reiniciar la app."
        )
        nota_hub.setProperty("class", "muted-hint")
        nota_hub.setWordWrap(True)
        lay_hub.addWidget(nota_hub)
        lay_hub.addStretch()
        top_row.addWidget(card_hub, stretch=1)

        lay_root.addLayout(top_row)

        # --- Tarjeta SMTP a ancho completo ---
        card_smtp = QFrame()
        card_smtp.setProperty("class", "config-card")
        lay_smtp = QVBoxLayout(card_smtp)
        lay_smtp.setContentsMargins(20, 18, 20, 18)
        lay_smtp.setSpacing(10)

        h_smtp = QHBoxLayout()
        lbl_smtp = QLabel("Notificaciones por Correo Electrónico (SMTP)")
        lbl_smtp.setProperty("class", "section-title")
        h_smtp.addWidget(lbl_smtp)
        h_smtp.addStretch()
        self.pill_smtp_card = QLabel("Sin configurar")
        self.pill_smtp_card.setProperty("class", "status-pill")
        self.pill_smtp_card.setProperty("state", "warn")
        h_smtp.addWidget(self.pill_smtp_card)
        lay_smtp.addLayout(h_smtp)

        hint_smtp = QLabel("Completa todos los campos para activar el envío automático de alertas por correo.")
        hint_smtp.setProperty("class", "muted-hint")
        lay_smtp.addWidget(hint_smtp)

        grid_smtp = QGridLayout()
        grid_smtp.setHorizontalSpacing(16)
        grid_smtp.setVerticalSpacing(8)

        self.env_smtp_host = QLineEdit()
        self.env_smtp_host.setPlaceholderText("Ej. smtp.gmail.com")
        self.env_smtp_port = QLineEdit()
        self.env_smtp_port.setPlaceholderText("Ej. 587")
        self.env_smtp_user = QLineEdit()
        self.env_smtp_user.setPlaceholderText("usuario@dominio.com")
        self.env_smtp_pass = QLineEdit()
        self.env_smtp_pass.setPlaceholderText("Contraseña o App Password")
        self.env_smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.env_smtp_sender = QLineEdit()
        self.env_smtp_sender.setPlaceholderText("alertas@buap.mx")
        self.env_smtp_recipient = QLineEdit()
        self.env_smtp_recipient.setPlaceholderText("responsable@buap.mx")

        campos_smtp = [
            ("Servidor SMTP (SMTP_HOST)", self.env_smtp_host, 0, 0),
            ("Puerto (SMTP_PORT)", self.env_smtp_port, 0, 1),
            ("Usuario SMTP (SMTP_USERNAME)", self.env_smtp_user, 2, 0),
            ("Contraseña SMTP (SMTP_PASSWORD)", self.env_smtp_pass, 2, 1),
            ("Remitente (SMTP_SENDER)", self.env_smtp_sender, 4, 0),
            ("Destinatario (SMTP_RECIPIENT)", self.env_smtp_recipient, 4, 1),
        ]
        for titulo_campo, widget_campo, fila_g, col_g in campos_smtp:
            lbl_f = QLabel(titulo_campo)
            lbl_f.setProperty("class", "field-label")
            grid_smtp.addWidget(lbl_f, fila_g, col_g)
            grid_smtp.addWidget(widget_campo, fila_g + 1, col_g)

        lay_smtp.addLayout(grid_smtp)

        opts_smtp = QHBoxLayout()
        opts_smtp.setSpacing(20)
        self.env_smtp_tls = QCheckBox("Usar cifrado TLS (SMTP_USE_TLS)")
        self.env_smtp_tls.setChecked(True)
        self.env_smtp_tls.setCursor(Qt.CursorShape.PointingHandCursor)
        opts_smtp.addWidget(self.env_smtp_tls)

        chk_smtp_pass = QCheckBox("Mostrar contraseña SMTP")
        chk_smtp_pass.setCursor(Qt.CursorShape.PointingHandCursor)
        chk_smtp_pass.toggled.connect(
            lambda c: self.env_smtp_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        opts_smtp.addWidget(chk_smtp_pass)
        opts_smtp.addStretch()
        lay_smtp.addLayout(opts_smtp)

        lay_root.addWidget(card_smtp)

        # --- Barra inferior de guardado y estado ---
        self.banner_env = QLabel("")
        self.banner_env.setObjectName("StatusBanner")
        self.banner_env.setWordWrap(True)
        self.banner_env.setVisible(False)
        lay_root.addWidget(self.banner_env)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch()

        btn_recargar = QPushButton("Recargar valores")
        btn_recargar.setProperty("class", "btn-secondary")
        btn_recargar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_recargar.clicked.connect(self._recargar_valores_env_click)
        footer.addWidget(btn_recargar)

        btn_guardar = QPushButton("Guardar y Aplicar")
        btn_guardar.setProperty("class", "btn-primary")
        btn_guardar.setMinimumWidth(160)
        btn_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_guardar.clicked.connect(self._guardar_valores_env)
        footer.addWidget(btn_guardar)

        lay_root.addLayout(footer)
        lay_root.addStretch()
        scroll.setWidget(contenedor)
        return scroll

    def _cargar_valores_env(self) -> None:
        cfg = leer_config_env()
        self.env_tg_token.setText(cfg.get("TELEGRAM_BOT_TOKEN", ""))
        self.env_tg_chat.setText(cfg.get("TELEGRAM_CHAT_ID", ""))

        self.env_smtp_host.setText(cfg.get("SMTP_HOST", ""))
        self.env_smtp_port.setText(cfg.get("SMTP_PORT", ""))
        self.env_smtp_user.setText(cfg.get("SMTP_USERNAME", ""))
        self.env_smtp_pass.setText(cfg.get("SMTP_PASSWORD", ""))
        self.env_smtp_sender.setText(cfg.get("SMTP_SENDER", ""))
        self.env_smtp_recipient.setText(cfg.get("SMTP_RECIPIENT", ""))
        use_tls = cfg.get("SMTP_USE_TLS", "true").lower() != "false"
        self.env_smtp_tls.setChecked(use_tls)

        hub_host = cfg.get("HUB_HOST", "") or "0.0.0.0"
        hub_port = cfg.get("HUB_PORT", "") or "5000"
        self.env_hub_host.setText(hub_host)
        self.env_hub_port.setText(hub_port)
        self.pill_hub_card.setText(f"{hub_host}:{hub_port}")

    def _recargar_valores_env_click(self) -> None:
        self._cargar_valores_env()
        self._mostrar_banner(self.banner_env, "Valores recargados desde .env.", "info")

    def _guardar_valores_env(self) -> None:
        hub_port = self.env_hub_port.text().strip() or "5000"
        smtp_port = self.env_smtp_port.text().strip()

        if not hub_port.isdigit() or not (1 <= int(hub_port) <= 65535):
            self._mostrar_banner(
                self.banner_env,
                "El puerto del Hub (HUB_PORT) debe ser un número entre 1 y 65535.",
                "error",
            )
            self.env_hub_port.setFocus()
            return

        if smtp_port and (not smtp_port.isdigit() or not (1 <= int(smtp_port) <= 65535)):
            self._mostrar_banner(
                self.banner_env,
                "El puerto SMTP debe ser un número entre 1 y 65535.",
                "error",
            )
            self.env_smtp_port.setFocus()
            return

        valores = {
            "TELEGRAM_BOT_TOKEN": self.env_tg_token.text().strip(),
            "TELEGRAM_CHAT_ID": self.env_tg_chat.text().strip(),
            "SMTP_HOST": self.env_smtp_host.text().strip(),
            "SMTP_PORT": smtp_port,
            "SMTP_USERNAME": self.env_smtp_user.text().strip(),
            "SMTP_PASSWORD": self.env_smtp_pass.text().strip(),
            "SMTP_SENDER": self.env_smtp_sender.text().strip(),
            "SMTP_RECIPIENT": self.env_smtp_recipient.text().strip(),
            "SMTP_USE_TLS": "true" if self.env_smtp_tls.isChecked() else "false",
            "HUB_HOST": self.env_hub_host.text().strip() or "0.0.0.0",
            "HUB_PORT": hub_port,
        }

        try:
            guardar_config_env(valores)
        except Exception as exc:
            self._mostrar_banner(
                self.banner_env, f"No se pudo guardar .env: {exc}", "error"
            )
            return

        self.pill_hub_card.setText(f"{valores['HUB_HOST']}:{valores['HUB_PORT']}")

        if self.hub_thread is not None:
            tiene_tg, tiene_smtp = self.hub_thread.recargar_canales()
            self.actualizar_estado_canales(tiene_tg, tiene_smtp)

        self._mostrar_banner(
            self.banner_env,
            "Configuración guardada en .env y canales de alerta actualizados.",
            "ok",
        )
        self._emitir_log(f"Configuración de alertas/Hub guardada en .env por '{self.usuario_actual}'.")
