cd ~/www
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
# 3. Esperar
sleep 5
# 4. Probar login
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=123456"   -L 2>&1 | grep -E "Bienvenido|BLOQUEADA|catalogo"
# Probar con respuesta completa
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=123456"   -L -v 2>&1 | head -50
# Ver logs de Flask
tail -30 ~/www/app.log
# 1. Verificar que el cliente está bloqueado
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, motivo, estado FROM bloqueos WHERE cliente_id = 1 AND tipo_usuario = 'cliente';
"
# 2. Probar login
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=123456"   -L 2>&1 | grep -E "Bienvenido|BLOQUEADA|Motivo|catalogo"
# Probar con respuesta completa
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=123456"   -L 2>&1 | head -50
tail -30 ~/www/app.log
# Verificar la línea 668
sed -n '660,680p' ~/www/app.py | grep -A 10 "bloqueo = db.session.execute"
# Verificar la línea 668
sed -n '660,680p' ~/www/app.py | grep -A 10 "bloqueo = db.session.execute"
(venv) librospe@ssh1:~/www$ # Verificar la línea 668
sed -n '660,680p' ~/www/app.py | grep -A 10 "bloqueo = db.session.execute"
(venv) librospe@ssh1:~/www$ # Verificar la línea 668
sed -n '660,680p' ~/www/app.py | grep -A 10 "bloqueo = db.session.execute"
(venv) librospe@ssh1:~/www$ 
(venv) librospe@ssh1:~/www$ # Verificar la línea 668
sed -n '660,680p' ~/www/app.py | grep -A 10 "bloqueo = db.session.execute"
(venv) librospe@ssh1:~/www$ # Verificar la línea 668
sed -n '660,680p' ~/www/app.py | grep -A 10 "bloqueo = db.session.execute"
(venv) librospe@ssh1:~/www$ # Buscar la función login_cliente
grep -n "def login_cliente" ~/www/app.py
# Buscar la consulta de bloqueo
grep -n "bloqueo = db.session.execute" ~/www/app.py
# 1. Corregir la primera consulta (login_cliente)
sed -i '658s/.*/        bloqueo = db.session.execute(text("""SELECT id, motivo, fecha_bloqueo FROM bloqueos WHERE cliente_id = :cliente_id AND tipo_usuario = '\''cliente'\'' AND estado = 1"""), {"cliente_id": cliente.id}).mappings().first()/' ~/www/app.py
# 2. Corregir la segunda consulta (si existe)
sed -i '1215s/.*/        bloqueo = db.session.execute(text("""SELECT id, motivo, fecha_bloqueo FROM bloqueos WHERE cliente_id = :cliente_id AND tipo_usuario = '\''cliente'\'' AND estado = 1"""), {"cliente_id": cliente.id}).mappings().first()/' ~/www/app.py
# Verificar la línea 658
sed -n '655,665p' ~/www/app.py
# Verificar la línea 1215
sed -n '1212,1222p' ~/www/app.py
# 1. Matar Flask
pkill -9 -f "python app.py"
# 2. Ejecutar
cd ~/www
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
# 3. Esperar
sleep 5
# 4. Probar login de cliente bloqueado
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=123456"   -L 2>&1 | grep -E "Bienvenido|BLOQUEADA|Motivo"
cat ~/www/app.log
# 1. Matar Flask
pkill -9 -f "python app.py"
# 2. Ejecutar
cd ~/www
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
# 3. Esperar
sleep 5
# 4. Probar
curl -X POST http://127.7.55.226:8000/bloqueos/desbloquear/1   -b cookies.txt   -H "Content-Type: application/json"   -L 2>&1 | head -20
# Ver todos los bloqueos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, usuario_sistema_id, tipo_usuario, motivo, estado FROM bloqueos;
"
# Desbloquear el bloqueo con ID 3
curl -X POST http://127.7.55.226:8000/bloqueos/desbloquear/3   -b cookies.txt   -H "Content-Type: application/json"   -L 2>&1 | grep -E "success|error|message"
# Ver bloqueos activos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, usuario_sistema_id, tipo_usuario, motivo, estado FROM bloqueos WHERE estado = 1;
"
# Bloquear al cliente 1 (pedro luna)
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
INSERT INTO bloqueos (tipo_usuario, cliente_id, motivo, fecha_bloqueo, bloqueado_por, estado)
VALUES ('cliente', 1, 'Prueba de bloqueo - Cliente por actividad sospechosa', NOW(), 1, 1);
"
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, motivo, estado FROM bloqueos WHERE estado = 1;
"
# Verificar que la función existe
grep -n "def registrar_intento_fallido" ~/www/app.py
# Ver la función login_cliente
grep -A 80 "def login_cliente()" ~/www/app.py | head -85
# 1. Limpiar intentos previos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
DELETE FROM intentos_login WHERE email = 'cliente@mail.com';
"
# 2. Probar 3 intentos fallidos
for i in 1 2 3; do     echo "========== INTENTO $i ==========";     curl -X POST http://127.7.55.226:8000/login-cliente       -d "email=cliente@mail.com&clave=clave_incorrecta"       -L 2>&1 | grep -E "incorrecta|BLOQUEADA|quedan";     echo ""; done
# 3. Verificar el bloqueo en la base de datos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT email, intentos, email_bloqueado, ips_bloqueadas FROM intentos_login WHERE email = 'cliente@mail.com';
"
# Intentar login con el cliente bloqueado (con su contraseña correcta)
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=123456"   -L 2>&1 | grep -E "BLOQUEADA|Motivo"
# Verificar bloqueos en la tabla
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, motivo, estado FROM bloqueos WHERE cliente_id = 1;
"
# Ver el último registro de intentos_login
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, email, intentos, email_bloqueado FROM intentos_login ORDER BY id DESC LIMIT 5;
"
# Verificar si existe en bloqueos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, tipo_usuario, motivo, estado FROM bloqueos WHERE cliente_id = 1 AND tipo_usuario = 'cliente';
"
# Crear bloqueo para que aparezca en el panel
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
INSERT INTO bloqueos (tipo_usuario, cliente_id, motivo, fecha_bloqueo, bloqueado_por, estado)
VALUES ('cliente', 1, 'Bloqueo automático por 3 intentos fallidos de login', NOW(), 1, 1);
"
# Verificar
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, motivo, estado FROM bloqueos WHERE cliente_id = 1;
"
# 1. Matar Flask
pkill -9 -f "python app.py"
# 2. Ejecutar
cd ~/www
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
# 3. Esperar
sleep 5
# 4. Probar
curl -b cookies.txt http://127.7.55.226:8000/bloqueos | grep -E "Manual|Automático|Origen" | head -10
# Verificar la API de bloqueos
curl -b cookies.txt http://127.7.55.226:8000/api/bloqueos
# 1. Matar Flask
pkill -9 -f "python app.py"
# 2. Ejecutar
cd ~/www
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
# 3. Esperar
sleep 5
# 4. Probar la API
curl -b cookies.txt http://127.7.55.226:8000/api/bloqueos | python -m json.tool
# 5. Contar los bloqueos
curl -b cookies.txt http://127.7.55.226:8000/api/bloqueos | python -c "import sys, json; print(len(json.load(sys.stdin)))"
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, email, intentos, email_bloqueado FROM intentos_login 
WHERE email_bloqueado IS NOT NULL AND email_bloqueado > NOW();
"
# 1. Limpiar intentos previos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
DELETE FROM intentos_login WHERE email = 'cliente@mail.com';
"
# 2. Probar 3 intentos fallidos
echo "========== INTENTO 1 =========="
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=clave_incorrecta"   -L 2>&1 | grep -E "incorrecta|BLOQUEADA|quedan"
echo "========== INTENTO 2 =========="
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=clave_incorrecta"   -L 2>&1 | grep -E "incorrecta|BLOQUEADA|quedan"
echo "========== INTENTO 3 =========="
curl -X POST http://127.7.55.226:8000/login-cliente   -d "email=cliente@mail.com&clave=clave_incorrecta"   -L 2>&1 | grep -E "incorrecta|BLOQUEADA|quedan"
# 3. Verificar el bloqueo
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, email, intentos, email_bloqueado FROM intentos_login WHERE email = 'cliente@mail.com';
"
curl -b cookies.txt http://127.7.55.226:8000/api/bloqueos | python -m json.tool
# 1. Desbloquear al cliente manualmente
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
UPDATE bloqueos SET estado = 0, fecha_desbloqueo = NOW() WHERE cliente_id = 1 AND tipo_usuario = 'cliente' AND estado = 1;
"
# 2. Verificar que el cliente está desbloqueado
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, cliente_id, motivo, estado FROM bloqueos WHERE cliente_id = 1 AND tipo_usuario = 'cliente';
"
# 3. Limpiar intentos previos
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
DELETE FROM intentos_login WHERE email = 'cliente@mail.com';
"
# 4. Probar 3 intentos fallidos
for i in 1 2 3; do     echo "========== INTENTO $i ==========";     curl -X POST http://127.7.55.226:8000/login-cliente       -d "email=cliente@mail.com&clave=clave_incorrecta"       -L 2>&1 | grep -E "incorrecta|BLOQUEADA|quedan";     echo ""; done
# 5. Verificar bloqueo en intentos_login
mysql -u librospe -p75535870 -h mysql-librospe.alwaysdata.net librospe_db -e "
SELECT id, email, intentos, email_bloqueado FROM intentos_login WHERE email = 'cliente@mail.com';
"
# 6. Verificar API
curl -b cookies.txt http://127.7.55.226:8000/api/bloqueos | python -m json.tool
# 7. Contar bloqueos
curl -b cookies.txt http://127.7.55.226:8000/api/bloqueos | python -c "import sys, json; print(len(json.load(sys.stdin)))"
# 1. Matar Flask
pkill -9 -f "python app.py"
# 2. Ejecutar
cd ~/www
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
# 3. Esperar
sleep 5
# 4. Probar
curl -b cookies.txt http://127.7.55.226:8000/bloqueos-sistema | grep -E "Usuarios del Sistema|bloqueados" | head -5
head -20 ~/www/app.py | grep datetime
# Ver los últimos errores
tail -100 ~/logs/error.log
# Buscar archivos .log en todo el home
find ~ -name "*.log" 2>/dev/null
# Buscar en la carpeta www
find ~/www -name "*.log" 2>/dev/null
# Ver la estructura de tu directorio
ls -la ~/
# Ver la estructura de tu proyecto
ls -la ~/www/
# Ver los logs de Flask
tail -100 ~/www/logs/flask.log
tail -100 ~/admin/logs/uwsgi/1037421.log
tail -50 ~/admin/logs/uwsgi/1037421.log | grep -A 10 -B 10 "ERROR"
tail -100 ~/admin/logs/uwsgi/1037421.log | grep -A 30 "login-cliente"
tail -30 ~/admin/logs/uwsgi/1037421.log
# 1. Eliminar el archivo de caché de Python
find ~/www -name "*.pyc" -delete
# 2. Eliminar el caché de Jinja2 (si existe)
rm -rf ~/www/venv/lib/python3.13/site-packages/jinja2/ext.pyc 2>/dev/null
rm -rf ~/www/__pycache__ 2>/dev/null
rm -rf ~/www/templates/__pycache__ 2>/dev/null
# 3. Verificar el archivo actual
cat ~/www/templates/login_cliente.html | grep -n "intentos" | head -20
# 4. Sobrescribir el archivo con una versión muy simple
cat > ~/www/templates/login_cliente.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Login Cliente</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-primary text-white text-center">
                        <h4>📚 Librería Salesiana</h4>
                        <small>Inicia sesión para comprar</small>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                        {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">
                            {{ message }}
                        </div>
                        {% endfor %}
                        {% endif %}
                        {% endwith %}

                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Correo Electrónico</label>
                                <input type="email" name="email" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Contraseña</label>
                                <input type="password" name="clave" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Iniciar Sesión</button>
                        </form>
                    </div>
                    <div class="card-footer text-center">
                        <small>¿No tienes cuenta? <a href="/registro-cliente">Regístrate</a></small>
                        <br>
                        <small><a href="/catalogo">← Seguir comprando como invitado</a></small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
EOF

# 5. Forzar reinicio del servidor
sudo supervisorctl restart 1037421
# 6. Esperar 2 segundos
sleep 2
# 7. Verificar que el servidor se reinició
tail -20 ~/admin/logs/uwsgi/1037421.log
# Reemplazar el template con una versión que NO use variables None
cat > ~/www/templates/login_cliente.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Login Cliente</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-primary text-white text-center">
                        <h4>📚 Librería Salesiana</h4>
                        <small>Inicia sesión para comprar</small>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                        {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">
                            {{ message }}
                        </div>
                        {% endfor %}
                        {% endif %}
                        {% endwith %}

                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Correo Electrónico</label>
                                <input type="email" name="email" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Contraseña</label>
                                <input type="password" name="clave" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Iniciar Sesión</button>
                        </form>
                    </div>
                    <div class="card-footer text-center">
                        <small>¿No tienes cuenta? <a href="/registro-cliente">Regístrate</a></small>
                        <br>
                        <small><a href="/catalogo">← Seguir comprando como invitado</a></small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
EOF

# Reiniciar
sudo supervisorctl restart 1037421
sleep 3
tail -20 ~/admin/logs/uwsgi/1037421.log
# Reemplazar el template con una versión que NO use variables None
cat > ~/www/templates/login_cliente.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Login Cliente</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-primary text-white text-center">
                        <h4>📚 Librería Salesiana</h4>
                        <small>Inicia sesión para comprar</small>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                        {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">
                            {{ message }}
                        </div>
                        {% endfor %}
                        {% endif %}
                        {% endwith %}

                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Correo Electrónico</label>
                                <input type="email" name="email" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Contraseña</label>
                                <input type="password" name="clave" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Iniciar Sesión</button>
                        </form>
                    </div>
                    <div class="card-footer text-center">
                        <small>¿No tienes cuenta? <a href="/registro-cliente">Regístrate</a></small>
                        <br>
                        <small><a href="/catalogo">← Seguir comprando como invitado</a></small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
EOF

# Reiniciar
sudo supervisorctl restart 1037421
sleep 3
tail -20 ~/admin/logs/uwsgi/1037421.log
# 1. Eliminar el template problemático
rm -f ~/www/templates/login_cliente.html
# 2. Crear un nuevo template simple
nano ~/www/templates/login_cliente.html
# Guardar: Ctrl+O, Enter, luego Ctrl+X
# Reiniciar la aplicación
touch ~/www/tmp/restart.txt
# Esperar 2 segundos
sleep 2
# Verificar el log
tail -20 ~/admin/logs/uwsgi/1037421.log
# Ver qué archivo existe realmente
ls -la ~/www/templates/login_cliente.html
cat ~/www/templates/login_cliente.html | head -20
# Si el archivo existe, elimínalo y crea uno nuevo con echo
rm -f ~/www/templates/login_cliente.html
# Crear un archivo nuevo usando echo línea por línea
echo '<!DOCTYPE html>' > ~/www/templates/login_cliente.html
echo '<html>' >> ~/www/templates/login_cliente.html
echo '<head>' >> ~/www/templates/login_cliente.html
echo '    <title>Login Cliente</title>' >> ~/www/templates/login_cliente.html
echo '    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">' >> ~/www/templates/login_cliente.html
echo '</head>' >> ~/www/templates/login_cliente.html
echo '<body>' >> ~/www/templates/login_cliente.html
echo '    <div class="container mt-5">' >> ~/www/templates/login_cliente.html
echo '        <div class="row justify-content-center">' >> ~/www/templates/login_cliente.html
echo '            <div class="col-md-4">' >> ~/www/templates/login_cliente.html
echo '                <div class="card">' >> ~/www/templates/login_cliente.html
echo '                    <div class="card-header bg-primary text-white text-center">' >> ~/www/templates/login_cliente.html
echo '                        <h4>📚 Librería Salesiana</h4>' >> ~/www/templates/login_cliente.html
echo '                        <small>Inicia sesión para comprar</small>' >> ~/www/templates/login_cliente.html
echo '                    </div>' >> ~/www/templates/login_cliente.html
echo '                    <div class="card-body">' >> ~/www/templates/login_cliente.html
echo '                        <form method="POST">' >> ~/www/templates/login_cliente.html
echo '                            <div class="mb-3">' >> ~/www/templates/login_cliente.html
echo '                                <label class="form-label">Correo Electrónico</label>' >> ~/www/templates/login_cliente.html
echo '                                <input type="email" name="email" class="form-control" required>' >> ~/www/templates/login_cliente.html
echo '                            </div>' >> ~/www/templates/login_cliente.html
echo '                            <div class="mb-3">' >> ~/www/templates/login_cliente.html
echo '                                <label class="form-label">Contraseña</label>' >> ~/www/templates/login_cliente.html
echo '                                <input type="password" name="clave" class="form-control" required>' >> ~/www/templates/login_cliente.html
echo '                            </div>' >> ~/www/templates/login_cliente.html
echo '                            <button type="submit" class="btn btn-primary w-100">Iniciar Sesión</button>' >> ~/www/templates/login_cliente.html
echo '                        </form>' >> ~/www/templates/login_cliente.html
echo '                    </div>' >> ~/www/templates/login_cliente.html
echo '                    <div class="card-footer text-center">' >> ~/www/templates/login_cliente.html
echo '                        <small>¿No tienes cuenta? <a href="/registro-cliente">Regístrate aquí</a></small>' >> ~/www/templates/login_cliente.html
echo '                        <br>' >> ~/www/templates/login_cliente.html
echo '                        <small><a href="/catalogo">← Seguir comprando como invitado</a></small>' >> ~/www/templates/login_cliente.html
echo '                    </div>' >> ~/www/templates/login_cliente.html
echo '                </div>' >> ~/www/templates/login_cliente.html
echo '            </div>' >> ~/www/templates/login_cliente.html
echo '        </div>' >> ~/www/templates/login_cliente.html
echo '    </div>' >> ~/www/templates/login_cliente.html
echo '</body>' >> ~/www/templates/login_cliente.html
echo '</html>' >> ~/www/templates/login_cliente.html
# Verificar que el archivo se creó
head -10 ~/www/templates/login_cliente.html
# Reiniciar la aplicación
touch ~/www/tmp/restart.txt
sleep 2
# Ver los logs
tail -30 ~/admin/logs/uwsgi/1037421.log
# 1. Verificar que el template simple existe y es correcto
wc -l ~/www/templates/login_cliente.html
cat ~/www/templates/login_cliente.html
# 2. Forzar reinicio completo de uWSGI
sudo supervisorctl stop 1037421
sleep 3
sudo supervisorctl start 1037421
sleep 3
# 3. Verificar el log
tail -30 ~/admin/logs/uwsgi/1037421.log
# 1. Reiniciar mediante el archivo de touch
touch ~/www/tmp/restart.txt
# 2. También puedes reiniciar uWSGI tocando el archivo de configuración
touch ~/admin/config/uwsgi/1037421.conf
# 3. Esperar 5 segundos
sleep 5
# 4. Verificar los logs
tail -30 ~/admin/logs/uwsgi/1037421.log
# 1. Eliminar todos los archivos .pyc
find ~/www -name "*.pyc" -delete
# 2. Eliminar el caché de Jinja2
rm -rf ~/www/templates/__pycache__
# 3. Eliminar el caché de la aplicación
rm -rf ~/www/__pycache__
# 4. Reiniciar
touch ~/www/tmp/restart.txt
sleep 3
# 5. Verificar logs
tail -20 ~/admin/logs/uwsgi/1037421.log
ls
cd www
ls
cd templates
nano login_cliente.html
nano login_cliente.html
mysql -u librospe -p -h mysql-librospe.alwaysdata.net librospe_db
mysql -u librospe -p -h mysql-librospe.alwaysdata.net librospe_db
grep -n "pedidos" ~/www/app.py | grep -i "count"
grep -n "def ver_pedidos" ~/www/app.py
sed -n '2819,2900p' ~/www/app.py
pip install python-dotenv
nano .env
