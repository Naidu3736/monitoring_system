import sys
from PyQt6.QtWidgets import QApplication
from ui.login import VentanaLogin
from ui.ui_main_window import DashboardPrincipal

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    login = VentanaLogin()
    if login.exec() == VentanaLogin.DialogCode.Accepted:
        ventana = DashboardPrincipal(usuario_actual=login.usuario_autenticado)
        ventana.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)