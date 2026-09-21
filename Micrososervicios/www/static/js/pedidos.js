
    async function cambiarEstado(event, select) {
        // Prevenir cualquier comportamiento por defecto (recarga de página)
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        
        const pedidoId = select.dataset.pedidoId;
        const nuevoEstado = select.value;
        const oldValue = select.dataset.oldValue;
        
        // Si el estado no cambió, no hacer nada
        if (nuevoEstado === oldValue) {
            return false;
        }
        
        // Deshabilitar select durante la petición
        select.disabled = true;
        select.style.opacity = '0.6';
        
        console.log('📤 Cambiando pedido:', pedidoId, 'a:', nuevoEstado);
        
        // Si es delivery y se marca como "Entregado", pedir constancia de entrega
        let extra = '';
        if (nuevoEstado === 'entregado') {
            const { value: datosRecibo } = await Swal.fire({
                title: '🎁 Confirmar entrega (Delivery)',
                html: `
                    <p style="font-size:14px;text-align:left">El pedido es <strong>Delivery</strong>. Ingresa quién recibió el pedido:</p>
                    <input id="nombreRecibe" class="swal2-input" placeholder="Nombre de quien recibió *" autocomplete="off">
                    <input id="dniRecibe" class="swal2-input" placeholder="DNI de quien recibió (opcional)" maxlength="8" autocomplete="off">
                `,
                showCancelButton: true,
                confirmButtonText: '✅ Confirmar entrega',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#28a745',
                preConfirm: () => {
                    const nombre = document.getElementById('nombreRecibe').value.trim();
                    if (!nombre) {
                        Swal.showValidationMessage('Ingresa el nombre de quien recibió el pedido');
                        return false;
                    }
                    return { nombre: nombre, dni: document.getElementById('dniRecibe').value.trim() };
                }
            });
            
            if (!datosRecibo || !datosRecibo.nombre) {
                select.value = oldValue || 'pendiente';
                select.disabled = false;
                select.style.opacity = '';
                return false;
            }
            extra = '&nombre_recibe=' + encodeURIComponent(datosRecibo.nombre) +
                    '&dni_recibe=' + encodeURIComponent(datosRecibo.dni || '');
        }
        
        // Enviar petición AJAX
        try {
            const response = await fetch(`/pedidos/cambiar-estado/${pedidoId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `estado=${nuevoEstado}${extra}`
            });
            
            let data;
            try {
                data = await response.json();
            } catch (e) {
                throw new Error('Error en la respuesta del servidor');
            }
            
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Error al actualizar el estado');
            }
            
            // Actualizar el badge de estado en la fila
            const row = document.getElementById(`pedido-${pedidoId}`);
            if (row) {
                const badge = row.querySelector('.estado-badge');
                if (badge) {
                    const estadosMap = {
                        'pendiente': { text: '⏳ Pendiente', class: 'bg-warning' },
                        'confirmado': { text: '✅ Confirmado', class: 'bg-info' },
                        'preparando': { text: '📦 Preparando', class: 'bg-primary' },
                        'enviado': { text: '🚚 Enviado', class: 'bg-info' },
                        'listo_tienda': { text: '🏪 Listo', class: 'bg-success' },
                        'entregado': { text: '🎁 Entregado', class: 'bg-success' },
                        'recogido': { text: '🙌 Recogido', class: 'bg-success' },
                        'cancelado': { text: '❌ Cancelado', class: 'bg-danger' }
                    };
                    const info = estadosMap[nuevoEstado] || { text: nuevoEstado, class: 'bg-secondary' };
                    badge.textContent = info.text;
                    badge.className = `badge estado-badge ${info.class} fs-6 px-2 px-md-3 py-1 py-md-2`;
                }
            }
            
            select.dataset.oldValue = nuevoEstado;
            mostrarNotificacion('✅ ' + data.message, 'success');
            
            // Actualizar contadores
            actualizarContadores();
        } catch (error) {
            console.error('❌ Error:', error);
            select.value = oldValue || 'pendiente';
            mostrarNotificacion('❌ Error: ' + error.message, 'danger');
        } finally {
            select.disabled = false;
            select.style.opacity = '1';
        }
        
        return false;
    }

    function mostrarNotificacion(mensaje, tipo) {
        const existing = document.querySelector('.custom-notification');
        if (existing) {
            existing.remove();
        }
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${tipo} alert-dismissible fade show custom-notification`;
        alert.innerHTML = `
            <i class="fas ${tipo === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'} me-2"></i>
            ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert" onclick="this.closest('.custom-notification').remove()"></button>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 3000);
    }

    function actualizarContadores() {
        // Obtener todos los pedidos de la tabla
        const filas = document.querySelectorAll('#tablaPedidos .pedido-row');
        let total = filas.length;
        let pendientes = 0;
        let completados = 0;
        let enProceso = 0;
        
        filas.forEach(fila => {
            const badge = fila.querySelector('.estado-badge');
            if (badge) {
                const texto = badge.textContent.trim();
                if (texto.includes('Pendiente') || texto.includes('⏳ Pendiente')) {
                    pendientes++;
                } else if (texto.includes('Entregado') || texto.includes('🎁 Entregado') || texto.includes('Recogido') || texto.includes('🙌 Recogido')) {
                    completados++;
                } else if (texto.includes('Confirmado') || texto.includes('✅ Confirmado') || 
                           texto.includes('Preparando') || texto.includes('📦 Preparando') || 
                           texto.includes('Enviado') || texto.includes('🚚 Enviado') || 
                           texto.includes('Listo') || texto.includes('🏪 Listo')) {
                    enProceso++;
                }
            }
        });
        
        // Actualizar contadores en la UI
        const totalPedidos = document.getElementById('totalPedidos');
        const pendientesPedidos = document.getElementById('pendientesPedidos');
        const completadosPedidos = document.getElementById('completadosPedidos');
        const procesoPedidos = document.getElementById('procesoPedidos');
        const totalRegistros = document.getElementById('totalRegistros');
        
        if (totalPedidos) totalPedidos.textContent = total;
        if (pendientesPedidos) pendientesPedidos.textContent = pendientes;
        if (completadosPedidos) completadosPedidos.textContent = completados;
        if (procesoPedidos) procesoPedidos.textContent = enProceso;
        if (totalRegistros) totalRegistros.textContent = total + ' registros';
    }
