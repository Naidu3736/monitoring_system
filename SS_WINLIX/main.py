import sys
from PyQt6.QtWidgets import QApplication
from ui.ui_main_window import DashboardPrincipal

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = DashboardPrincipal()
    ventana.showMaximized()
    sys.exit(app.exec())
