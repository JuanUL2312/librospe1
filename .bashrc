
# Alias para gestionar bloqueos
alias ver_bloqueos='cd ~/www && source venv/bin/activate && python3 -c "from app import app, db, IntentosLogin; from datetime import datetime; ahora=datetime.now(); [print(f\"🔒 {b.email} - IP: {b.ip}\") for b in IntentosLogin.query.all() if (b.email_bloqueado and b.email_bloqueado>ahora) or (b.ips_bloqueadas and b.ips_bloqueadas>ahora)] or print(\"✅ No hay bloqueos\")"'

alias desbloquear_todo='cd ~/www && source venv/bin/activate && python3 -c "from app import app, db, IntentosLogin; IntentosLogin.query.update({\"email_bloqueado\": None, \"ips_bloqueadas\": None, \"intentos\": 0}); db.session.commit(); print(\"✅ Todos los bloqueos eliminados\")"'

alias reiniciar_bloqueos='cd ~/www && source venv/bin/activate && python3 reiniciar_bloqueos.py'

alias restart='touch ~/www/tmp/restart.txt && echo "✅ App reiniciada"'

alias status='ps aux | grep passenger | grep -v grep | wc -l && echo "procesos Passenger activos"'

# Scripts para gestionar bloqueos
alias ver_bloqueos='cd ~/www && python3 ver_bloqueos.py'
alias desbloquear_todo='cd ~/www && python3 desbloquear_todo.py'
alias reiniciar_bloqueos='cd ~/www && python3 reiniciar_bloqueos.py'
alias desbloquear_ip='cd ~/www && python3 desbloquear_ip.py'
alias desbloquear_email='cd ~/www && python3 desbloquear_email.py'

# =============================================
# ALIASES PARA LIBROS-PE
# =============================================

# Sincronización
alias sincronizar='~/sincronizar_completo.sh'
alias verificar='~/verificar_sincronizacion.sh'
alias programar='~/programar_sincronizacion.sh'

# Logs
alias logs='tail -f ~/sincronizacion.log'
alias ultimo_log='tail -20 ~/sincronizacion.log'

# Reinicio
alias reiniciar='~/restart.sh'
alias status='~/check_restart.sh'

# Base de datos
alias db='mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db'
alias db_consulta='mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e'

echo "📚 Aliases cargados para LibrosPE"
