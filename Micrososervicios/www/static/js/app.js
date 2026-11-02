
    // ============================================
    // ACTUALIZAR CONTADOR DE USUARIOS BLOQUEADOS
    // ============================================
    function actualizarContadorBloqueos() {
        const contador = document.getElementById('contador-bloqueos');
        if (!contador) return;
        
        fetch('/api/bloqueos')
            .then(response => response.json())
            .then(data => {
                const cantidad = data.length || 0;
                contador.textContent = cantidad;
                if (cantidad > 0) {
                    contador.style.display = 'inline';
                } else {
                    contador.style.display = 'none';
                }
            })
            .catch(error => console.error('Error al obtener bloqueos:', error));
    }

    // Actualizar al cargar la página
    document.addEventListener('DOMContentLoaded', function() {
        actualizarContadorBloqueos();
    });

    // Actualizar cada 30 segundos
    setInterval(actualizarContadorBloqueos, 30000);



        document.addEventListener('DOMContentLoaded', function() {
            // ============================================
            // SIDEBAR: ALTURA REAL DE LA NAVBAR (--nav-h)
            // ============================================
            function ajustarNavH() {
                const nav = document.querySelector('.navbar');
                if (nav) {
                    document.documentElement.style.setProperty('--nav-h', nav.offsetHeight + 'px');
                }
            }
            ajustarNavH();
            window.addEventListener('resize', ajustarNavH);

            // ============================================
            // MENU LATERAL: MARCAR LA PAGINA ACTUAL
            // ============================================
            document.querySelectorAll('.admin-dashboard-grid a[href]').forEach(function(a) {
                try {
                    if (a.getAttribute('href') && new URL(a.href, location.origin).pathname === location.pathname) {
                        a.classList.add('active');
                    }
                } catch (e) { /* href invalido */ }
            });

            // ============================================
            // EFECTO DE SOMBRA AL HACER SCROLL
            // ============================================
            const panel = document.getElementById('panelSalesiano');
            if (panel) {
                window.addEventListener('scroll', function() {
                    if (window.scrollY > 10) {
                        panel.classList.add('scrolled');
                    } else {
                        panel.classList.remove('scrolled');
                    }
                });
            }

            // ============================================
            // FECHA Y HORA ACTUAL
            // ============================================
            const now = new Date();
            function partesPeru(fecha) {
                return Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
                    timeZone: 'America/Lima', year: 'numeric', month: '2-digit',
                    day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
                }).formatToParts(fecha).map(({type, value}) => [type, value]));
            }
            const actual = partesPeru(now);
            const year = actual.year;
            const month = actual.month;
            const day = actual.day;
            const hour = actual.hour;
            const min = actual.minute;
            const datetimeLocal = `${year}-${month}-${day}T${hour}:${min}`;

            const fechaHoraInput = document.getElementById('fecha_hora');
            if (fechaHoraInput) {
                fechaHoraInput.value = datetimeLocal;
            }

            const tomorrow = partesPeru(new Date(now.getTime() + 24 * 60 * 60 * 1000));
            const maxDate = `${tomorrow.year}-${tomorrow.month}-${tomorrow.day}T23:59`;
            if (fechaHoraInput) {
                fechaHoraInput.max = maxDate;
            }

            // ============================================
            // DROP ZONE PARA IMÁGENES
            // ============================================
            const dropZone = document.getElementById('dropZone');
            const fileInput = document.getElementById('imagenInput');

            if (dropZone && fileInput) {
                ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => {
                    dropZone.addEventListener(e, e => {
                        e.preventDefault();
                        e.stopPropagation();
                    });
                });

                ['dragenter', 'dragover'].forEach(e => {
                    dropZone.addEventListener(e, () => dropZone.classList.add('drag-over'));
                });

                ['dragleave', 'drop'].forEach(e => {
                    dropZone.addEventListener(e, () => dropZone.classList.remove('drag-over'));
                });

                dropZone.addEventListener('drop', e => {
                    const files = e.dataTransfer.files;
                    handleFile(files[0]);
                });

                fileInput.addEventListener('change', e => {
                    handleFile(e.target.files[0]);
                });

                function handleFile(file) {
                    if (!file) return;

                    if (!file.type.startsWith('image/')) {
                        alert('❌ Solo imágenes');
                        return;
                    }

                    if (file.size > 5 * 1024 * 1024) {
                        alert('❌ Máximo 5MB');
                        return;
                    }

                    const dt = new DataTransfer();
                    dt.items.add(file);
                    fileInput.files = dt.files;

                    const reader = new FileReader();
                    reader.onload = e => {
                        const preview = document.querySelector('.dropzone-preview');
                        if (preview) {
                            preview.innerHTML = `
                                <div style="text-align:center;padding:15px;background:#d4edda;border-radius:8px;">
                                    <img src="${e.target.result}" style="max-height:150px;border-radius:8px;">
                                    <br><strong style="color:#155724;">${file.name}</strong>
                                    <br><small>${(file.size / 1024 / 1024).toFixed(1)}MB ✅</small>
                                    <br><button type="button" 
                                        onclick="document.getElementById('imagenInput').value='';this.parentElement.parentElement.innerHTML='';"
                                        style="background:#dc3545;color:white;border:none;border-radius:4px;padding:5px 10px;margin-top:10px;cursor:pointer;">
                                        🗑️ Limpiar
                                    </button>
                                </div>
                            `;
                        }
                    };
                    reader.readAsDataURL(file);
                }
            }
        });
    