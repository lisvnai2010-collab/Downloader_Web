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
pkg install python clang binutils -y
pip install flask requests beautifulsoup4 urllib3

# 4. Clonar repositorio
echo "📥 Descargando el Downloader Web..."
cd ~/
rm -rf Downloader_Web

# ✅ TU REPOSITORIO
git clone https://github.com/lisvnai2010-collab/Downloader_Web.git Downloader_Web

# 5. Dar permisos a los binarios
echo "🔓 Dando permisos..."
cd ~/Downloader_Web
chmod +x bitzero_32.bin bitzero_64.bin bitzero.sh

# 5.5. Instalar binarios en el sistema
echo "📦 Instalando binarios en el sistema..."
cp bitzero_32.bin $PREFIX/bin/
cp bitzero_64.bin $PREFIX/bin/
cp bitzero.sh $PREFIX/bin/bitzero
chmod +x $PREFIX/bin/bitzero $PREFIX/bin/bitzero_32.bin $PREFIX/bin/bitzero_64.bin
echo "✅ Binarios instalados correctamente"

# 6. Crear script de inicio
echo "📝 Creando script de inicio..."
cat > ~/iniciar_downloader.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/Downloader_Web
python app.py
EOF
chmod +x ~/iniciar_downloader.sh

# 7. Crear comandos rápidos
echo "📝 Creando comandos rápidos..."
cat >> ~/.bashrc << 'EOF'

# Comandos para Downloader Web
alias downloader='~/iniciar_downloader.sh'
alias dw-start='~/iniciar_downloader.sh'
alias dw-stop='pkill -f "python app.py"'
alias dw-status='ps aux | grep "python app.py" | grep -v grep'
EOF

# 8. Cargar los comandos
source ~/.bashrc

echo ""
echo "✅ ¡INSTALACIÓN COMPLETA!"
echo ""
echo "📋 COMANDOS DISPONIBLES:"
echo "   downloader   → Iniciar el servidor"
echo "   dw-start     → Iniciar el servidor"
echo "   dw-stop      → Detener el servidor"
echo "   dw-status    → Ver si el servidor está corriendo"
echo ""
echo "🌐 Accede a: http://127.0.0.1:5000"
echo ""
echo "🚀 Para iniciar ahora mismo, ejecuta: downloader"chmod +x bitzero

# 6. Crear script de inicio
echo "📝 Creando script de inicio..."
cat > ~/iniciar_downloader.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/Downloader_Web
python app.py
EOF
chmod +x ~/iniciar_downloader.sh

# 7. Crear comandos rápidos
echo "📝 Creando comandos rápidos..."
cat >> ~/.bashrc << 'EOF'

# Comandos para Downloader Web
alias downloader='~/iniciar_downloader.sh'
alias dw-start='~/iniciar_downloader.sh'
alias dw-stop='pkill -f "python app.py"'
alias dw-status='ps aux | grep "python app.py" | grep -v grep'
EOF

# 8. Cargar los comandos
source ~/.bashrc

echo ""
echo "✅ ¡INSTALACIÓN COMPLETA!"
echo ""
echo "📋 COMANDOS DISPONIBLES:"
echo "   downloader   → Iniciar el servidor"
echo "   dw-start     → Iniciar el servidor"
echo "   dw-stop      → Detener el servidor"
echo "   dw-status    → Ver si el servidor está corriendo"
echo ""
echo "🌐 Accede a: http://127.0.0.1:5000"
echo ""
echo "🚀 Para iniciar ahora mismo, ejecuta: downloader"
