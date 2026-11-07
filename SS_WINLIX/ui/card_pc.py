from pathlib import Path
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

BASE_DIR = Path(__file__).resolve().parent.parent

class TarjetaPC(QFrame):
    click_pc = pyqtSignal(str)
    hover_pc = pyqtSignal(str)

    def __init__(self, pc_id, fila, lab_nombre="", parent=None):
        super().__init__(parent)
        self.pc_id = pc_id
        self.fila = fila
        self.lab_nombre = lab_nombre
        self.estado = "OK"
        self.ultimo_evento = "Integridad de periféricos verificada"

        self.setObjectName("PCCard")
        self.setFixedSize(108, 98)
        self.setProperty("estado", "OK")
        self.setProperty("blink", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Barra superior: Laboratorio  y estado
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        self.lbl_tag = QLabel(self.fila.replace("Fila ", "F-"))
        self.lbl_tag.setStyleSheet("color: #475569; font-size: 9px; font-weight: bold; background: transparent;")
        self.indicador_punto = QLabel("●")
        self.indicador_punto.setStyleSheet("color: #10b981; font-size: 11px; background: transparent;")
        top_row.addWidget(self.lbl_tag)
        top_row.addStretch()
        top_row.addWidget(self.indicador_punto)
        layout.addLayout(top_row)

        #   estación
        self.lbl_icono = QLabel()
        self.lbl_icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icono.setStyleSheet("background: transparent;")
        self._cargar_imagen_pc()
        layout.addWidget(self.lbl_icono)

        #  Identificador del equipo
        self.lbl_id = QLabel(self.pc_id)
        self.lbl_id.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_id.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_id.setStyleSheet("background: transparent; color: #f8fafc;")
        layout.addWidget(self.lbl_id)

        #  Badge inferior de seguridad
        self.lbl_sub = QLabel("PROTEGIDO")
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sub.setStyleSheet("color: #10b981; font-size: 9px; font-weight: bold; background: transparent;")
        layout.addWidget(self.lbl_sub)

        self.actualizar_tooltip()

    def _cargar_imagen_pc(self):
        ruta_png = BASE_DIR / "resources" / "pc.png"
        if ruta_png.exists():
            pixmap = QPixmap(str(ruta_png)).scaled(
                32, 32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_icono.setPixmap(pixmap)
        else:
            self.lbl_icono.setText("PC")
            self.lbl_icono.setStyleSheet("font-size: 20px; background: transparent;")

    def actualizar_tooltip(self):
        color_estado = "#10b981" if self.estado == "OK" else ("#f43f5e" if self.estado == "ALERTA" else "#f59e0b")
        texto_estado = "ARMADO / EN LÍNEA" if self.estado == "OK" else ("¡INTRUSIÓN FÍSICA DETECTADA!" if self.estado == "ALERTA" else "PÉRDIDA DE TELEMETRÍA")

        html_tooltip = f"""
        <div style='line-height: 1.45;'>
            <b style='font-size: 13px; color: #00e5ff;'>{self.pc_id}</b>
            <span style='color: #94a3b8;'>[{self.lab_nombre} - {self.fila}]</span><br>
            <b>Seguridad:</b> <span style='color: {color_estado}; font-weight: bold;'>{texto_estado}</span><br>
            <b>Agente WMI:</b> Activo (Ring-0 Hook)<br>
            <b>Último reporte:</b> {self.ultimo_evento}
        </div>
        """
        self.setToolTip(html_tooltip.strip())

    def enterEvent(self, event):
        self.hover_pc.emit(self.pc_id)
        super().enterEvent(event)

    def mousePressEvent(self, event):
        self.click_pc.emit(self.pc_id)
        super().mousePressEvent(event)

    def set_parpadeo(self, activo: bool):
        self.setProperty("blink", "true" if activo else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_estado(self, nuevo_estado, detalle="Integridad de periféricos verificada"):
        self.estado = nuevo_estado
        self.ultimo_evento = detalle
        self.setProperty("estado", nuevo_estado)
        self.setProperty("blink", "false")

        if nuevo_estado == "OK":
            self.indicador_punto.setText("●")
            self.indicador_punto.setStyleSheet("color: #10b981; font-size: 11px; background: transparent;")
            self.lbl_sub.setText("PROTEGIDO")
            self.lbl_sub.setStyleSheet("color: #10b981; font-size: 9px; font-weight: bold; background: transparent;")
        elif nuevo_estado == "ALERTA":
            self.indicador_punto.setText("▲")
            self.indicador_punto.setStyleSheet("color: #f43f5e; font-size: 11px; background: transparent;")
            self.lbl_sub.setText("INTRUSIÓN")
            self.lbl_sub.setStyleSheet("color: #f43f5e; font-weight: bold; font-size: 9px; background: transparent;")
        elif nuevo_estado == "TIMEOUT":
            self.indicador_punto.setText("■")
            self.indicador_punto.setStyleSheet("color: #f59e0b; font-size: 11px; background: transparent;")
            self.lbl_sub.setText("SIN SEÑAL")
            self.lbl_sub.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 9px; background: transparent;")

        self.actualizar_tooltip()
        self.style().unpolish(self)
        self.style().polish(self)