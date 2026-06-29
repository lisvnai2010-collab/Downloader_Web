#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# INSTALADOR DE DOWNLOADER WEB
# Repositorio: https://github.com/lisvnai2010-collab/Downloader_Web
# ============================================

echo "🚀 Iniciando instalación del Downloader Web..."
echo ""

# 1. Verificar que estamos en Termux
if [ ! -d "/data/data/com.termux" ]; then
    echo "❌ Este script solo funciona en Termux"
    exit 1
fi

# 2. Actualizar paquetes
echo "📦 Actualizando paquetes..."
pkg update -y && pkg upgrade -y

# 3. Instalar dependencias
echo "📦 Instalando dependencias..."
pkg install python clang binutils git -y
pip install flask requests beautifulsoup4 urllib3

# 4. Crear carpeta ZEROX_WORD en Downloads
INSTALL_DIR="/storage/emulated/0/Download/ZEROX_WORD"
echo "📁 Creando carpeta de instalación: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# 5. Clonar repositorio dentro de ZEROX_WORD
echo "📥 Descargando el Downloader Web..."
rm -rf "$INSTALL_DIR/Downloader_Web"
git clone https://github.com/lisvnai2010-collab/Downloader_Web.git "$INSTALL_DIR/Downloader_Web"
cd "$INSTALL_DIR/Downloader_Web"

# 6. Dar permisos a los binarios
echo "🔓 Dando permisos..."
chmod +x bitzero_32.so bitzero_64.so bitzero.sh runner.py

# 7. Instalar binarios en el sistema con nombres renombrados
echo "📦 Instalando binarios en el sistema..."
cp bitzero_32.so "$PREFIX/lib/bitzero.cpython-313-arm-linux-androideabi.so"
cp bitzero_64.so "$PREFIX/lib/bitzero.cpython-313-aarch64-linux-android.so"
cp bitzero.sh $PREFIX/bin/bitzero
chmod +x $PREFIX/bin/bitzero

echo "✅ Binarios instalados correctamente"

# 7.1. Detectar arquitectura e informar al usuario
ARCH=$(uname -m)
echo ""
if [ "$ARCH" = "aarch64" ]; then
    echo "🖥️ Arquitectura detectada: 64-bit (aarch64) → usando bitzero.cpython-313-aarch64-linux-android.so"
else
    echo "🖥️ Arquitectura detectada: 32-bit (armv8l/armeabi-v7a) → usando bitzero.cpython-313-arm-linux-androideabi.so"
fi
echo ""

# 8. Crear script de inicio apuntando a ZEROX_WORD
echo "📝 Creando script de inicio..."
cat > ~/iniciar_downloader.sh << EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$INSTALL_DIR/Downloader_Web"
python app.py
EOF
chmod +x ~/iniciar_downloader.sh

# 9. Crear comandos rápidos
echo "📝 Creando comandos rápidos..."
if ! grep -q "Comandos para Downloader Web" ~/.bashrc; then
cat >> ~/.bashrc << 'EOF'

# Comandos para Downloader Web
alias Downloader='~/iniciar_downloader.sh'
alias downloader='~/iniciar_downloader.sh'
alias dw-start='~/iniciar_downloader.sh'
alias dw-stop='pkill -f "python app.py"'
alias dw-status='ps aux | grep "python app.py" | grep -v grep'
EOF
fi

# 10. Cargar los comandos
source ~/.bashrc

echo ""
echo "✅ ¡INSTALACIÓN COMPLETA!"
echo ""
echo "📂 Archivos instalados en:"
echo "   $INSTALL_DIR/Downloader_Web"
echo ""
echo "📋 COMANDOS DISPONIBLES:"
echo "   Downloader   → Iniciar el servidor"
echo "   dw-start     → Iniciar el servidor"
echo "   dw-stop      → Detener el servidor"
echo "   dw-status    → Ver si el servidor está corriendo"
echo ""
echo "🌐 Accede a: http://127.0.0.1:5000"
echo ""
echo "🚀 Para iniciar ahora mismo, ejecuta: Downloader"