#!/usr/bin/env bash
# ==============================================================================
# INSTALADOR AUTOMÁTICO PARA ORACLE CLOUD (SANTIAGO / SÃO PAULO)
# Configura: Zona horaria Lima, Swap 2GB, FFmpeg, rclone y carpetas de logs
# ==============================================================================

set -e

echo "================================================================="
echo " CONFIGURANDO SERVIDOR ORACLE CLOUD PARA GRABADOR DE RADIOS"
echo "================================================================="

# 1. Zona horaria de Perú (GMT-5)
echo "--> Configurando zona horaria a America/Lima..."
sudo timedatectl set-timezone America/Lima
date

# 2. Memoria Swap de 2 GB para proteger instancias de 1 GB RAM (AMD Micro)
if [ ! -f /swapfile ]; then
    echo "--> Creando archivo Swap de 2 GB..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap de 2 GB activado:"
    free -h
else
    echo "--> Swap ya existe."
    free -h
fi

# 3. Instalar dependencias (FFmpeg, rclone, curl, jq)
echo "--> Actualizando repositorios e instalando FFmpeg y rclone..."
sudo apt-get update -qq
sudo apt-get install -y ffmpeg rclone curl jq git

# 4. Crear carpeta de logs
mkdir -p "$HOME/radio_logs"

echo "================================================================="
echo " ¡SERVIDOR LISTO! Versiones instaladas:"
ffmpeg -version | head -n 1
rclone --version | head -n 1
echo "================================================================="
