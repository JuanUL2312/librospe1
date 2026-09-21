
// ============================================
// MÉTODO DE PAGO Y CÁLCULO DE VUELTO
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    const metodoPago = document.getElementById('metodo_pago');
    const montoRecibido = document.getElementById('monto_recibido');
    const vueltoSection = document.getElementById('vueltoSection');
    const totalDisplay = document.getElementById('total_display');
    const vueltoInfo = document.getElementById('vueltoInfo');

    function actualizarVuelto() {
        const total = parseFloat(totalDisplay.value) || 0;
        const recibido = parseFloat(montoRecibido.value) || 0;
        const vuelto = recibido - total;
        if (recibido > 0) {
            if (vuelto >= 0) {
                vueltoInfo.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fas fa-hand-holding-usd me-1"></i>Vuelto: <strong>S/. ' + vuelto.toFixed(2) + '</strong></div>';
            } else {
                vueltoInfo.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fas fa-exclamation-triangle me-1"></i>Falta: <strong>S/. ' + Math.abs(vuelto).toFixed(2) + '</strong></div>';
            }
        } else {
            vueltoInfo.innerHTML = '';
        }
    }

    function toggleVuelto() {
        if (metodoPago.value === 'efectivo') {
            vueltoSection.style.display = 'block';
            actualizarVuelto();
        } else {
            vueltoSection.style.display = 'none';
            vueltoInfo.innerHTML = '';
        }
    }

    metodoPago.addEventListener('change', toggleVuelto);
    montoRecibido.addEventListener('input', actualizarVuelto);
    totalDisplay.addEventListener('change', actualizarVuelto);
    toggleVuelto();
});
