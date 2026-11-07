import json
from functools import partial
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QTextEdit,
    QStackedWidget, QButtonGroup, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QColor, QCloseEvent

from ui.card_pc import TarjetaPC
from ui.adm_panel import DialogoAdminLabs
from ui.login import RUTA_USUARIOS, hash_password
from services.hub_bridge import HubServerThread, DEFAULT_LOG_PATH

BASE_DIR = Path(__file__).resolve().parent.parent


class DashboardPrincipal(QMainWindow):
    def __init__(self, usuario_actual: str = "admin") -> None:
        super().__init__()
        self.usuario_actual = usuario_actual
        self.setWindowTitle(
            f"Monitoreo de Seguridad de Hardware (BUAP) - Operador: {self.usuario_actual}"
        )
        self.resize(1360, 780)

        self.datos_laboratorios: dict[str, dict[str, list[str]]] = self._cargar_config_laboratorios()
        self.tarjetas_map: dict[str, TarjetaPC] = {}
        self.btns_tabs: dict[str, QPushButton] = {}
        self.pc_seleccionada: str | None = None
        self.pcs_en_alerta: set[str] = set()
        self.fase_parpadeo: bool = False
        self.tiene_tg_configurado: bool = False
        self.tiene_smtp_configurado: bool = False

        self.cargar_estilos()
        self._armar_interfaz()
        self._actualizar_contadores_kpi()

        # Atajos de teclado: F2 (Menú Izquierdo), F3 (Detalles Derecho), F5 (Estilos)
        self.shortcut_sidebar = QShortcut(QKeySequence("F2"), self)
        self.shortcut_sidebar.activated.connect(self._toggle_sidebar)

        self.shortcut_inspector = QShortcut(QKeySequence("F3"), self)
        self.shortcut_inspector.activated.connect(self._toggle_inspector)

        self.shortcut_reload = QShortcut(QKeySequence("F5"), self)
        self.shortcut_reload.activated.connect(self.cargar_estilos)

        self.timer_parpadeo = QTimer(self)
        self.timer_parpadeo.timeout.connect(self._toggle_parpadeo)
        self.timer_parpadeo.start(450)

        # Arrancar el Hub Server de monitoring_system-main en segundo plano
        self.hub_thread = HubServerThread()
        self.hub_thread.log_signal.connect(self.agregar_log)
        self.hub_thread.canales_configurados.connect(self._actualizar_estado_canales)
        self.hub_thread.reporte_recibido.connect(self._procesar_reporte_hub)
        self.hub_thread.alerta_procesada.connect(self._mostrar_resultado_alert_manager)
        self.hub_thread.start()

        # Cargar historial de monitoring_system-main/logs/alerts.log
        self._cargar_logs_previos()

    def _cargar_config_laboratorios(self) -> dict[str, dict[str, list[str]]]:
        ruta_json = BASE_DIR / "config" / "laboratorios.json"
        if not ruta_json.exists():
            ruta_json.parent.mkdir(parents=True, exist_ok=True)
            default_labs = {
                "LABORATORIO 01": {
                    "FILA A": ["PC-02", "PC-03", "PC-04", "PC-05", "PC-06", "PC-07"],
                    "FILA B": ["PC-08", "PC-09", "PC-10", "PC-11", "PC-12", "PC-13"]
                }
            }
            with open(ruta_json, "w", encoding="utf-8") as f:
                json.dump(default_labs, f, indent=4)
            return default_labs
        with open(ruta_json, "r", encoding="utf-8") as f:
            return json.load(f)

    def cargar_estilos(self) -> None:
        ruta_estilos = BASE_DIR / "assets" / "styles.css"
        if ruta_estilos.exists():
            with open(ruta_estilos, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            if hasattr(self, "console"):
                self.agregar_log("Estilos visuales (styles.css) recargados.")

    def _armar_interfaz(self) -> None:
        root = QWidget()
        layout_root = QHBoxLayout(root)
        layout_root.setContentsMargins(0, 0, 0, 0)
        layout_root.setSpacing(0)

        self.main_stack = QStackedWidget()

        self.sidebar_widget = self._crear_sidebar()
        layout_root.addWidget(self.sidebar_widget)

        self.main_stack.addWidget(self._crear_vista_monitoreo())   # 0: Centro de Monitoreo
        self.main_stack.addWidget(self._crear_vista_eventos())     # 1: Registro de Eventos
        self.main_stack.addWidget(self._crear_vista_red())         # 2: Registro de Red
        self.main_stack.addWidget(self._crear_vista_config())      # 3: Configuración del Sistema

        layout_root.addWidget(self.main_stack)
        self.setCentralWidget(root)

    def _crear_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(235)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 18)
        layout.setSpacing(6)

        lbl_logo = QLabel("SAPPHIRE SOC")
        lbl_logo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_logo.setStyleSheet("color: #00e5ff; letter-spacing: 0.5px;")
        lbl_sub = QLabel("FCC - Seguridad de Hardware BUAP")
        lbl_sub.setStyleSheet("color: #64748b; font-size: 11px;")

        layout.addWidget(lbl_logo)
        layout.addWidget(lbl_sub)
        layout.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        botones_info = [
            ("  Centro de Monitoreo", 0),
            ("  Registro de Eventos", 1),
            ("  Registro de Red", 2),
            ("  Configuración del Sistema", 3),
        ]

        for idx, (texto, stack_idx) in enumerate(botones_info):
            btn = QPushButton(texto)
            btn.setProperty("class", "nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(partial(self.main_stack.setCurrentIndex, stack_idx))
            self.nav_group.addButton(btn, stack_idx)
            layout.addWidget(btn)

        layout.addSpacing(10)
        btn_admin_labs = QPushButton("  Editar Salas / PCs")
        btn_admin_labs.setProperty("class", "nav-btn")
        btn_admin_labs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_admin_labs.clicked.connect(self._abrir_admin_labs)
        layout.addWidget(btn_admin_labs)

        layout.addStretch()

        box_user = QFrame()
        box_user.setStyleSheet(
            "background-color: #0d121f; border: 1px solid #1e293b; border-radius: 6px; padding: 6px;"
        )
        lay_u = QVBoxLayout(box_user)
        lay_u.setContentsMargins(6, 4, 6, 4)
        lbl_op = QLabel(f"Operador: {self.usuario_actual.upper()}")
        lbl_op.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: bold;")
        lbl_buap = QLabel("Protección de Hardware BUAP")
        lbl_buap.setStyleSheet("color: #64748b; font-size: 10px;")
        lay_u.addWidget(lbl_op)
        lay_u.addWidget(lbl_buap)
        layout.addWidget(box_user)

        return sidebar

    def _toggle_sidebar(self) -> None:
        visible = not self.sidebar_widget.isVisible()
        self.sidebar_widget.setVisible(visible)
        if hasattr(self, "btn_toggle_left"):
            self.btn_toggle_left.setText("☰" if not visible else "◀ Menú")

    def _toggle_inspector(self) -> None:
        visible = not self.inspector_widget.isVisible()
        self.inspector_widget.setVisible(visible)
        if hasattr(self, "btn_toggle_right"):
            self.btn_toggle_right.setText("◨ Detalles" if not visible else "Detalles ▶")

    def _crear_vista_monitoreo(self) -> QWidget:
        area_central = QWidget()
        layout_central = QVBoxLayout(area_central)
        layout_central.setContentsMargins(16, 14, 16, 14)
        layout_central.setSpacing(12)

        layout_central.addLayout(self._crear_header_kpis())

        body = QHBoxLayout()
        body.setSpacing(14)

        self.stacked_labs = QStackedWidget()
        self._construir_vistas_laboratorios()
        body.addWidget(self.stacked_labs, stretch=7)

        self.inspector_widget = self._crear_panel_inspector()
        body.addWidget(self.inspector_widget, stretch=3)
        layout_central.addLayout(body, stretch=8)

        layout_central.addWidget(self._crear_consola_logs(), stretch=2)
        return area_central

    def _crear_header_kpis(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)

        self.btn_toggle_left = QPushButton("◀ Menú")
        self.btn_toggle_left.setToolTip("Ocultar/Mostrar menú izquierdo (F2)")
        self.btn_toggle_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_left.setStyleSheet(
            "background-color: #111726; color: #94a3b8; border: 1px solid #1e293b; "
            "border-radius: 6px; padding: 6px 10px; font-weight: bold; font-size: 11px;"
        )
        self.btn_toggle_left.clicked.connect(self._toggle_sidebar)
        header.addWidget(self.btn_toggle_left)

        self.tabs_box = QHBoxLayout()
        self.tabs_box.setSpacing(8)
        self._reconstruir_tabs_labs()
        header.addLayout(self.tabs_box)

        btn_quick_lab = QPushButton("Salas")
        btn_quick_lab.setToolTip("Agregar o quitar Salas, Filas y Equipos")
        btn_quick_lab.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quick_lab.setStyleSheet(
            "background-color: #111726; color: #38bdf8; border: 1px dashed #1e3a5f; "
            "border-radius: 6px; padding: 6px 10px; font-weight: bold; font-size: 11px;"
        )
        btn_quick_lab.clicked.connect(self._abrir_admin_labs)
        header.addWidget(btn_quick_lab)

        header.addStretch()

        pill_nodes = QFrame()
        pill_nodes.setProperty("class", "kpi-pill")
        lay_n = QHBoxLayout(pill_nodes)
        lay_n.setContentsMargins(8, 2, 8, 2)
        self.lbl_kpi_nodos = QLabel("ACTIVOS: 0 OK | 0 ALERTA")
        self.lbl_kpi_nodos.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: bold;")
        lay_n.addWidget(self.lbl_kpi_nodos)
        header.addWidget(pill_nodes)

        pill_status = QFrame()
        pill_status.setProperty("class", "kpi-pill")
        lay_s = QHBoxLayout(pill_status)
        lay_s.setContentsMargins(8, 2, 8, 2)
        self.lbl_kpi_alerta = QLabel("● PERÍMETRO: SEGURO")
        self.lbl_kpi_alerta.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold;")
        lay_s.addWidget(self.lbl_kpi_alerta)
        header.addWidget(pill_status)

        pill_hb = QFrame()
        pill_hb.setProperty("class", "kpi-pill")
        lay_h = QHBoxLayout(pill_hb)
        lay_h.setContentsMargins(8, 2, 8, 2)
        lbl_hb = QLabel("● HUB TCP: ACTIVO")
        lbl_hb.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: bold;")
        lay_h.addWidget(lbl_hb)
        header.addWidget(pill_hb)

        self.btn_toggle_right = QPushButton("Detalles ▶")
        self.btn_toggle_right.setToolTip("Ocultar/Mostrar detalles (F3)")
        self.btn_toggle_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_right.setStyleSheet(
            "background-color: #111726; color: #94a3b8; border: 1px solid #1e293b; "
            "border-radius: 6px; padding: 6px 10px; font-weight: bold; font-size: 11px;"
        )
        self.btn_toggle_right.clicked.connect(self._toggle_inspector)
        header.addWidget(self.btn_toggle_right)

        return header

    def _reconstruir_tabs_labs(self) -> None:
        while self.tabs_box.count():
            item = self.tabs_box.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        self.btns_tabs.clear()

        for i, lab_nombre in enumerate(self.datos_laboratorios.keys()):
            btn = QPushButton(lab_nombre)
            btn.setProperty("class", "tab-lab")
            btn.setProperty("active", "true" if i == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(partial(self._cambiar_lab, lab_nombre, btn))
            self.tabs_box.addWidget(btn)
            self.btns_tabs[lab_nombre] = btn

    def _construir_vistas_laboratorios(self) -> None:
        while self.stacked_labs.count():
            w = self.stacked_labs.widget(0)
            if w is not None:
                self.stacked_labs.removeWidget(w)
                w.deleteLater()
        self.tarjetas_map.clear()

        for lab_nombre, filas in self.datos_laboratorios.items():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")

            contenedor_lab = QWidget()
            layout_filas = QVBoxLayout(contenedor_lab)
            layout_filas.setSpacing(12)
            layout_filas.setContentsMargins(0, 0, 8, 0)

            for fila_nombre, pcs in filas.items():
                fila_box = QFrame()
                fila_box.setObjectName("FilaContainer")
                fila_layout = QHBoxLayout(fila_box)
                fila_layout.setContentsMargins(12, 10, 12, 10)
                fila_layout.setSpacing(10)

                lbl_fila = QLabel(fila_nombre.upper())
                lbl_fila.setFixedWidth(58)
                lbl_fila.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                lbl_fila.setStyleSheet("color: #64748b;")
                fila_layout.addWidget(lbl_fila)

                for pc_id in pcs:
                    tarjeta = TarjetaPC(pc_id, fila_nombre, lab_nombre)
                    tarjeta.click_pc.connect(self._al_seleccionar_pc)
                    fila_layout.addWidget(tarjeta)
                    self.tarjetas_map[pc_id] = tarjeta

                fila_layout.addStretch()
                layout_filas.addWidget(fila_box)

            layout_filas.addStretch()
            scroll.setWidget(contenedor_lab)
            self.stacked_labs.addWidget(scroll)

    def _crear_panel_inspector(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Inspector")
        panel.setMinimumWidth(290)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        titulo = QLabel("DETALLES DEL EQUIPO:")
        titulo.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        titulo.setStyleSheet("color: #00e5ff; letter-spacing: 0.5px;")
        layout.addWidget(titulo)

        self.lbl_insp_id = QLabel("Selecciona una estación")
        self.lbl_insp_id.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(self.lbl_insp_id)

        self.lbl_insp_os = QLabel("Agente OS: -")
        self.lbl_insp_ubi = QLabel("Ubicación: -")
        self.lbl_insp_perif = QLabel("Periféricos USB: -")
        self.lbl_insp_status = QLabel("Nivel de Seguridad: -")

        for l in (self.lbl_insp_os, self.lbl_insp_ubi, self.lbl_insp_perif, self.lbl_insp_status):
            l.setStyleSheet("color: #cbd5e1; font-size: 12px;")
            layout.addWidget(l)

        self.box_wmi = QFrame()
        self.box_wmi.setObjectName("WMIBox")
        lay_wmi = QVBoxLayout(self.box_wmi)
        self.lbl_wmi_evento = QLabel("Monitor Hub: Escuchando eventos de agentes...")
        self.lbl_wmi_evento.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;")
        self.lbl_wmi_evento.setWordWrap(True)
        lay_wmi.addWidget(self.lbl_wmi_evento)
        layout.addWidget(self.box_wmi)

        layout.addSpacing(4)
        lbl_notif_title = QLabel("DESPACHO DE ALERTAS (ALERT_MANAGER):")
        lbl_notif_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: bold;")
        layout.addWidget(lbl_notif_title)

        self.badge_telegram = QLabel("  Bot Telegram: VERIFICANDO...")
        self.badge_telegram.setStyleSheet("background-color: #111624; color: #64748b; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.badge_telegram)

        self.badge_email = QLabel("  Correo SMTP: VERIFICANDO...")
        self.badge_email.setStyleSheet("background-color: #111624; color: #64748b; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.badge_email)

        layout.addStretch()

        self.btn_desactivar = QPushButton("Reconocer y Silenciar Alarma")
        self.btn_desactivar.setStyleSheet(
            "background-color: #be123c; color: white; font-weight: bold; padding: 9px; border-radius: 6px;"
        )
        self.btn_desactivar.setEnabled(False)
        self.btn_desactivar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_desactivar.clicked.connect(self._desactivar_alerta_actual)
        layout.addWidget(self.btn_desactivar)

        self.btn_simular = QPushButton("Simular Extracción USB (PC-04)")
        self.btn_simular.setStyleSheet(
            "background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7; padding: 8px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_simular.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_simular.clicked.connect(
            lambda: self.hub_thread.simular_evento_local(
                "PC-04", "Teclado USB HID", "remove", "USB\\VID_046D&PID_C31C"
            )
        )
        layout.addWidget(self.btn_simular)

        return panel

    def _crear_consola_logs(self) -> QTextEdit:
        self.console = QTextEdit()
        self.console.setObjectName("ConsoleLogs")
        self.console.setReadOnly(True)
        self.agregar_log(
            f"SAPPHIRE SOC inicializado por operador '{self.usuario_actual}'. "
            "Atajos: [F2] Ocultar Menú | [F3] Ocultar Detalles."
        )
        return self.console

    def _crear_vista_eventos(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl = QLabel("Registro Forense de Incidentes (Sincronizado con alerts.log)")
        lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #00e5ff;")
        layout.addWidget(lbl)

        self.tabla_eventos = QTableWidget(0, 6)
        self.tabla_eventos.setHorizontalHeaderLabels([
            "Timestamp", "Nodo / PC", "Sala", "Acción", "Dispositivo / sys_name", "Estado / Operador"
        ])
        header = self.tabla_eventos.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_eventos.setAlternatingRowColors(True)
        self.tabla_eventos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla_eventos)

        return page

    def _crear_vista_red(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        top = QHBoxLayout()
        lbl = QLabel("Estado de Enlace de Agentes (pc_monitoring)")
        lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #00e5ff;")
        top.addWidget(lbl)
        top.addStretch()

        btn_sim_timeout = QPushButton("Simular Corte de Red (PC-02)")
        btn_sim_timeout.setStyleSheet(
            "background-color: #d97706; color: white; padding: 7px 14px; border-radius: 5px; font-weight: bold;"
        )
        btn_sim_timeout.clicked.connect(partial(self._cambiar_estado_timeout, "PC-02"))
        top.addWidget(btn_sim_timeout)
        layout.addLayout(top)

        self.tabla_red = QTableWidget(0, 5)
        self.tabla_red.setHorizontalHeaderLabels([
            "Estación", "Laboratorio", "Fila", "Transporte", "Estado del Enlace"
        ])
        header = self.tabla_red.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_red.setAlternatingRowColors(True)
        self.tabla_red.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla_red)

        self._poblar_tabla_red()
        return page

    def _poblar_tabla_red(self) -> None:
        self.tabla_red.setRowCount(0)
        for idx, (pc_id, tarjeta) in enumerate(self.tarjetas_map.items()):
            self.tabla_red.insertRow(idx)
            self.tabla_red.setItem(idx, 0, QTableWidgetItem(pc_id))
            self.tabla_red.setItem(idx, 1, QTableWidgetItem(tarjeta.lab_nombre))
            self.tabla_red.setItem(idx, 2, QTableWidgetItem(tarjeta.fila))
            self.tabla_red.setItem(idx, 3, QTableWidgetItem("TCP Socket (Hub)"))
            estado_item = QTableWidgetItem("ONLINE (Protegido)" if tarjeta.estado == "OK" else tarjeta.estado)
            estado_item.setForeground(QColor("#10b981" if tarjeta.estado == "OK" else "#f59e0b"))
            self.tabla_red.setItem(idx, 4, estado_item)

    def _crear_vista_config(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        lbl = QLabel("Configuración de Seguridad y Cuentas de Operador")
        lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #00e5ff;")
        layout.addWidget(lbl)

        card_admin = QFrame()
        card_admin.setObjectName("Inspector")
        card_admin.setMaximumWidth(480)
        lay_a = QVBoxLayout(card_admin)
        lay_a.setContentsMargins(18, 18, 18, 18)
        lay_a.setSpacing(10)

        lbl_alta = QLabel("Dar de Alta Nuevo Operador / Administrador")
        lbl_alta.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lay_a.addWidget(lbl_alta)

        self.cfg_new_user = QLineEdit()
        self.cfg_new_user.setPlaceholderText("Nombre del nuevo usuario")
        lay_a.addWidget(self.cfg_new_user)

        self.cfg_new_pass = QLineEdit()
        self.cfg_new_pass.setPlaceholderText("Contraseña (mínimo 6 caracteres)")
        self.cfg_new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        lay_a.addWidget(self.cfg_new_pass)

        btn_crear_op = QPushButton("Registrar Operador Autorizado")
        btn_crear_op.setStyleSheet(
            "background-color: #0284c7; color: white; padding: 9px; border-radius: 5px; font-weight: bold;"
        )
        btn_crear_op.clicked.connect(self._registrar_operador_desde_cfg)
        lay_a.addWidget(btn_crear_op)

        layout.addWidget(card_admin)
        layout.addStretch()
        return page

    def _registrar_operador_desde_cfg(self) -> None:
        u = self.cfg_new_user.text().strip()
        p = self.cfg_new_pass.text().strip()
        if len(u) < 3 or len(p) < 6:
            QMessageBox.warning(self, "Datos inválidos", "El usuario requiere mínimo 3 caracteres y la contraseña 6.")
            return
        with open(RUTA_USUARIOS, "r", encoding="utf-8") as f:
            usuarios = json.load(f)
        if u in usuarios:
            QMessageBox.warning(self, "Duplicado", "Ese operador ya existe.")
            return
        usuarios[u] = hash_password(p)
        with open(RUTA_USUARIOS, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4)
        self.cfg_new_user.clear()
        self.cfg_new_pass.clear()
        self.agregar_log(f"Nuevo operador '{u}' dado de alta por '{self.usuario_actual}'.")
        QMessageBox.information(self, "Operador Creado", f"Cuenta '{u}' registrada correctamente.")

    # =========================================================================
    # INTEGRACIÓN CON HUB SERVER Y ALERT_MANAGER DE TU COLABORADOR
    # =========================================================================
    def _cargar_logs_previos(self) -> None:
        if DEFAULT_LOG_PATH.exists():
            try:
                with open(DEFAULT_LOG_PATH, "r", encoding="utf-8") as f:
                    ultimas_lineas = [line.strip() for line in f.readlines() if line.strip()][-8:]
                if ultimas_lineas:
                    self.agregar_log("<b>--- Últimos eventos en monitoring_system-main/logs/alerts.log ---</b>")
                    for linea in ultimas_lineas:
                        self.console.append(f"<span style='color:#94a3b8;'>{linea}</span>")
            except Exception:
                pass

    def _actualizar_estado_canales(self, tiene_tg: bool, tiene_smtp: bool) -> None:
        self.tiene_tg_configurado = tiene_tg
        self.tiene_smtp_configurado = tiene_smtp
        txt_tg = "LISTO (.env)" if tiene_tg else "SIN CONFIGURAR (.env)"
        txt_smtp = "LISTO (.env)" if tiene_smtp else "SIN CONFIGURAR (.env)"
        self.badge_telegram.setText(f"  Bot Telegram: {txt_tg}")
        self.badge_email.setText(f"  Correo SMTP: {txt_smtp}")

    def _procesar_reporte_hub(self, report: dict) -> None:
        pc_id = str(report.get("pc_name", "DESCONOCIDO")).strip().upper()
        device_name = str(report.get("device_name", "Periférico"))
        action = str(report.get("action", "change")).lower()
        sys_name = str(report.get("sys_name", "-"))

        detalle = f"[{action.upper()}] {device_name} ({sys_name})"

        if action == "remove":
            self.reportar_evento_alerta(pc_id, f"Action:{action}", detalle)
            if pc_id not in self.tarjetas_map:
                self.agregar_log(
                    f"<span style='color:#f59e0b;'>Aviso: '{pc_id}' reportó extracción pero no está en el mapa actual (agrégalo en Salas).</span>"
                )
        else:
            self.agregar_log(
                f"<span style='color:#10b981;'>[EVENTO {action.upper()} en {pc_id}]</span> {device_name} ({sys_name})"
            )
            tarjeta = self.tarjetas_map.get(pc_id)
            lab_nombre = tarjeta.lab_nombre if tarjeta else "Sala Externa"
            fila_idx = self.tabla_eventos.rowCount()
            self.tabla_eventos.insertRow(fila_idx)
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for col, val in enumerate([ahora, pc_id, lab_nombre, action.upper(), f"{device_name} ({sys_name})", "CONECTADO"]):
                item = QTableWidgetItem(val)
                if col == 5:
                    item.setForeground(QColor("#10b981"))
                self.tabla_eventos.setItem(fila_idx, col, item)

    def _mostrar_resultado_alert_manager(self, pc_id: str, entregado: bool) -> None:
        color = "#10b981" if entregado else "#f43f5e"
        estado_txt = "ENVIADO [✓]" if entregado else "ERROR [✗]"

        if self.tiene_tg_configurado:
            self.badge_telegram.setText(f"  Bot Telegram: {estado_txt}")
            self.badge_telegram.setStyleSheet(
                f"background-color: #111624; color: {color}; border-radius: 4px; padding: 6px; font-weight: bold;"
            )
        if self.tiene_smtp_configurado:
            self.badge_email.setText(f"  Correo SMTP: {estado_txt}")
            self.badge_email.setStyleSheet(
                f"background-color: #111624; color: {color}; border-radius: 4px; padding: 6px; font-weight: bold;"
            )

        self.agregar_log(
            f"AlertManager registró el incidente de <b>{pc_id}</b> en <i>alerts.log</i>."
        )

    def _abrir_admin_labs(self) -> None:
        dlg = DialogoAdminLabs(self.datos_laboratorios, self)
        dlg.exec()
        if dlg.cambios_realizados:
            pcs_validas = {
                pc
                for filas in self.datos_laboratorios.values()
                for lista in filas.values()
                for pc in lista
            }
            self.pcs_en_alerta.intersection_update(pcs_validas)

            self._reconstruir_tabs_labs()
            self._construir_vistas_laboratorios()
            self._poblar_tabla_red()
            self._actualizar_contadores_kpi()
            self.agregar_log("Topología de Salas, Filas y PCs actualizada en laboratorios.json.")

    def agregar_log(self, mensaje: str) -> None:
        ahora = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"<span style='color:#64748b;'>[{ahora}]</span> {mensaje}")

    def _actualizar_contadores_kpi(self) -> None:
        total = len(self.tarjetas_map)
        alertas = len(self.pcs_en_alerta)
        seguros = total - alertas
        self.lbl_kpi_nodos.setText(f"ACTIVOS: {seguros} OK | {alertas} ALERTA")

    def _cambiar_lab(self, nombre_lab: str, boton_presionado: QPushButton) -> None:
        for boton in self.btns_tabs.values():
            boton.setProperty("active", "false")
            st = boton.style()
            if st is not None:
                st.unpolish(boton)
                st.polish(boton)

        boton_presionado.setProperty("active", "true")
        st_btn = boton_presionado.style()
        if st_btn is not None:
            st_btn.unpolish(boton_presionado)
            st_btn.polish(boton_presionado)

        nombres = list(self.datos_laboratorios.keys())
        if nombre_lab in nombres:
            self.stacked_labs.setCurrentIndex(nombres.index(nombre_lab))

    def _al_seleccionar_pc(self, pc_id: str) -> None:
        self.pc_seleccionada = pc_id
        tarjeta = self.tarjetas_map.get(pc_id)
        if tarjeta is None:
            return

        if hasattr(self, "inspector_widget") and not self.inspector_widget.isVisible():
            self._toggle_inspector()

        self.lbl_insp_id.setText(f"{pc_id} ({tarjeta.lab_nombre})")
        self.lbl_insp_os.setText("Agente OS: Windows / Linux (pc_monitoring)")
        self.lbl_insp_ubi.setText(f"Ubicación: {tarjeta.lab_nombre} • {tarjeta.fila}")
        self.lbl_insp_perif.setText("Periféricos vigilados: Teclado, Mouse, Monitor")

        if tarjeta.estado == "ALERTA":
            self.lbl_insp_status.setText("Nivel de Seguridad: INTRUSIÓN FÍSICA")
            self.lbl_insp_status.setStyleSheet("color: #f43f5e; font-weight: bold;")
            self.btn_desactivar.setEnabled(True)
        elif tarjeta.estado == "TIMEOUT":
            self.lbl_insp_status.setText("Nivel de Seguridad: SIN TELEMETRÍA (OFFLINE)")
            self.lbl_insp_status.setStyleSheet("color: #f59e0b; font-weight: bold;")
            self.btn_desactivar.setEnabled(True)
        else:
            self.lbl_insp_status.setText("Nivel de Seguridad: ARMADO Y VERIFICADO")
            self.lbl_insp_status.setStyleSheet("color: #10b981; font-weight: bold;")
            self.btn_desactivar.setEnabled(False)

    def _cambiar_estado_timeout(self, pc_id: str) -> None:
        tarjeta = self.tarjetas_map.get(pc_id)
        if tarjeta:
            tarjeta.set_estado("TIMEOUT", "Pérdida de enlace TCP con el agente")
            self._poblar_tabla_red()
            self.agregar_log(f"<span style='color:#f59e0b;'>ADVERTENCIA: {pc_id} perdió conexión con el Hub.</span>")

    def reportar_evento_alerta(self, pc_id: str, clase_wmi: str, detalle: str) -> None:
        self.pcs_en_alerta.add(pc_id)
        tarjeta = self.tarjetas_map.get(pc_id)
        lab_nombre = tarjeta.lab_nombre if tarjeta else "Sala Externa"

        if tarjeta is not None:
            tarjeta.set_estado("ALERTA", detalle)

        self.lbl_kpi_alerta.setText("● PERÍMETRO: ALERTA CRÍTICA")
        self.lbl_kpi_alerta.setStyleSheet("color: #f43f5e; font-weight: bold;")
        self._actualizar_contadores_kpi()
        self._al_seleccionar_pc(pc_id)

        self.lbl_wmi_evento.setText(
            f"[ALERTA HUB]\nNodo: {pc_id}\nEvento: {detalle}"
        )
        self.lbl_wmi_evento.setStyleSheet("color: #fda4af; font-size: 11px; font-family: 'Consolas', monospace;")

        fila_idx = self.tabla_eventos.rowCount()
        self.tabla_eventos.insertRow(fila_idx)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for col, val in enumerate([ahora, pc_id, lab_nombre, clase_wmi, detalle, "ACTIVA"]):
            item = QTableWidgetItem(val)
            if col == 5:
                item.setForeground(QColor("#f43f5e"))
            self.tabla_eventos.setItem(fila_idx, col, item)

        self._poblar_tabla_red()

    def _desactivar_alerta_actual(self) -> None:
        pc_id = self.pc_seleccionada
        if pc_id is None:
            return

        self.pcs_en_alerta.discard(pc_id)
        tarjeta = self.tarjetas_map.get(pc_id)
        if tarjeta is not None:
            tarjeta.set_estado("OK", f"Restablecido por {self.usuario_actual}")
        self._al_seleccionar_pc(pc_id)
        self._actualizar_contadores_kpi()
        self._poblar_tabla_red()

        if not self.pcs_en_alerta:
            self.lbl_kpi_alerta.setText("● PERÍMETRO: SEGURO")
            self.lbl_kpi_alerta.setStyleSheet("color: #10b981; font-weight: bold;")
            self.lbl_wmi_evento.setText("Monitor Hub: Escuchando eventos de agentes...")
            self.lbl_wmi_evento.setStyleSheet("color: #94a3b8; font-size: 11px; font-family: 'Consolas', monospace;")

        for row in range(self.tabla_eventos.rowCount()):
            item_pc = self.tabla_eventos.item(row, 1)
            item_est = self.tabla_eventos.item(row, 5)
            if item_pc and item_est and item_pc.text() == pc_id and item_est.text() == "ACTIVA":
                item_res = QTableWidgetItem(f"SILENCIADA ({self.usuario_actual})")
                item_res.setForeground(QColor("#10b981"))
                self.tabla_eventos.setItem(row, 5, item_res)

        self.agregar_log(
            f"<span style='color:#10b981;'>Alarma reconocida y restablecida en {pc_id} por '{self.usuario_actual}'.</span>"
        )

    def _toggle_parpadeo(self) -> None:
        if not self.pcs_en_alerta:
            return

        self.fase_parpadeo = not self.fase_parpadeo
        for pc_id in list(self.pcs_en_alerta):
            tarjeta = self.tarjetas_map.get(pc_id)
            if tarjeta is not None:
                tarjeta.set_parpadeo(self.fase_parpadeo)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "hub_thread"):
            self.hub_thread.detener()
        super().closeEvent(a0)