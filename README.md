# Anomaly-Detection-Arduino-UNO-Q
Detección de anomalías con Arduino UNO Q y Edge Impulse para Nerdearla México 2026

# Partes
UNO Q 4gb
Web Cam
USB Hub

# Entrenar el modelo

Registrarse en Edge Impulse https://www.edgeimpulse.com/
Subir las fotos bajo la etiqueta no anomaly
Entrenar el modelo con learning block FOMO-AD

# Setup

Conectar UNO Q al hub, cámara y teclado al hub, monitor hdmi. Conectarse a WiFi. Abrir línea de comandos con CTRL ALT T

Ejecutar:
sudo apt update
curl -sL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y gcc g++ make build-essential nodejs sox gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-base gstreamer1.0-plugins-base-apps
sudo npm install edge-impulse-linux -g --unsafe-perm

Ejecutar $edge-impulse-linux-runner
Loguearse y seleccionar el proyecto.

Salir con CTRL C
Copiar anomaly.py por FTP o bien via Nano, copy-paste en línea de comandos

Ejecutar python3 anomaly.py
