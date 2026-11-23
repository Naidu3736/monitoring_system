# SAPPHIRE SOC — Monitoreo de Seguridad de Hardware (BUAP)

Aplicación de escritorio en **Python / PyQt6** con **Hub TCP embebido** para la supervisión en tiempo real de periféricos físicos (teclado, mouse y monitor) en laboratorios de cómputo, registro forense de incidentes y despacho de alertas por Telegram y correo electrónico (SMTP).

---

## Funcionalidades implementadas

### 1. Autenticación integrada
- Pantalla de inicio de sesión integrada en la ventana principal (`ui/login.py`), sin diálogos flotantes.
- Almacenamiento de credenciales cifradas con `SHA-256` + salt en `config/usuarios.json`.
- Opción para mostrar/ocultar contraseña, avisos de validación en línea y bloqueo temporal de 15 segundos tras 4 intentos fallidos.
- Cierre de sesión desde el panel lateral que detiene el Hub y regresa al login en la misma ventana.
- Credenciales iniciales de prueba (si no existe `config/usuarios.json`): `admin` / `admin123`.

### 2. Centro de Monitoreo en tiempo real
- Visualización por **Laboratorios / Salas** y **Filas** con tarjetas individuales por estación (`ui/card_pc.py`).
- Estados visuales por equipo:
  - `OK` (**Protegido**): estación sin incidentes activos.
  - `ALERTA` (**Intrusión**): parpadeo visual al recibir un evento `remove` desde un agente real.
  - `TIMEOUT` (**Sin señal**): cuando un agente conectado cierra o pierde su enlace TCP con el Hub.
- **Panel Inspector**: muestra ubicación, estado de enlace del agente, último evento recibido, estado de entrega de alertas (Telegram / SMTP) y botón **Reconocer y Silenciar Alarma**.
- **Indicadores superiores (KPIs)**: conteo de equipos `OK` / `ALERTA`, estado del perímetro y dirección/puerto real del Hub TCP.
- **Consola de bitácora**: muestra actividad en tiempo real y carga los últimos registros de `monitoring_system-main/logs/alerts.log`.
- **Atajos de teclado**: `F2` (mostrar/ocultar menú lateral), `F3` (mostrar/ocultar inspector de detalles), `F5` (recargar `assets/styles.css`).

### 3. Registro de Eventos y Registro de Red
- **Registro de Eventos**: tabla cronológica con fecha/hora, estación, sala, acción (`add`, `remove`, `change`), dispositivo/`sys_name` y estado (`ACTIVA`, `CONECTADO` o `SILENCIADA` con el nombre del operador).
- **Registro de Red**: tabla por estación con la IP/puerto TCP del agente conectado, estado del enlace (`CONECTADO`, `EN ESPERA DE AGENTE`, `DESCONECTADO`, `ALERTA ACTIVA`) y contador de sockets conectados al Hub.

### 4. Configuración del Sistema (`ui/config_view.py` y `ui/adm_panel.py`)
Organizada en cuatro sub-pestañas dentro del panel principal:
- **Salas y Equipos**: editor interactivo de 3 columnas (`Salas` | `Filas` | `Equipos`) que permite crear, renombrar y eliminar salas o filas, dar de alta equipos individualmente, en lote (separados por comas) o con sugerencia correlativa (`+ PC-XX`), y dar de baja seleccionando uno o varios equipos. Persiste automáticamente en `config/laboratorios.json` y sincroniza el monitoreo al instante. También cuenta con acceso directo desde el botón `+ Salas` en el monitoreo.
- **Operadores y Acceso**: listado de cuentas registradas en `config/usuarios.json` (indicando la sesión actual), alta de nuevos operadores con confirmación de contraseña, cambio de contraseña y eliminación protegida.
- **Alertas y Hub**: formulario para ver y guardar en `.env` las credenciales de **Bot de Telegram**, **Correo SMTP** (con TLS) y configuración del **Servidor Hub TCP** (`HUB_HOST`, `HUB_PORT`). Los canales de Telegram y SMTP se recargan en caliente al guardar.
- **Apariencia**: selector entre **Modo Oscuro** (carbón neutro) y **Modo Claro**, aplicado en tiempo real y persistido en `config/preferencias.json`.

### 5. Hub TCP y Alertas reales (`services/hub_bridge.py` y `monitoring_system-main/hub/`)
- Servidor TCP no bloqueante (`selectors`) ejecutado en un hilo `QThread` dentro de la aplicación.
- Recibe mensajes JSON delimitados por salto de línea (`\n`) con el formato:
  ```json
  {
    "pc_name": "PC-01",
    "device_name": "Teclado USB HID",
    "action": "remove",
    "sys_name": "USB\\VID_046D&PID_C31C"
  }
  ```
- Maneja desconexiones abruptas de clientes y mensajes malformados sin interrumpir el servicio.
- Integra `AlertManager` para registrar incidentes en `monitoring_system-main/logs/alerts.log` y despachar notificaciones reales mediante `TelegramAlert` y `EmailAlert`.

### 6. Agente de Monitoreo de Estaciones (`monitoring_system-main/pc_monitoring/`)
- **Windows** (`windows_monitoring.py`): vigila eventos WMI (`Creation`, `Deletion`, `Modification`) sobre `Win32_Keyboard`, `Win32_PointingDevice` y `Win32_DesktopMonitor`.
- **Linux** (`linux_monitoring.py`): vigila eventos `pyudev` en subsistemas `usb` y `drm`.
- Envía cada evento al Hub mediante `ClientPC` (`pc_client.py`).

---

## Estructura principal del proyecto

```text
SS_WIN/
├── main.py                              # Punto de entrada de la aplicación PyQt6
├── assets/
│   └── styles.css                       # Hoja de estilos oscura (SAPPHIRE SOC)
├── config/
│   ├── laboratorios.json                # Topología de salas, filas y equipos
│   └── usuarios.json                    # Operadores autorizados (hash SHA-256)
├── resources/
│   └── pc.png                           # Icono de estación para tarjetas
├── services/
│   └── hub_bridge.py                    # Puente PyQt6 ↔ Hub TCP, .env y AlertManager
├── ui/
│   ├── login.py                         # Pantalla integrada de inicio de sesión
│   ├── ui_main_window.py                # Ventana principal, monitoreo, eventos y red
│   ├── card_pc.py                       # Tarjeta visual interactiva por estación
│   ├── adm_panel.py                     # Editor de 3 columnas para Salas/Filas/PCs
│   └── config_view.py                   # Vista de Configuración con 3 sub-pestañas
└── monitoring_system-main/
    ├── hub/                             # Servidor TCP y AlertManager (Telegram / SMTP)
    ├── pc_monitoring/                   # Agente cliente para Windows (WMI) y Linux (pyudev)
    └── logs/alerts.log                  # Bitácora persistente de alertas
```

---

## Requisitos e instalación

### Panel principal + Hub (Windows)
Dependencias base en el entorno virtual (`venv`):
```powershell
.\venv\Scripts\pip.exe install PyQt6 requests python-dotenv
```

### Agente cliente `pc_monitoring`
- **En Windows** (incluyendo pruebas locales en la misma PC):
  ```powershell
  .\venv\Scripts\pip.exe install wmi pywin32
  ```
- **En Linux**:
  ```bash
  pip install pyudev
  ```

---

## Ejecución y prueba rápida

### 1. Iniciar el Panel y Hub TCP
```powershell
.\venv\Scripts\python.exe main.py
```
1. Inicia sesión con una cuenta registrada en `config/usuarios.json` (por defecto `admin` / `admin123`).
2. *(Opcional)* Entra a **Configuración del Sistema → Alertas y Hub** para configurar Telegram y/o SMTP y pulsa **Guardar y Aplicar**.
3. Confirma en la barra superior que el indicador muestre `● HUB TCP: 0.0.0.0:5000`.

### 2. Conectar un agente real (en la misma PC o en red local)
En otra terminal PowerShell:
```powershell
$env:PYTHONPATH = "c:\Users\Diego Salinas\Desktop\SS_WIN\monitoring_system-main"
$env:MONITOR_SERVER_HOST = "127.0.0.1"   # Usa la IP del Hub si el agente está en otra PC
$env:MONITOR_SERVER_PORT = "5000"
$env:MONITOR_PC_NAME = "PC-01"           # Debe coincidir con un ID en config/laboratorios.json
.\venv\Scripts\python.exe monitoring_system-main\pc_monitoring\main.py
```
Al desconectar o reconectar un teclado o mouse USB, el evento se reflejará en tiempo real en el mapa de laboratorio, la consola, `Registro de Eventos`, `alerts.log` y los canales de alerta configurados.

---

## Variables de entorno

### Archivo `.env` (gestionable desde *Configuración → Alertas y Hub*)
| Variable | Descripción | Valor por defecto |
|---|---|---|
| `HUB_HOST` | Interfaz de escucha del servidor Hub TCP | `0.0.0.0` |
| `HUB_PORT` | Puerto TCP del Hub | `5000` |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | *(vacío)* |
| `TELEGRAM_CHAT_ID` | ID del chat o grupo destino en Telegram | *(vacío)* |
| `SMTP_HOST` | Servidor SMTP (ej. `smtp.gmail.com`) | *(vacío)* |
| `SMTP_PORT` | Puerto SMTP (ej. `587`) | *(vacío)* |
| `SMTP_USERNAME` | Usuario de autenticación SMTP | *(vacío)* |
| `SMTP_PASSWORD` | Contraseña o App Password SMTP | *(vacío)* |
| `SMTP_SENDER` | Dirección remitente | *(vacío)* |
| `SMTP_RECIPIENT` | Dirección destinataria de alertas | *(vacío)* |
| `SMTP_USE_TLS` | Habilitar STARTTLS (`true` / `false`) | `true` |

### Variables del agente `pc_monitoring`
| Variable | Descripción | Valor por defecto |
|---|---|---|
| `MONITOR_SERVER_HOST` | IP o hostname del Hub TCP | `127.0.0.1` |
| `MONITOR_SERVER_PORT` | Puerto TCP del Hub | `5000` |
| `MONITOR_SERVER_TIMEOUT` | Timeout de conexión en segundos | `10` |
| `MONITOR_PC_NAME` | Identificador de la estación (ej. `PC-01`) | `PC_CCOX_XX` |

---

## Componentes pendientes / en desarrollo
- `monitoring_system-main/node_sensor/`: estructura reservada para nodos sensores externos (aún sin implementación).
- `services/notifications.py` y `modules/`: archivos/directorios base sin lógica activa (las notificaciones se gestionan actualmente mediante `hub/alerts/` vía `services/hub_bridge.py`).
