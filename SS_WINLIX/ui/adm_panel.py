import json
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QWidget, QListWidget,
    QListWidgetItem, QAbstractItemView, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.login import repolir_widget

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_LABS = BASE_DIR / "config" / "laboratorios.json"


class WidgetTopologiaLabs(QWidget):
    """Editor visual de 3 columnas (Salas | Filas | Equipos)."""

    topologia_modificada = pyqtSignal()

    def __init__(
        self,
        datos_laboratorios: dict[str, dict[str, list[str]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.datos = datos_laboratorios

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # --- Barra superior: ruta actual + totales ---
        top_bar = QFrame()
        top_bar.setProperty("class", "config-card")
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(14, 10, 14, 10)
        top_lay.setSpacing(12)

        self.lbl_breadcrumb = QLabel("Selecciona una sala para explorar sus filas y equipos")
        self.lbl_breadcrumb.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: 600;")
        top_lay.addWidget(self.lbl_breadcrumb)
        top_lay.addStretch()

        self.lbl_totales = QLabel("0 salas · 0 filas · 0 PCs")
        self.lbl_totales.setProperty("class", "status-pill")
        self.lbl_totales.setProperty("state", "info")
        top_lay.addWidget(self.lbl_totales)
        layout.addWidget(top_bar)

        # --- Banner inline de feedback (sin popups molestos) ---
        self.lbl_banner = QLabel("")
        self.lbl_banner.setObjectName("StatusBanner")
        self.lbl_banner.setWordWrap(True)
        self.lbl_banner.setVisible(False)
        layout.addWidget(self.lbl_banner)

        # --- Espacio de trabajo en 3 columnas ---
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(14)

        cols_layout.addWidget(self._construir_col_salas(), stretch=3)
        cols_layout.addWidget(self._construir_col_filas(), stretch=3)
        cols_layout.addWidget(self._construir_col_pcs(), stretch=4)

        layout.addLayout(cols_layout, stretch=1)

        self.refrescar()

    # =========================================================================
    # CONSTRUCCIÓN DE COLUMNAS
    # =========================================================================
    def _construir_col_salas(self) -> QFrame:
        box = QFrame()
        box.setProperty("class", "topo-col")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        lbl = QLabel("1. SALAS / LABORATORIOS")
        lbl.setProperty("class", "col-title")
        head.addWidget(lbl)
        head.addStretch()
        self.lbl_count_labs = QLabel("0")
        self.lbl_count_labs.setProperty("class", "count-badge")
        head.addWidget(self.lbl_count_labs)
        lay.addLayout(head)

        hint = QLabel("Haz clic en una sala para ver o editar sus filas.")
        hint.setProperty("class", "muted-hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.lista_labs = QListWidget()
        self.lista_labs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_labs.currentItemChanged.connect(self._al_cambiar_lab)
        lay.addWidget(self.lista_labs, stretch=1)

        row_add = QHBoxLayout()
        row_add.setSpacing(6)
        self.input_nuevo_lab = QLineEdit()
        self.input_nuevo_lab.setPlaceholderText("Nueva sala (ej. LABORATORIO 04)")
        self.input_nuevo_lab.returnPressed.connect(self._crear_sala)
        row_add.addWidget(self.input_nuevo_lab, stretch=1)

        btn_add = QPushButton("+ Crear")
        btn_add.setProperty("class", "btn-primary")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._crear_sala)
        row_add.addWidget(btn_add)
        lay.addLayout(row_add)

        row_actions = QHBoxLayout()
        row_actions.setSpacing(6)
        self.btn_renombrar_lab = QPushButton("Renombrar")
        self.btn_renombrar_lab.setProperty("class", "btn-secondary")
        self.btn_renombrar_lab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_renombrar_lab.clicked.connect(self._renombrar_sala)
        row_actions.addWidget(self.btn_renombrar_lab)

        self.btn_del_lab = QPushButton("Eliminar sala")
        self.btn_del_lab.setProperty("class", "btn-danger-outline")
        self.btn_del_lab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_lab.clicked.connect(self._eliminar_sala)
        row_actions.addWidget(self.btn_del_lab)
        lay.addLayout(row_actions)

        return box

    def _construir_col_filas(self) -> QFrame:
        box = QFrame()
        box.setProperty("class", "topo-col")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        lbl = QLabel("2. FILAS DE LA SALA")
        lbl.setProperty("class", "col-title")
        head.addWidget(lbl)
        head.addStretch()
        self.lbl_count_filas = QLabel("0")
        self.lbl_count_filas.setProperty("class", "count-badge")
        head.addWidget(self.lbl_count_filas)
        lay.addLayout(head)

        self.lbl_lab_context = QLabel("Selecciona una sala a la izquierda.")
        self.lbl_lab_context.setProperty("class", "muted-hint")
        self.lbl_lab_context.setWordWrap(True)
        lay.addWidget(self.lbl_lab_context)

        self.lista_filas = QListWidget()
        self.lista_filas.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_filas.currentItemChanged.connect(self._al_cambiar_fila)
        lay.addWidget(self.lista_filas, stretch=1)

        self.lbl_empty_filas = QLabel(
            "Esta sala aún no tiene filas.\nAgrega la primera abajo (ej. FILA A)."
        )
        self.lbl_empty_filas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_filas.setStyleSheet(
            "color: #64748b; font-size: 12px; padding: 14px; "
            "background-color: #070a12; border: 1px dashed #1e293b; border-radius: 8px;"
        )
        self.lbl_empty_filas.setVisible(False)
        lay.addWidget(self.lbl_empty_filas)

        row_add = QHBoxLayout()
        row_add.setSpacing(6)
        self.input_nueva_fila = QLineEdit()
        self.input_nueva_fila.setPlaceholderText("Nueva fila (ej. FILA B)")
        self.input_nueva_fila.returnPressed.connect(self._crear_fila)
        row_add.addWidget(self.input_nueva_fila, stretch=1)

        self.btn_add_fila = QPushButton("+ Crear")
        self.btn_add_fila.setProperty("class", "btn-primary")
        self.btn_add_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_fila.clicked.connect(self._crear_fila)
        row_add.addWidget(self.btn_add_fila)
        lay.addLayout(row_add)

        row_actions = QHBoxLayout()
        row_actions.setSpacing(6)
        self.btn_renombrar_fila = QPushButton("Renombrar")
        self.btn_renombrar_fila.setProperty("class", "btn-secondary")
        self.btn_renombrar_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_renombrar_fila.clicked.connect(self._renombrar_fila)
        row_actions.addWidget(self.btn_renombrar_fila)

        self.btn_del_fila = QPushButton("Eliminar fila")
        self.btn_del_fila.setProperty("class", "btn-danger-outline")
        self.btn_del_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_fila.clicked.connect(self._eliminar_fila)
        row_actions.addWidget(self.btn_del_fila)
        lay.addLayout(row_actions)

        return box

    def _construir_col_pcs(self) -> QFrame:
        box = QFrame()
        box.setProperty("class", "topo-col")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        lbl = QLabel("3. EQUIPOS (PCs)")
        lbl.setProperty("class", "col-title")
        head.addWidget(lbl)
        head.addStretch()

        self.btn_auto_pc = QPushButton("+ Siguiente PC")
        self.btn_auto_pc.setProperty("class", "btn-secondary")
        self.btn_auto_pc.setToolTip("Agrega automáticamente el siguiente número correlativo (ej. PC-06)")
        self.btn_auto_pc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_pc.clicked.connect(self._agregar_siguiente_pc)
        head.addWidget(self.btn_auto_pc)

        self.lbl_count_pcs = QLabel("0")
        self.lbl_count_pcs.setProperty("class", "count-badge")
        head.addWidget(self.lbl_count_pcs)
        lay.addLayout(head)

        self.lbl_fila_context = QLabel("Selecciona una fila para administrar sus equipos.")
        self.lbl_fila_context.setProperty("class", "muted-hint")
        self.lbl_fila_context.setWordWrap(True)
        lay.addWidget(self.lbl_fila_context)

        self.lista_pcs = QListWidget()
        self.lista_pcs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_pcs.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista_pcs.itemSelectionChanged.connect(self._actualizar_estado_botones)
        lay.addWidget(self.lista_pcs, stretch=1)

        self.lbl_empty_pcs = QLabel(
            "No hay equipos registrados en esta fila.\nEscribe un ID abajo o usa '+ Siguiente PC'."
        )
        self.lbl_empty_pcs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_pcs.setWordWrap(True)
        self.lbl_empty_pcs.setStyleSheet(
            "color: #64748b; font-size: 12px; padding: 14px; "
            "background-color: #070a12; border: 1px dashed #1e293b; border-radius: 8px;"
        )
        self.lbl_empty_pcs.setVisible(False)
        lay.addWidget(self.lbl_empty_pcs)

        row_add = QHBoxLayout()
        row_add.setSpacing(6)
        self.input_pc = QLineEdit()
        self.input_pc.setPlaceholderText("PC-06 o lista: PC-06, PC-07")
        self.input_pc.returnPressed.connect(self._agregar_pc)
        row_add.addWidget(self.input_pc, stretch=1)

        self.btn_agregar_pc = QPushButton("+ Alta")
        self.btn_agregar_pc.setProperty("class", "btn-success")
        self.btn_agregar_pc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_agregar_pc.clicked.connect(self._agregar_pc)
        row_add.addWidget(self.btn_agregar_pc)
        lay.addLayout(row_add)

        self.btn_eliminar_pc = QPushButton("Dar de baja seleccionados")
        self.btn_eliminar_pc.setProperty("class", "btn-danger-outline")
        self.btn_eliminar_pc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_eliminar_pc.clicked.connect(self._quitar_pcs_seleccionados)
        lay.addWidget(self.btn_eliminar_pc)

        return box

    # =========================================================================
    # UTILIDADES DE ESTADO Y PERSISTENCIA
    # =========================================================================
    def _mostrar_banner(self, mensaje: str, kind: str = "ok") -> None:
        self.lbl_banner.setText(mensaje)
        self.lbl_banner.setProperty("kind", kind)
        self.lbl_banner.setVisible(True)
        repolir_widget(self.lbl_banner)

    def _lab_actual(self) -> str | None:
        item = self.lista_labs.currentItem()
        if item is None:
            return None
        val = item.data(Qt.ItemDataRole.UserRole)
        return str(val) if val else None

    def _fila_actual(self) -> str | None:
        item = self.lista_filas.currentItem()
        if item is None:
            return None
        val = item.data(Qt.ItemDataRole.UserRole)
        return str(val) if val else None

    def _guardar_json(self) -> None:
        RUTA_LABS.parent.mkdir(parents=True, exist_ok=True)
        with open(RUTA_LABS, "w", encoding="utf-8") as f:
            json.dump(self.datos, f, indent=4, ensure_ascii=False)
        self.topologia_modificada.emit()

    def _actualizar_totales(self) -> None:
        total_labs = len(self.datos)
        total_filas = sum(len(filas) for filas in self.datos.values())
        total_pcs = sum(
            len(pcs)
            for filas in self.datos.values()
            for pcs in filas.values()
        )
        self.lbl_totales.setText(
            f"{total_labs} {'sala' if total_labs == 1 else 'salas'} · "
            f"{total_filas} {'fila' if total_filas == 1 else 'filas'} · "
            f"{total_pcs} {'equipo' if total_pcs == 1 else 'equipos'}"
        )

        lab = self._lab_actual()
        fila = self._fila_actual()
        if lab and fila:
            n_pcs = len(self.datos.get(lab, {}).get(fila, []))
            self.lbl_breadcrumb.setText(f"{lab}   ›   {fila}   ({n_pcs} PCs)")
        elif lab:
            self.lbl_breadcrumb.setText(f"{lab}   ›   Sin filas")
        else:
            self.lbl_breadcrumb.setText("Selecciona una sala para explorar sus filas y equipos")

    def _actualizar_estado_botones(self) -> None:
        lab = self._lab_actual()
        fila = self._fila_actual()
        hay_lab = lab is not None and lab in self.datos
        hay_fila = hay_lab and fila is not None and fila in self.datos[lab]

        self.btn_renombrar_lab.setEnabled(hay_lab)
        self.btn_del_lab.setEnabled(hay_lab and len(self.datos) > 1)

        self.input_nueva_fila.setEnabled(hay_lab)
        self.btn_add_fila.setEnabled(hay_lab)
        self.btn_renombrar_fila.setEnabled(hay_fila)
        self.btn_del_fila.setEnabled(hay_fila)

        self.input_pc.setEnabled(hay_fila)
        self.btn_agregar_pc.setEnabled(hay_fila)
        self.btn_auto_pc.setEnabled(hay_fila)

        seleccionados = len(self.lista_pcs.selectedItems())
        self.btn_eliminar_pc.setEnabled(hay_fila and seleccionados > 0)
        if seleccionados > 0:
            self.btn_eliminar_pc.setText(
                f"Dar de baja ({seleccionados} {'equipo' if seleccionados == 1 else 'equipos'})"
            )
        else:
            self.btn_eliminar_pc.setText("Dar de baja seleccionados")

        if hay_fila:
            sugerido = self._sugerir_siguiente_pc()
            self.btn_auto_pc.setText(f"+ {sugerido}")
        else:
            self.btn_auto_pc.setText("+ Siguiente PC")

    # =========================================================================
    # REFRESCO DE LISTAS
    # =========================================================================
    def refrescar(
        self,
        lab_objetivo: str | None = None,
        fila_objetivo: str | None = None,
    ) -> None:
        lab_previo = lab_objetivo if lab_objetivo is not None else self._lab_actual()
        fila_previa = fila_objetivo if fila_objetivo is not None else self._fila_actual()

        self.lista_labs.blockSignals(True)
        self.lista_labs.clear()

        fila_idx_sel = 0
        for idx, (lab_nombre, filas) in enumerate(self.datos.items()):
            n_filas = len(filas)
            n_pcs = sum(len(pcs) for pcs in filas.values())
            texto = f"{lab_nombre} ({n_filas}f · {n_pcs} PCs)"
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, lab_nombre)
            self.lista_labs.addItem(item)
            if lab_nombre == lab_previo:
                fila_idx_sel = idx

        self.lbl_count_labs.setText(str(len(self.datos)))
        if self.lista_labs.count() > 0:
            self.lista_labs.setCurrentRow(fila_idx_sel)
        self.lista_labs.blockSignals(False)

        self._poblar_filas(fila_objetivo=fila_previa)

    def _al_cambiar_lab(self, _curr: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        self._poblar_filas()

    def _poblar_filas(self, fila_objetivo: str | None = None) -> None:
        lab = self._lab_actual()
        self.lista_filas.blockSignals(True)
        self.lista_filas.clear()

        if lab and lab in self.datos:
            filas_dict = self.datos[lab]
            self.lbl_lab_context.setText(f"Filas configuradas en {lab}:")
            sel_idx = 0
            for idx, (fila_nombre, pcs) in enumerate(filas_dict.items()):
                item = QListWidgetItem(f"{fila_nombre}   ({len(pcs)} PCs)")
                item.setData(Qt.ItemDataRole.UserRole, fila_nombre)
                self.lista_filas.addItem(item)
                if fila_nombre == fila_objetivo:
                    sel_idx = idx
            self.lbl_count_filas.setText(str(len(filas_dict)))
            vacia = len(filas_dict) == 0
            self.lista_filas.setVisible(not vacia)
            self.lbl_empty_filas.setVisible(vacia)
            if not vacia:
                self.lista_filas.setCurrentRow(sel_idx)
        else:
            self.lbl_lab_context.setText("Selecciona una sala a la izquierda.")
            self.lbl_count_filas.setText("0")
            self.lista_filas.setVisible(True)
            self.lbl_empty_filas.setVisible(False)

        self.lista_filas.blockSignals(False)
        self._poblar_pcs()

    def _al_cambiar_fila(self, _curr: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        self._poblar_pcs()

    def _poblar_pcs(self) -> None:
        lab = self._lab_actual()
        fila = self._fila_actual()
        self.lista_pcs.blockSignals(True)
        self.lista_pcs.clear()

        if lab and fila and lab in self.datos and fila in self.datos[lab]:
            pcs = self.datos[lab][fila]
            self.lbl_fila_context.setText(
                f"Equipos en {fila} (selecciona uno o varios para dar de baja):"
            )
            for pc_id in pcs:
                item = QListWidgetItem(f"●   {pc_id}")
                item.setData(Qt.ItemDataRole.UserRole, pc_id)
                self.lista_pcs.addItem(item)
            self.lbl_count_pcs.setText(str(len(pcs)))
            vacia = len(pcs) == 0
            self.lista_pcs.setVisible(not vacia)
            self.lbl_empty_pcs.setVisible(vacia)
        else:
            self.lbl_fila_context.setText("Crea o selecciona una fila para administrar equipos.")
            self.lbl_count_pcs.setText("0")
            self.lista_pcs.setVisible(True)
            self.lbl_empty_pcs.setVisible(False)

        self.lista_pcs.blockSignals(False)
        self._actualizar_totales()
        self._actualizar_estado_botones()

    # =========================================================================
    # ACCIONES DE SALAS
    # =========================================================================
    def _crear_sala(self) -> None:
        nuevo_lab = self.input_nuevo_lab.text().strip().upper()
        if not nuevo_lab:
            self._mostrar_banner("Escribe un nombre para la nueva sala (ej. LABORATORIO 04).", "warn")
            self.input_nuevo_lab.setFocus()
            return
        if nuevo_lab in self.datos:
            self._mostrar_banner(f"La sala '{nuevo_lab}' ya existe.", "warn")
            return

        self.datos[nuevo_lab] = {"FILA A": []}
        self._guardar_json()
        self.input_nuevo_lab.clear()
        self.refrescar(lab_objetivo=nuevo_lab, fila_objetivo="FILA A")
        self._mostrar_banner(f"Sala '{nuevo_lab}' creada con 'FILA A' inicial.", "ok")

    def _renombrar_sala(self) -> None:
        lab = self._lab_actual()
        if not lab or lab not in self.datos:
            return
        nuevo, ok = QInputDialog.getText(
            self, "Renombrar Sala", "Nuevo nombre para la sala:", text=lab
        )
        if not ok:
            return
        nuevo = nuevo.strip().upper()
        if not nuevo or nuevo == lab:
            return
        if nuevo in self.datos:
            self._mostrar_banner(f"Ya existe una sala llamada '{nuevo}'.", "warn")
            return

        reordenado = {
            (nuevo if k == lab else k): v for k, v in self.datos.items()
        }
        self.datos.clear()
        self.datos.update(reordenado)
        self._guardar_json()
        self.refrescar(lab_objetivo=nuevo)
        self._mostrar_banner(f"Sala renombrada de '{lab}' a '{nuevo}'.", "ok")

    def _eliminar_sala(self) -> None:
        lab = self._lab_actual()
        if not lab or lab not in self.datos:
            return
        if len(self.datos) <= 1:
            self._mostrar_banner("Debe existir al menos un laboratorio en el sistema.", "warn")
            return

        n_pcs = sum(len(pcs) for pcs in self.datos[lab].values())
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar '{lab}' junto con sus {len(self.datos[lab])} filas y {n_pcs} equipos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            del self.datos[lab]
            self._guardar_json()
            self.refrescar()
            self._mostrar_banner(f"Sala '{lab}' eliminada.", "info")

    # =========================================================================
    # ACCIONES DE FILAS
    # =========================================================================
    def _crear_fila(self) -> None:
        lab = self._lab_actual()
        if not lab or lab not in self.datos:
            self._mostrar_banner("Primero selecciona o crea una sala.", "warn")
            return
        nueva_fila = self.input_nueva_fila.text().strip().upper()
        if not nueva_fila:
            self._mostrar_banner("Escribe el nombre de la fila (ej. FILA B).", "warn")
            self.input_nueva_fila.setFocus()
            return
        if nueva_fila in self.datos[lab]:
            self._mostrar_banner(f"'{nueva_fila}' ya existe en {lab}.", "warn")
            return

        self.datos[lab][nueva_fila] = []
        self._guardar_json()
        self.input_nueva_fila.clear()
        self.refrescar(lab_objetivo=lab, fila_objetivo=nueva_fila)
        self._mostrar_banner(f"Fila '{nueva_fila}' creada en {lab}.", "ok")

    def _renombrar_fila(self) -> None:
        lab = self._lab_actual()
        fila = self._fila_actual()
        if not lab or not fila or lab not in self.datos or fila not in self.datos[lab]:
            return
        nueva, ok = QInputDialog.getText(
            self, "Renombrar Fila", f"Nuevo nombre para '{fila}' en {lab}:", text=fila
        )
        if not ok:
            return
        nueva = nueva.strip().upper()
        if not nueva or nueva == fila:
            return
        if nueva in self.datos[lab]:
            self._mostrar_banner(f"La fila '{nueva}' ya existe en {lab}.", "warn")
            return

        self.datos[lab] = {
            (nueva if k == fila else k): v for k, v in self.datos[lab].items()
        }
        self._guardar_json()
        self.refrescar(lab_objetivo=lab, fila_objetivo=nueva)
        self._mostrar_banner(f"Fila renombrada a '{nueva}'.", "ok")

    def _eliminar_fila(self) -> None:
        lab = self._lab_actual()
        fila = self._fila_actual()
        if not lab or not fila or lab not in self.datos or fila not in self.datos[lab]:
            return

        n_pcs = len(self.datos[lab][fila])
        resp = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar '{fila}' de '{lab}' junto con sus {n_pcs} equipos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            del self.datos[lab][fila]
            self._guardar_json()
            self.refrescar(lab_objetivo=lab)
            self._mostrar_banner(f"Fila '{fila}' eliminada de {lab}.", "info")

    # =========================================================================
    # ACCIONES DE EQUIPOS (PCs)
    # =========================================================================
    def _sugerir_siguiente_pc(self) -> str:
        lab = self._lab_actual()
        numeros: list[int] = []
        if lab and lab in self.datos:
            for pcs in self.datos[lab].values():
                for pc in pcs:
                    m = re.search(r"(\d+)$", pc)
                    if m:
                        numeros.append(int(m.group(1)))
        siguiente = (max(numeros) + 1) if numeros else 1
        return f"PC-{siguiente:02d}"

    def _agregar_siguiente_pc(self) -> None:
        sugerido = self._sugerir_siguiente_pc()
        self.input_pc.setText(sugerido)
        self._agregar_pc()

    def _agregar_pc(self) -> None:
        lab = self._lab_actual()
        fila = self._fila_actual()
        if not lab or not fila or lab not in self.datos or fila not in self.datos[lab]:
            self._mostrar_banner("Primero selecciona o crea una Sala y una Fila.", "warn")
            return

        entrada = self.input_pc.text().strip().upper()
        if not entrada:
            self._mostrar_banner("Ingresa al menos un identificador de equipo (ej. PC-06).", "warn")
            self.input_pc.setFocus()
            return

        candidatos = [p.strip() for p in entrada.split(",") if p.strip()]
        existentes_lab = {
            pc: f_nombre
            for f_nombre, lista in self.datos[lab].items()
            for pc in lista
        }

        agregados: list[str] = []
        duplicados: list[str] = []

        for pc_id in candidatos:
            if pc_id in existentes_lab or pc_id in agregados:
                duplicados.append(pc_id)
                continue
            self.datos[lab][fila].append(pc_id)
            agregados.append(pc_id)

        if agregados:
            self._guardar_json()
            self.input_pc.clear()
            self.refrescar(lab_objetivo=lab, fila_objetivo=fila)
            msg = f"Alta completada en {fila}: {', '.join(agregados)}."
            if duplicados:
                msg += f" (Omitidos por duplicados: {', '.join(duplicados)})"
                self._mostrar_banner(msg, "warn")
            else:
                self._mostrar_banner(msg, "ok")
        else:
            self._mostrar_banner(
                f"Ya existen en {lab}: {', '.join(duplicados)}.", "warn"
            )

    def _quitar_pcs_seleccionados(self) -> None:
        lab = self._lab_actual()
        fila = self._fila_actual()
        if not lab or not fila or lab not in self.datos or fila not in self.datos[lab]:
            return

        items = self.lista_pcs.selectedItems()
        if not items:
            return

        pcs_a_quitar = [str(it.data(Qt.ItemDataRole.UserRole)) for it in items]
        if len(pcs_a_quitar) > 1:
            resp = QMessageBox.question(
                self,
                "Confirmar baja",
                f"¿Dar de baja {len(pcs_a_quitar)} equipos de '{fila}'?\n({', '.join(pcs_a_quitar)})",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self.datos[lab][fila] = [
            pc for pc in self.datos[lab][fila] if pc not in pcs_a_quitar
        ]
        self._guardar_json()
        self.refrescar(lab_objetivo=lab, fila_objetivo=fila)
        self._mostrar_banner(
            f"Baja realizada en {fila}: {', '.join(pcs_a_quitar)}.", "info"
        )
