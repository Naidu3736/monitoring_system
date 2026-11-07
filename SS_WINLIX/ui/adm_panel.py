import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QMessageBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LABS = BASE_DIR / "config" / "laboratorios.json"


class DialogoAdminLabs(QDialog):
    def __init__(
        self,
        datos_laboratorios: dict[str, dict[str, list[str]]],
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestión de Topología: Salas, Filas y Equipos")
        self.setFixedSize(480, 560)
        self.datos = datos_laboratorios
        self.cambios_realizados = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        titulo = QLabel("Topología de Laboratorios y Nodos")
        titulo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        titulo.setStyleSheet("color: #00e5ff;")
        layout.addWidget(titulo)

        # =====================================================================
        # SECCIÓN 1: SALAS / LABORATORIOS
        # =====================================================================
        box_salas = self._crear_contenedor_seccion()
        lay_salas = QVBoxLayout(box_salas)
        lay_salas.setSpacing(8)

        lbl_s1 = QLabel("1. SALAS / LABORATORIOS")
        lbl_s1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        lay_salas.addWidget(lbl_s1)

        row_sel_lab = QHBoxLayout()
        self.combo_lab = QComboBox()
        self.combo_lab.currentTextChanged.connect(self._actualizar_filas)
        row_sel_lab.addWidget(self.combo_lab, stretch=3)

        btn_del_lab = QPushButton("Eliminar Sala")
        btn_del_lab.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_lab.setStyleSheet(
            "background-color: #881337; color: white; padding: 6px 10px; border-radius: 5px; font-weight: bold;"
        )
        btn_del_lab.clicked.connect(self._eliminar_sala)
        row_sel_lab.addWidget(btn_del_lab, stretch=1)
        lay_salas.addLayout(row_sel_lab)

        row_add_lab = QHBoxLayout()
        self.input_nuevo_lab = QLineEdit()
        self.input_nuevo_lab.setPlaceholderText("Nueva sala (ej. LABORATORIO 04)")
        row_add_lab.addWidget(self.input_nuevo_lab, stretch=3)

        btn_add_lab = QPushButton("Crear Sala")
        btn_add_lab.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_lab.setStyleSheet(
            "background-color: #0284c7; color: white; padding: 6px 10px; border-radius: 5px; font-weight: bold;"
        )
        btn_add_lab.clicked.connect(self._crear_sala)
        row_add_lab.addWidget(btn_add_lab, stretch=1)
        lay_salas.addLayout(row_add_lab)

        layout.addWidget(box_salas)

        # =====================================================================
        # SECCIÓN 2: FILAS DE LA SALA SELECCIONADA
        # =====================================================================
        box_filas = self._crear_contenedor_seccion()
        lay_filas = QVBoxLayout(box_filas)
        lay_filas.setSpacing(8)

        lbl_s2 = QLabel("2. FILAS DE LA SALA ACTUAL")
        lbl_s2.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        lay_filas.addWidget(lbl_s2)

        row_sel_fila = QHBoxLayout()
        self.combo_fila = QComboBox()
        self.combo_fila.currentTextChanged.connect(self._actualizar_resumen_pcs)
        row_sel_fila.addWidget(self.combo_fila, stretch=3)

        btn_del_fila = QPushButton("Eliminar Fila")
        btn_del_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_fila.setStyleSheet(
            "background-color: #881337; color: white; padding: 6px 10px; border-radius: 5px; font-weight: bold;"
        )
        btn_del_fila.clicked.connect(self._eliminar_fila)
        row_sel_fila.addWidget(btn_del_fila, stretch=1)
        lay_filas.addLayout(row_sel_fila)

        row_add_fila = QHBoxLayout()
        self.input_nueva_fila = QLineEdit()
        self.input_nueva_fila.setPlaceholderText("Nueva fila (ej. FILA E)")
        row_add_fila.addWidget(self.input_nueva_fila, stretch=3)

        btn_add_fila = QPushButton("Crear Fila")
        btn_add_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_fila.setStyleSheet(
            "background-color: #0284c7; color: white; padding: 6px 10px; border-radius: 5px; font-weight: bold;"
        )
        btn_add_fila.clicked.connect(self._crear_fila)
        row_add_fila.addWidget(btn_add_fila, stretch=1)
        lay_filas.addLayout(row_add_fila)

        layout.addWidget(box_filas)

        # =====================================================================
        # SECCIÓN 3: EQUIPOS (PCs) EN LA FILA SELECCIONADA
        # =====================================================================
        box_pcs = self._crear_contenedor_seccion()
        lay_pcs = QVBoxLayout(box_pcs)
        lay_pcs.setSpacing(8)

        lbl_s3 = QLabel("3. EQUIPOS (PCs) EN LA FILA SELECCIONADA")
        lbl_s3.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        lay_pcs.addWidget(lbl_s3)

        self.lbl_pcs_actuales = QLabel("Equipos en fila: -")
        self.lbl_pcs_actuales.setWordWrap(True)
        self.lbl_pcs_actuales.setStyleSheet(
            "color: #94a3b8; font-size: 11px; background-color: #07090e; padding: 6px; border-radius: 4px;"
        )
        lay_pcs.addWidget(self.lbl_pcs_actuales)

        self.input_pc = QLineEdit()
        self.input_pc.setPlaceholderText("Identificador del Equipo (ej. PC-28)")
        lay_pcs.addWidget(self.input_pc)

        btns_pc_layout = QHBoxLayout()
        btn_agregar_pc = QPushButton("Dar de Alta PC")
        btn_agregar_pc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_agregar_pc.setStyleSheet(
            "background-color: #059669; color: white; padding: 8px; border-radius: 5px; font-weight: bold;"
        )
        btn_agregar_pc.clicked.connect(self._agregar_pc)

        btn_eliminar_pc = QPushButton("Dar de Baja PC")
        btn_eliminar_pc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_eliminar_pc.setStyleSheet(
            "background-color: #be123c; color: white; padding: 8px; border-radius: 5px; font-weight: bold;"
        )
        btn_eliminar_pc.clicked.connect(self._quitar_pc)

        btns_pc_layout.addWidget(btn_agregar_pc)
        btns_pc_layout.addWidget(btn_eliminar_pc)
        lay_pcs.addLayout(btns_pc_layout)

        layout.addWidget(box_pcs)
        layout.addStretch()

        self._recargar_combo_labs()

    def _crear_contenedor_seccion(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #0d121f; border: 1px solid #1e293b; border-radius: 8px; }"
            "QLabel { border: none; background: transparent; }"
        )
        return frame

    def _guardar_json(self) -> None:
        RUTA_LABS.parent.mkdir(parents=True, exist_ok=True)
        with open(RUTA_LABS, "w", encoding="utf-8") as f:
            json.dump(self.datos, f, indent=4, ensure_ascii=False)
        self.cambios_realizados = True

    def _recargar_combo_labs(self, lab_seleccionado: str | None = None) -> None:
        self.combo_lab.blockSignals(True)
        self.combo_lab.clear()
        nombres_labs = list(self.datos.keys())
        self.combo_lab.addItems(nombres_labs)
        if lab_seleccionado and lab_seleccionado in nombres_labs:
            self.combo_lab.setCurrentText(lab_seleccionado)
        self.combo_lab.blockSignals(False)
        self._actualizar_filas(self.combo_lab.currentText())

    def _actualizar_filas(self, lab_nombre: str) -> None:
        self.combo_fila.blockSignals(True)
        self.combo_fila.clear()
        if lab_nombre in self.datos:
            self.combo_fila.addItems(list(self.datos[lab_nombre].keys()))
        self.combo_fila.blockSignals(False)
        self._actualizar_resumen_pcs()

    def _actualizar_resumen_pcs(self) -> None:
        lab = self.combo_lab.currentText()
        fila = self.combo_fila.currentText()
        if lab in self.datos and fila in self.datos[lab]:
            lista_pcs = self.datos[lab][fila]
            texto = ", ".join(lista_pcs) if lista_pcs else "(Fila vacía)"
            self.lbl_pcs_actuales.setText(f"Equipos en {fila} ({len(lista_pcs)}): {texto}")
        else:
            self.lbl_pcs_actuales.setText("Equipos en fila: -")

    # --- Acciones de Salas ---
    def _crear_sala(self) -> None:
        nuevo_lab = self.input_nuevo_lab.text().strip().upper()
        if not nuevo_lab:
            QMessageBox.warning(self, "Campo vacío", "Escribe el nombre de la nueva sala (ej. LABORATORIO 04).")
            return
        if nuevo_lab in self.datos:
            QMessageBox.warning(self, "Sala duplicada", f"La sala '{nuevo_lab}' ya existe.")
            return

        self.datos[nuevo_lab] = {"FILA A": []}
        self._guardar_json()
        self.input_nuevo_lab.clear()
        self._recargar_combo_labs(nuevo_lab)
        QMessageBox.information(self, "Sala Creada", f"Se creó '{nuevo_lab}' con 'FILA A' inicial.")

    def _eliminar_sala(self) -> None:
        lab = self.combo_lab.currentText()
        if not lab:
            return
        if len(self.datos) <= 1:
            QMessageBox.warning(self, "Acción no permitida", "Debe existir al menos un laboratorio en el sistema.")
            return

        resp = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Seguro que deseas eliminar '{lab}' y todas sus filas/equipos asociados?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            del self.datos[lab]
            self._guardar_json()
            self._recargar_combo_labs()

    # --- Acciones de Filas ---
    def _crear_fila(self) -> None:
        lab = self.combo_lab.currentText()
        nueva_fila = self.input_nueva_fila.text().strip().upper()
        if not lab:
            return
        if not nueva_fila:
            QMessageBox.warning(self, "Campo vacío", "Escribe el nombre de la fila (ej. FILA E).")
            return
        if nueva_fila in self.datos[lab]:
            QMessageBox.warning(self, "Fila duplicada", f"La '{nueva_fila}' ya existe en {lab}.")
            return

        self.datos[lab][nueva_fila] = []
        self._guardar_json()
        self.input_nueva_fila.clear()
        self._actualizar_filas(lab)
        self.combo_fila.setCurrentText(nueva_fila)

    def _eliminar_fila(self) -> None:
        lab = self.combo_lab.currentText()
        fila = self.combo_fila.currentText()
        if not lab or not fila:
            return

        resp = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Eliminar '{fila}' de '{lab}' junto con sus equipos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            del self.datos[lab][fila]
            self._guardar_json()
            self._actualizar_filas(lab)

    # --- Acciones de PCs ---
    def _agregar_pc(self) -> None:
        lab = self.combo_lab.currentText()
        fila = self.combo_fila.currentText()
        pc_id = self.input_pc.text().strip().upper()

        if not lab or not fila:
            QMessageBox.warning(self, "Sin ubicación", "Primero selecciona o crea una Sala y una Fila.")
            return
        if not pc_id:
            QMessageBox.warning(self, "Campo vacío", "Ingresa un identificador válido (ej. PC-28).")
            return

        for f_nombre, lista in self.datos[lab].items():
            if pc_id in lista:
                QMessageBox.warning(self, "Equipo duplicado", f"El equipo {pc_id} ya existe en {f_nombre} ({lab}).")
                return

        self.datos[lab][fila].append(pc_id)
        self._guardar_json()
        self.input_pc.clear()
        self._actualizar_resumen_pcs()

    def _quitar_pc(self) -> None:
        lab = self.combo_lab.currentText()
        fila = self.combo_fila.currentText()
        pc_id = self.input_pc.text().strip().upper()

        if lab in self.datos and fila in self.datos[lab] and pc_id in self.datos[lab][fila]:
            self.datos[lab][fila].remove(pc_id)
            self._guardar_json()
            self.input_pc.clear()
            self._actualizar_resumen_pcs()
        else:
            QMessageBox.warning(self, "No encontrado", f"No se encontró el equipo '{pc_id}' en {fila}.")