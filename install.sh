#!/data/data/com.termux/files/usr/bin/bash

# ============================================
# INSTALADOR DE BOT DE APK
# ============================================

echo "🚀 Iniciando instalación del Bot..."
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
echo "📥 Descargando el bot..."
cd ~/
rm -rf BOT-DE-APK

# ⚠️ CAMBIA ESTO POR TU REPOSITORIO
git clone https://github.com/TU_USUARIO/TU-REPOSITORIO.git BOT-DE-APK
# ----------------------------------------

# 5. Dar permisos al binario
echo "🔓 Dando permisos..."
cd ~/BOT-DE-APK
chmod +x bitzero

# 6. Crear script de inicio
echo "📝 Creando script de inicio..."
cat > ~/iniciar_bot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/BOT-DE-APK
python app.py
EOF
chmod +x ~/iniciar_bot.sh

# 7. Crear comandos rápidos
echo "📝 Creando comandos rápidos..."
cat >> ~/.bashrc << 'EOF'

# Comandos para el Bot
alias bot='~/iniciar_bot.sh'
alias bot-start='~/iniciar_bot.sh'
alias bot-stop='pkill -f "python app.py"'
alias bot-status='ps aux | grep "python app.py" | grep -v grep'
EOF

# 8. Cargar los comandos
source ~/.bashrc

echo ""
echo "✅ ¡INSTALACIÓN COMPLETA!"
echo ""
echo "📋 COMANDOS DISPONIBLES:"
echo "   bot          → Iniciar el servidor"
echo "   bot-start    → Iniciar el servidor"
echo "   bot-stop     → Detener el servidor"
echo "   bot-status   → Ver si el servidor está corriendo"
echo ""
echo "🌐 Accede a: http://127.0.0.1:5000"
echo ""
echo "🚀 Para iniciar el bot ahora mismo, ejecuta: bot"
