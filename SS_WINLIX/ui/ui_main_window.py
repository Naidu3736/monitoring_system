import json
from functools import partial
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QTextEdit,
    QStackedWidget, QButtonGroup, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QColor, QCloseEvent

from ui.card_pc import TarjetaPC
from ui.config_view import VistaConfiguracion
from ui.login import VistaLogin, repolir_widget
from services.hub_bridge import HubServerThread, DEFAULT_LOG_PATH

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_PREFERENCIAS = BASE_DIR / "config" / "preferencias.json"


class DashboardPrincipal(QMainWindow):
    def __init__(self, usuario_actual: str | None = None) -> None:
        super().__init__()
        self.usuario_actual: str = usuario_actual or ""
        self.tema_actual: str = self._cargar_tema_preferido()
        self.setWindowTitle("SAPPHIRE SOC — Autenticación de Seguridad (BUAP)")
        self.resize(1360, 780)
        self.setMinimumSize(1024, 640)

        self.datos_laboratorios: dict[str, dict[str, list[str]]] = {}
        self.tarjetas_map: dict[str, TarjetaPC] = {}
        self.btns_tabs: dict[str, QPushButton] = {}
        self.peers_por_pc: dict[str, str] = {}
        self.conexiones_activas: int = 0
        self.pc_seleccionada: str | None = None
        self.pcs_en_alerta: set[str] = set()
        self.fase_parpadeo: bool = False
        self.tiene_tg_configurado: bool = False
        self.tiene_smtp_configurado: bool = False
        self._sesion_activa: bool = False
        self.hub_thread: HubServerThread | None = None
        self.dashboard_root: QWidget | None = None

        # Stack principal: 0 = Pantalla de Login integrada, 1 = Dashboard
        self.app_stack = QStackedWidget()
        self.vista_login = VistaLogin(self)
        self.vista_login.autenticado.connect(self._al_iniciar_sesion)
        self.app_stack.addWidget(self.vista_login)
        self.setCentralWidget(self.app_stack)

        self.cargar_estilos()

        # Atajos globales: F2 (Menú Izquierdo), F3 (Detalles Derecho), F5 (Estilos)
        self.shortcut_sidebar = QShortcut(QKeySequence("F2"), self)
        self.shortcut_sidebar.activated.connect(self._toggle_sidebar)

        self.shortcut_inspector = QShortcut(QKeySequence("F3"), self)
        self.shortcut_inspector.activated.connect(self._toggle_inspector)

        self.shortcut_reload = QShortcut(QKeySequence("F5"), self)
        self.shortcut_reload.activated.connect(self.cargar_estilos)

        self.timer_parpadeo = QTimer(self)
        self.timer_parpadeo.timeout.connect(self._toggle_parpadeo)

        if usuario_actual:
            self._al_iniciar_sesion(usuario_actual)
        else:
            self.vista_login.reiniciar_formulario()

    # =========================================================================
    # GESTIÓN DE TEMAS (OSCURO NEUTRO / CLARO NEUTRO)
    # =========================================================================
    def _cargar_tema_preferido(self) -> str:
        if RUTA_PREFERENCIAS.exists():
            try:
                with open(RUTA_PREFERENCIAS, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tema = str(data.get("tema", "dark")).strip().lower()
                if tema in ("dark", "light"):
                    return tema
            except Exception:
                pass
        return "dark"

    def _guardar_tema_preferido(self) -> None:
        RUTA_PREFERENCIAS.parent.mkdir(parents=True, exist_ok=True)
        with open(RUTA_PREFERENCIAS, "w", encoding="utf-8") as f:
            json.dump({"tema": self.tema_actual}, f, indent=4)

    def _establecer_tema(self, nuevo_tema: str) -> None:
        if nuevo_tema not in ("dark", "light") or nuevo_tema == self.tema_actual:
            return
        self.tema_actual = nuevo_tema
        self._guardar_tema_preferido()
        self.cargar_estilos()
        if self._sesion_activa:
            for tarjeta in self.tarjetas_map.values():
                tarjeta.set_tema(self.tema_actual)
            self._poblar_tabla_red()
            self.vista_config.actualizar_estado_tema(self.tema_actual)

    def _color_semantica(self, tipo: str) -> str:
        oscuro = self.tema_actual == "dark"
        paleta = {
            "ok": "#34d399" if oscuro else "#059669",
            "alert": "#fb7185" if oscuro else "#be123c",
            "warn": "#fbbf24" if oscuro else "#b45309",
            "muted": "#a1a1aa" if oscuro else "#52525b",
            "dim": "#71717a" if oscuro else "#71717a",
        }
        return paleta.get(tipo, paleta["muted"])

    def cargar_estilos(self) -> None:
        archivo = "styles.css" if self.tema_actual == "dark" else "styles_light.css"
        ruta_estilos = BASE_DIR / "assets" / archivo
        if ruta_estilos.exists():
            with open(ruta_estilos, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

        if self._sesion_activa and hasattr(self, "console"):
            etiqueta = "oscuro" if self.tema_actual == "dark" else "claro"
            self.agregar_log(f"Tema visual aplicado: modo {etiqueta} ({archivo}).")

    # =========================================================================
    # CICLO DE SESIÓN (LOGIN INTEGRADO ↔ DASHBOARD)
    # =========================================================================
    def _al_iniciar_sesion(self, usuario: str) -> None:
        self.usuario_actual = usuario
        self._sesion_activa = True
        self.setWindowTitle(
            f"Monitoreo de Seguridad de Hardware (BUAP) - Operador: {self.usuario_actual}"
        )

        if self.dashboard_root is not None:
            self.app_stack.removeWidget(self.dashboard_root)
            self.dashboard_root.deleteLater()
            self.dashboard_root = None

        self.datos_laboratorios = self._cargar_config_laboratorios()
        self.tarjetas_map = {}
        self.btns_tabs = {}
        self.peers_por_pc = {}
        self.conexiones_activas = 0
        self.pc_seleccionada = None
        self.pcs_en_alerta = set()
        self.fase_parpadeo = False

        self.dashboard_root = self._armar_interfaz()
        self.app_stack.addWidget(self.dashboard_root)
        self.app_stack.setCurrentWidget(self.dashboard_root)
        self._actualizar_contadores_kpi()

        self.timer_parpadeo.start(450)

        # Arrancar el Hub Server real en segundo plano
        self.hub_thread = HubServerThread()
        self.vista_config.hub_thread = self.hub_thread
        self.hub_thread.log_signal.connect(self.agregar_log)
        self.hub_thread.canales_configurados.connect(self._actualizar_estado_canales)
        self.hub_thread.hub_estado_cambiado.connect(self._actualizar_estado_hub)
        self.hub_thread.agente_conectado.connect(self._al_conectar_agente)
        self.hub_thread.agente_desconectado.connect(self._al_desconectar_agente)
        self.hub_thread.reporte_recibido.connect(self._procesar_reporte_hub)
        self.hub_thread.alerta_procesada.connect(self._mostrar_resultado_alert_manager)
        self.hub_thread.start()

        self._cargar_logs_previos()

    def _cerrar_sesion(self) -> None:
        self.timer_parpadeo.stop()
        if self.hub_thread is not None:
            self.hub_thread.detener()
            self.hub_thread = None

        self._sesion_activa = False
        self.usuario_actual = ""
        self.setWindowTitle("SAPPHIRE SOC — Autenticación de Seguridad (BUAP)")
        self.app_stack.setCurrentWidget(self.vista_login)
        self.vista_login.reiniciar_formulario()

        if self.dashboard_root is not None:
            self.app_stack.removeWidget(self.dashboard_root)
            self.dashboard_root.deleteLater()
            self.dashboard_root = None

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

    # =========================================================================
    # CONSTRUCCIÓN DEL DASHBOARD
    # =========================================================================
    def _armar_interfaz(self) -> QWidget:
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
        return root

    def _crear_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(235)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 18)
        layout.setSpacing(6)

        lbl_logo = QLabel("SAPPHIRE SOC")
        lbl_logo.setProperty("class", "sidebar-logo")
        lbl_sub = QLabel("FCC - Seguridad de Hardware BUAP")
        lbl_sub.setProperty("class", "sidebar-sub")

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

        layout.addStretch()

        box_user = QFrame()
        box_user.setObjectName("UserBox")
        lay_u = QVBoxLayout(box_user)
        lay_u.setContentsMargins(10, 10, 10, 10)
        lay_u.setSpacing(7)

        lbl_op = QLabel(f"Operador: {self.usuario_actual.upper()}")
        lbl_op.setProperty("class", "user-op")
        lbl_buap = QLabel("Protección de Hardware BUAP")
        lbl_buap.setProperty("class", "user-sub")
        lay_u.addWidget(lbl_op)
        lay_u.addWidget(lbl_buap)

        btn_logout = QPushButton("Cerrar sesión")
        btn_logout.setProperty("class", "btn-secondary")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._cerrar_sesion)
        lay_u.addWidget(btn_logout)

        layout.addWidget(box_user)

        return sidebar

    def _toggle_sidebar(self) -> None:
        if not self._sesion_activa:
            return
        visible = not self.sidebar_widget.isVisible()
        self.sidebar_widget.setVisible(visible)
        self.btn_toggle_left.setText("☰" if not visible else "◀ Menú")

    def _toggle_inspector(self) -> None:
        if not self._sesion_activa:
            return
        visible = not self.inspector_widget.isVisible()
        self.inspector_widget.setVisible(visible)
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
        self.btn_toggle_left.setProperty("class", "btn-secondary")
        self.btn_toggle_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_left.clicked.connect(self._toggle_sidebar)
        header.addWidget(self.btn_toggle_left)

        self.tabs_box = QHBoxLayout()
        self.tabs_box.setSpacing(8)
        self._reconstruir_tabs_labs()
        header.addLayout(self.tabs_box)

        btn_quick_lab = QPushButton("+ Salas")
        btn_quick_lab.setToolTip("Ir a Configuración → Salas y Equipos")
        btn_quick_lab.setProperty("class", "btn-quick-lab")
        btn_quick_lab.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quick_lab.clicked.connect(self._ir_a_config_topologia)
        header.addWidget(btn_quick_lab)

        header.addStretch()

        pill_nodes = QFrame()
        pill_nodes.setProperty("class", "kpi-pill")
        lay_n = QHBoxLayout(pill_nodes)
        lay_n.setContentsMargins(8, 2, 8, 2)
        self.lbl_kpi_nodos = QLabel("ACTIVOS: 0 OK | 0 ALERTA")
        self.lbl_kpi_nodos.setProperty("class", "kpi-text")
        lay_n.addWidget(self.lbl_kpi_nodos)
        header.addWidget(pill_nodes)

        pill_status = QFrame()
        pill_status.setProperty("class", "kpi-pill")
        lay_s = QHBoxLayout(pill_status)
        lay_s.setContentsMargins(8, 2, 8, 2)
        self.lbl_kpi_alerta = QLabel("● PERÍMETRO: SEGURO")
        self.lbl_kpi_alerta.setProperty("class", "kpi-text")
        self.lbl_kpi_alerta.setProperty("state", "ok")
        lay_s.addWidget(self.lbl_kpi_alerta)
        header.addWidget(pill_status)

        pill_hb = QFrame()
        pill_hb.setProperty("class", "kpi-pill")
        lay_h = QHBoxLayout(pill_hb)
        lay_h.setContentsMargins(8, 2, 8, 2)
        self.lbl_hb = QLabel("● HUB TCP: INICIANDO...")
        self.lbl_hb.setProperty("class", "kpi-text")
        self.lbl_hb.setProperty("state", "active")
        lay_h.addWidget(self.lbl_hb)
        header.addWidget(pill_hb)

        self.btn_toggle_right = QPushButton("Detalles ▶")
        self.btn_toggle_right.setToolTip("Ocultar/Mostrar detalles (F3)")
        self.btn_toggle_right.setProperty("class", "btn-secondary")
        self.btn_toggle_right.setCursor(Qt.CursorShape.PointingHandCursor)
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

            contenedor_lab = QWidget()
            contenedor_lab.setObjectName("ScrollContent")
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
                lbl_fila.setProperty("class", "fila-label")
                fila_layout.addWidget(lbl_fila)

                for pc_id in pcs:
                    tarjeta = TarjetaPC(pc_id, fila_nombre, lab_nombre, tema=self.tema_actual)
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

        titulo = QLabel("DETALLES DEL EQUIPO")
        titulo.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        titulo.setProperty("class", "inspector-title")
        layout.addWidget(titulo)

        self.lbl_insp_id = QLabel("Selecciona una estación")
        self.lbl_insp_id.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_insp_id.setProperty("class", "inspector-id")
        layout.addWidget(self.lbl_insp_id)

        self.lbl_insp_os = QLabel("Agente: -")
        self.lbl_insp_ubi = QLabel("Ubicación: -")
        self.lbl_insp_perif = QLabel("Periféricos USB: -")
        self.lbl_insp_status = QLabel("Nivel de Seguridad: -")

        for l in (self.lbl_insp_os, self.lbl_insp_ubi, self.lbl_insp_perif):
            l.setProperty("class", "inspector-meta")
            layout.addWidget(l)

        self.lbl_insp_status.setProperty("class", "inspector-status")
        layout.addWidget(self.lbl_insp_status)

        self.box_wmi = QFrame()
        self.box_wmi.setObjectName("WMIBox")
        lay_wmi = QVBoxLayout(self.box_wmi)
        self.lbl_wmi_evento = QLabel("Monitor Hub: Escuchando eventos reales de agentes...")
        self.lbl_wmi_evento.setProperty("class", "wmi-text")
        self.lbl_wmi_evento.setProperty("state", "normal")
        self.lbl_wmi_evento.setWordWrap(True)
        lay_wmi.addWidget(self.lbl_wmi_evento)
        layout.addWidget(self.box_wmi)

        layout.addSpacing(4)
        lbl_notif_title = QLabel("DESPACHO DE ALERTAS (ALERT_MANAGER)")
        lbl_notif_title.setProperty("class", "inspector-section")
        layout.addWidget(lbl_notif_title)

        self.badge_telegram = QLabel("Bot Telegram: VERIFICANDO...")
        self.badge_telegram.setProperty("class", "channel-badge")
        self.badge_telegram.setProperty("state", "pending")
        layout.addWidget(self.badge_telegram)

        self.badge_email = QLabel("Correo SMTP: VERIFICANDO...")
        self.badge_email.setProperty("class", "channel-badge")
        self.badge_email.setProperty("state", "pending")
        layout.addWidget(self.badge_email)

        layout.addStretch()

        self.btn_desactivar = QPushButton("Reconocer y Silenciar Alarma")
        self.btn_desactivar.setProperty("class", "btn-danger")
        self.btn_desactivar.setEnabled(False)
        self.btn_desactivar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_desactivar.clicked.connect(self._desactivar_alerta_actual)
        layout.addWidget(self.btn_desactivar)

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
        lbl.setProperty("class", "page-title")
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
        lbl.setProperty("class", "page-title")
        top.addWidget(lbl)
        top.addStretch()

        self.lbl_conexiones_hub = QLabel("Sockets conectados al Hub: 0")
        self.lbl_conexiones_hub.setProperty("class", "status-pill")
        self.lbl_conexiones_hub.setProperty("state", "info")
        top.addWidget(self.lbl_conexiones_hub)
        layout.addLayout(top)

        self.tabla_red = QTableWidget(0, 5)
        self.tabla_red.setHorizontalHeaderLabels([
            "Estación", "Laboratorio", "Fila", "Enlace / Dirección", "Estado del Enlace"
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

            peer = self.peers_por_pc.get(pc_id)
            transporte = f"TCP ({peer})" if peer else "TCP Socket (en espera)"
            self.tabla_red.setItem(idx, 3, QTableWidgetItem(transporte))

            if tarjeta.estado == "ALERTA":
                estado_txt, tipo_color = "ALERTA ACTIVA", "alert"
            elif tarjeta.estado == "TIMEOUT":
                estado_txt, tipo_color = "DESCONECTADO", "warn"
            elif peer:
                estado_txt, tipo_color = "CONECTADO (Protegido)", "ok"
            else:
                estado_txt, tipo_color = "EN ESPERA DE AGENTE", "muted"

            estado_item = QTableWidgetItem(estado_txt)
            estado_item.setForeground(QColor(self._color_semantica(tipo_color)))
            self.tabla_red.setItem(idx, 4, estado_item)

    def _crear_vista_config(self) -> QWidget:
        self.vista_config = VistaConfiguracion(
            usuario_actual=self.usuario_actual,
            datos_laboratorios=self.datos_laboratorios,
            tema_actual=self.tema_actual,
            hub_thread=None,
            log_callback=self.agregar_log,
            parent=self,
        )
        self.vista_config.topologia_modificada.connect(self._sincronizar_topologia_ui)
        self.vista_config.tema_cambiado.connect(self._establecer_tema)
        return self.vista_config

    # =========================================================================
    # INTEGRACIÓN EN TIEMPO REAL CON HUB SERVER Y ALERT_MANAGER
    # =========================================================================
    def _cargar_logs_previos(self) -> None:
        if DEFAULT_LOG_PATH.exists():
            try:
                with open(DEFAULT_LOG_PATH, "r", encoding="utf-8") as f:
                    ultimas_lineas = [line.strip() for line in f.readlines() if line.strip()][-8:]
                if ultimas_lineas:
                    self.agregar_log("<b>--- Últimos eventos en monitoring_system-main/logs/alerts.log ---</b>")
                    c_muted = self._color_semantica("muted")
                    for linea in ultimas_lineas:
                        self.console.append(f"<span style='color:{c_muted};'>{linea}</span>")
            except Exception:
                pass

    def _actualizar_estado_hub(self, activo: bool, detalle: str) -> None:
        self.lbl_hb.setText(f"● HUB TCP: {detalle}")
        self.lbl_hb.setProperty("state", "ok" if activo else "error")
        repolir_widget(self.lbl_hb)

    def _al_conectar_agente(self, _peer: str) -> None:
        self.conexiones_activas += 1
        self.lbl_conexiones_hub.setText(f"Sockets conectados al Hub: {self.conexiones_activas}")

    def _al_desconectar_agente(self, pc_id: str, _peer: str) -> None:
        self.conexiones_activas = max(0, self.conexiones_activas - 1)
        self.lbl_conexiones_hub.setText(f"Sockets conectados al Hub: {self.conexiones_activas}")
        if pc_id:
            self.peers_por_pc.pop(pc_id, None)
            tarjeta = self.tarjetas_map.get(pc_id)
            if tarjeta is not None and tarjeta.estado != "ALERTA":
                tarjeta.set_estado("TIMEOUT", "Conexión TCP cerrada por el agente")
            self._poblar_tabla_red()

    def _actualizar_estado_canales(self, tiene_tg: bool, tiene_smtp: bool) -> None:
        self.tiene_tg_configurado = tiene_tg
        self.tiene_smtp_configurado = tiene_smtp
        txt_tg = "LISTO (.env)" if tiene_tg else "SIN CONFIGURAR (.env)"
        txt_smtp = "LISTO (.env)" if tiene_smtp else "SIN CONFIGURAR (.env)"
        self.badge_telegram.setText(f"Bot Telegram: {txt_tg}")
        self.badge_email.setText(f"Correo SMTP: {txt_smtp}")
        self.badge_telegram.setProperty("state", "ok" if tiene_tg else "pending")
        self.badge_email.setProperty("state", "ok" if tiene_smtp else "pending")
        repolir_widget(self.badge_telegram)
        repolir_widget(self.badge_email)
        self.vista_config.actualizar_estado_canales(tiene_tg, tiene_smtp)

    def _procesar_reporte_hub(self, report: dict) -> None:
        pc_id = str(report.get("pc_name", "DESCONOCIDO")).strip().upper()
        device_name = str(report.get("device_name", "Periférico"))
        action = str(report.get("action", "change")).lower()
        sys_name = str(report.get("sys_name", "-"))
        peer = str(report.get("peer", "")).strip()

        if peer:
            self.peers_por_pc[pc_id] = peer

        detalle = f"[{action.upper()}] {device_name} ({sys_name})"

        if action == "remove":
            self.reportar_evento_alerta(pc_id, f"Action:{action}", detalle)
            if pc_id not in self.tarjetas_map:
                c_warn = self._color_semantica("warn")
                self.agregar_log(
                    f"<span style='color:{c_warn};'>Aviso: '{pc_id}' reportó extracción pero no está en el mapa actual (agrégalo en Salas).</span>"
                )
        else:
            tarjeta = self.tarjetas_map.get(pc_id)
            if tarjeta is not None and tarjeta.estado == "TIMEOUT":
                tarjeta.set_estado("OK", detalle)
            c_ok = self._color_semantica("ok")
            self.agregar_log(
                f"<span style='color:{c_ok};'>[EVENTO {action.upper()} en {pc_id}]</span> {device_name} ({sys_name})"
            )
            lab_nombre = tarjeta.lab_nombre if tarjeta else "Sala Externa"
            fila_idx = self.tabla_eventos.rowCount()
            self.tabla_eventos.insertRow(fila_idx)
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for col, val in enumerate([ahora, pc_id, lab_nombre, action.upper(), f"{device_name} ({sys_name})", "CONECTADO"]):
                item = QTableWidgetItem(val)
                if col == 5:
                    item.setForeground(QColor(c_ok))
                self.tabla_eventos.setItem(fila_idx, col, item)
            self._poblar_tabla_red()

    def _mostrar_resultado_alert_manager(self, pc_id: str, entregado: bool) -> None:
        estado_prop = "ok" if entregado else "error"
        estado_txt = "ENVIADO [✓]" if entregado else "ERROR [✗]"

        if self.tiene_tg_configurado:
            self.badge_telegram.setText(f"Bot Telegram: {estado_txt}")
            self.badge_telegram.setProperty("state", estado_prop)
            repolir_widget(self.badge_telegram)
        if self.tiene_smtp_configurado:
            self.badge_email.setText(f"Correo SMTP: {estado_txt}")
            self.badge_email.setProperty("state", estado_prop)
            repolir_widget(self.badge_email)

        self.agregar_log(
            f"AlertManager registró el incidente de <b>{pc_id}</b> en <i>alerts.log</i>."
        )

    def _sincronizar_topologia_ui(self) -> None:
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

    def _ir_a_config_topologia(self) -> None:
        self.main_stack.setCurrentIndex(3)
        btn_cfg = self.nav_group.button(3)
        if btn_cfg is not None:
            btn_cfg.setChecked(True)
        self.vista_config.seleccionar_subpestana(0)

    def agregar_log(self, mensaje: str) -> None:
        ahora = datetime.now().strftime("%H:%M:%S")
        c_dim = self._color_semantica("dim")
        self.console.append(f"<span style='color:{c_dim};'>[{ahora}]</span> {mensaje}")

    def _actualizar_contadores_kpi(self) -> None:
        total = len(self.tarjetas_map)
        alertas = len(self.pcs_en_alerta)
        seguros = total - alertas
        self.lbl_kpi_nodos.setText(f"ACTIVOS: {seguros} OK | {alertas} ALERTA")

    def _cambiar_lab(self, nombre_lab: str, boton_presionado: QPushButton) -> None:
        for boton in self.btns_tabs.values():
            boton.setProperty("active", "false")
            repolir_widget(boton)

        boton_presionado.setProperty("active", "true")
        repolir_widget(boton_presionado)

        nombres = list(self.datos_laboratorios.keys())
        if nombre_lab in nombres:
            self.stacked_labs.setCurrentIndex(nombres.index(nombre_lab))

    def _al_seleccionar_pc(self, pc_id: str) -> None:
        self.pc_seleccionada = pc_id
        tarjeta = self.tarjetas_map.get(pc_id)
        if tarjeta is None:
            return

        if not self.inspector_widget.isVisible():
            self._toggle_inspector()

        peer = self.peers_por_pc.get(pc_id)
        self.lbl_insp_id.setText(f"{pc_id} ({tarjeta.lab_nombre})")
        self.lbl_insp_os.setText(
            f"Agente: pc_monitoring ({peer})" if peer else "Agente: pc_monitoring (en espera)"
        )
        self.lbl_insp_ubi.setText(f"Ubicación: {tarjeta.lab_nombre} • {tarjeta.fila}")
        self.lbl_insp_perif.setText("Periféricos vigilados: Teclado, Mouse, Monitor")

        if tarjeta.estado == "ALERTA":
            self.lbl_insp_status.setText("Nivel de Seguridad: INTRUSIÓN FÍSICA")
            self.lbl_insp_status.setProperty("state", "alert")
            self.btn_desactivar.setEnabled(True)
        elif tarjeta.estado == "TIMEOUT":
            self.lbl_insp_status.setText("Nivel de Seguridad: SIN TELEMETRÍA (OFFLINE)")
            self.lbl_insp_status.setProperty("state", "warn")
            self.btn_desactivar.setEnabled(True)
        else:
            self.lbl_insp_status.setText("Nivel de Seguridad: ARMADO Y VERIFICADO")
            self.lbl_insp_status.setProperty("state", "ok")
            self.btn_desactivar.setEnabled(False)
        repolir_widget(self.lbl_insp_status)

    def reportar_evento_alerta(self, pc_id: str, clase_wmi: str, detalle: str) -> None:
        self.pcs_en_alerta.add(pc_id)
        tarjeta = self.tarjetas_map.get(pc_id)
        lab_nombre = tarjeta.lab_nombre if tarjeta else "Sala Externa"

        if tarjeta is not None:
            tarjeta.set_estado("ALERTA", detalle)

        self.lbl_kpi_alerta.setText("● PERÍMETRO: ALERTA CRÍTICA")
        self.lbl_kpi_alerta.setProperty("state", "alert")
        repolir_widget(self.lbl_kpi_alerta)
        self._actualizar_contadores_kpi()
        self._al_seleccionar_pc(pc_id)

        self.lbl_wmi_evento.setText(
            f"[ALERTA HUB]\nNodo: {pc_id}\nEvento: {detalle}"
        )
        self.lbl_wmi_evento.setProperty("state", "alert")
        repolir_widget(self.lbl_wmi_evento)

        fila_idx = self.tabla_eventos.rowCount()
        self.tabla_eventos.insertRow(fila_idx)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c_alert = self._color_semantica("alert")
        for col, val in enumerate([ahora, pc_id, lab_nombre, clase_wmi, detalle, "ACTIVA"]):
            item = QTableWidgetItem(val)
            if col == 5:
                item.setForeground(QColor(c_alert))
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
            self.lbl_kpi_alerta.setProperty("state", "ok")
            repolir_widget(self.lbl_kpi_alerta)
            self.lbl_wmi_evento.setText("Monitor Hub: Escuchando eventos reales de agentes...")
            self.lbl_wmi_evento.setProperty("state", "normal")
            repolir_widget(self.lbl_wmi_evento)

        c_ok = self._color_semantica("ok")
        for row in range(self.tabla_eventos.rowCount()):
            item_pc = self.tabla_eventos.item(row, 1)
            item_est = self.tabla_eventos.item(row, 5)
            if item_pc and item_est and item_pc.text() == pc_id and item_est.text() == "ACTIVA":
                item_res = QTableWidgetItem(f"SILENCIADA ({self.usuario_actual})")
                item_res.setForeground(QColor(c_ok))
                self.tabla_eventos.setItem(row, 5, item_res)

        self.agregar_log(
            f"<span style='color:{c_ok};'>Alarma reconocida y restablecida en {pc_id} por '{self.usuario_actual}'.</span>"
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
        self.timer_parpadeo.stop()
        if self.hub_thread is not None:
            self.hub_thread.detener()
            self.hub_thread = None
        super().closeEvent(a0)
