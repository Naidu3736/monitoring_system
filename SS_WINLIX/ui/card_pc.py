from pathlib import Path
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

from ui.login import repolir_widget

BASE_DIR = Path(__file__).resolve().parent.parent


class TarjetaPC(QFrame):
    click_pc = pyqtSignal(str)

    def __init__(
        self,
        pc_id: str,
        fila: str,
        lab_nombre: str = "",
        tema: str = "dark",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pc_id = pc_id
        self.fila = fila
        self.lab_nombre = lab_nombre
        self.tema = tema
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

        # Barra superior: Fila y punto de estado
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        tag_fila = self.fila.upper().replace("FILA ", "F-")
        self.lbl_tag = QLabel(tag_fila)
        self.lbl_tag.setProperty("class", "pc-tag")

        self.indicador_punto = QLabel("●")
        self.indicador_punto.setProperty("class", "pc-dot")
        self.indicador_punto.setProperty("estado", "OK")

        top_row.addWidget(self.lbl_tag)
        top_row.addStretch()
        top_row.addWidget(self.indicador_punto)
        layout.addLayout(top_row)

        # Icono de estación (coloreado dinámicamente según tema)
        self.lbl_icono = QLabel()
        self.lbl_icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icono.setStyleSheet("background: transparent;")
        self._cargar_imagen_pc()
        layout.addWidget(self.lbl_icono)

        # Identificador del equipo
        self.lbl_id = QLabel(self.pc_id)
        self.lbl_id.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_id.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_id.setProperty("class", "pc-id")
        layout.addWidget(self.lbl_id)

        # Badge inferior de seguridad
        self.lbl_sub = QLabel("PROTEGIDO")
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sub.setProperty("class", "pc-sub")
        self.lbl_sub.setProperty("estado", "OK")
        layout.addWidget(self.lbl_sub)

        self.actualizar_tooltip()

    def set_tema(self, tema: str) -> None:
        self.tema = tema
        self._cargar_imagen_pc()
        self.actualizar_tooltip()

    def _cargar_imagen_pc(self) -> None:
        ruta_png = BASE_DIR / "resources" / "pc.png"
        if ruta_png.exists():
            base = QPixmap(str(ruta_png)).scaled(
                30, 30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            tinted = QPixmap(base.size())
            tinted.fill(Qt.GlobalColor.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, base)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            color_icono = QColor("#d4d4d8") if self.tema == "dark" else QColor("#27272a")
            painter.fillRect(tinted.rect(), color_icono)
            painter.end()
            self.lbl_icono.setPixmap(tinted)
        else:
            self.lbl_icono.setText("PC")
            self.lbl_icono.setProperty("class", "pc-id")

    def actualizar_tooltip(self) -> None:
        if self.tema == "dark":
            color_id = "#f4f4f5"
            color_meta = "#a1a1aa"
            color_ok, color_alert, color_warn = "#34d399", "#fb7185", "#fbbf24"
        else:
            color_id = "#18181b"
            color_meta = "#52525b"
            color_ok, color_alert, color_warn = "#059669", "#be123c", "#b45309"

        color_estado = (
            color_ok if self.estado == "OK"
            else (color_alert if self.estado == "ALERTA" else color_warn)
        )
        texto_estado = (
            "ARMADO / EN LÍNEA" if self.estado == "OK"
            else ("¡INTRUSIÓN FÍSICA DETECTADA!" if self.estado == "ALERTA" else "PÉRDIDA DE TELEMETRÍA")
        )

        html_tooltip = f"""
        <div style='line-height: 1.45;'>
            <b style='font-size: 13px; color: {color_id};'>{self.pc_id}</b>
            <span style='color: {color_meta};'>[{self.lab_nombre} - {self.fila}]</span><br>
            <b>Seguridad:</b> <span style='color: {color_estado}; font-weight: bold;'>{texto_estado}</span><br>
            <b>Agente:</b> pc_monitoring (Hub TCP)<br>
            <b>Último reporte:</b> {self.ultimo_evento}
        </div>
        """
        self.setToolTip(html_tooltip.strip())

    def mousePressEvent(self, a0) -> None:
        self.click_pc.emit(self.pc_id)
        super().mousePressEvent(a0)

    def set_parpadeo(self, activo: bool) -> None:
        self.setProperty("blink", "true" if activo else "false")
        repolir_widget(self)

    def set_estado(self, nuevo_estado: str, detalle: str = "Integridad de periféricos verificada") -> None:
        self.estado = nuevo_estado
        self.ultimo_evento = detalle
        self.setProperty("estado", nuevo_estado)
        self.setProperty("blink", "false")

        if nuevo_estado == "OK":
            self.indicador_punto.setText("●")
            self.lbl_sub.setText("PROTEGIDO")
        elif nuevo_estado == "ALERTA":
            self.indicador_punto.setText("▲")
            self.lbl_sub.setText("INTRUSIÓN")
        elif nuevo_estado == "TIMEOUT":
            self.indicador_punto.setText("■")
            self.lbl_sub.setText("SIN SEÑAL")

        self.indicador_punto.setProperty("estado", nuevo_estado)
        self.lbl_sub.setProperty("estado", nuevo_estado)
        repolir_widget(self.indicador_punto)
        repolir_widget(self.lbl_sub)

        self.actualizar_tooltip()
        repolir_widget(self)
