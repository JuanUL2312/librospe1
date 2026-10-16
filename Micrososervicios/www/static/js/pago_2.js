
// ===============================
// VARIABLES GLOBALES
// ===============================
let carrito=[];
let checkoutData={};
let metodoSeleccionado=null;
let subtotal=0;
let descuento=0;
let costoEnvio=0;
let cargoContraentrega=0;
let total=0;

// ===============================
// INICIALIZACIÓN
// ===============================
document.addEventListener('DOMContentLoaded',function(){
    cargarDatos();
    verificarTipoEntrega();
    
    const numeroTarjeta = document.getElementById('numeroTarjeta');
    if(numeroTarjeta){
        numeroTarjeta.addEventListener('input', function() { validarTarjetaCompleta(); });
    }
});

// ===============================
// FUNCIONES DE VALIDACIÓN DE TARJETA
// ===============================

function formatearNumeroTarjeta(input) {
    let valor = input.value.replace(/\D/g, '');
    if (valor.length > 16) valor = valor.slice(0, 16);
    let formateado = '';
    for (let i = 0; i < valor.length; i++) {
        if (i > 0 && i % 4 === 0) formateado += ' ';
        formateado += valor[i];
    }
    input.value = formateado;
    validarTarjetaCompleta();
}

function validarTarjetaCompleta() {
    const numeroTarjeta = document.getElementById('numeroTarjeta');
    const tarjetaError = document.getElementById('tarjetaError');
    if (!numeroTarjeta || !tarjetaError) return true;
    const numeros = numeroTarjeta.value.replace(/\s/g, '');
    if (metodoSeleccionado === 'tarjeta') {
        if (numeros.length === 0) { tarjetaError.innerHTML = ''; return false; }
        if (numeros.length < 16) {
            tarjetaError.innerHTML = `<i class="fas fa-exclamation-triangle text-warning"></i> Faltan ${16 - numeros.length} dígitos`;
            tarjetaError.className = 'text-warning small';
            return false;
        } else if (numeros.length === 16) {
            tarjetaError.innerHTML = '<i class="fas fa-check-circle text-success"></i> Número válido';
            tarjetaError.className = 'text-success small';
            return true;
        }
    }
    return true;
}

function formatearFechaExpiracion(input) {
    let valor = input.value.replace(/\D/g, '');
    if (valor.length > 4) valor = valor.slice(0, 4);
    if (valor.length >= 2) {
        let mes = valor.slice(0, 2);
        let anio = valor.slice(2);
        if (parseInt(mes) > 12) mes = '12';
        if (parseInt(mes) < 1 && mes.length === 2) mes = '01';
        input.value = mes + (anio ? '/' + anio : '');
    } else {
        input.value = valor;
    }
    validarFechaExpiracion();
}

function validarFechaExpiracion() {
    const fechaInput = document.getElementById('fechaExpiracion');
    const fechaError = document.getElementById('fechaError');
    if (!fechaInput || !fechaError) return true;
    if (metodoSeleccionado === 'tarjeta' && fechaInput.value) {
        const partes = fechaInput.value.split('/');
        if (partes.length === 2) {
            const mes = parseInt(partes[0]);
            const anio = 2000 + parseInt(partes[1]);
            const ahora = new Date();
            const fechaActual = new Date(ahora.getFullYear(), ahora.getMonth());
            const fechaTarjeta = new Date(anio, mes - 1);
            if (mes < 1 || mes > 12) {
                fechaError.innerHTML = '<i class="fas fa-exclamation-triangle text-warning"></i> Mes inválido (01-12)';
                fechaError.className = 'text-warning small';
                return false;
            }
            if (fechaTarjeta < fechaActual) {
                fechaError.innerHTML = '<i class="fas fa-exclamation-triangle text-danger"></i> Tarjeta expirada';
                fechaError.className = 'text-danger small';
                return false;
            } else {
                fechaError.innerHTML = '<i class="fas fa-check-circle text-success"></i> Fecha válida';
                fechaError.className = 'text-success small';
                return true;
            }
        }
    }
    return true;
}

function validarCVV(input) {
    let valor = input.value.replace(/\D/g, '');
    if (valor.length > 4) valor = valor.slice(0, 4);
    input.value = valor;
    const cvvError = document.getElementById('cvvError');
    if (!cvvError) return true;
    if (metodoSeleccionado === 'tarjeta' && valor.length > 0) {
        if (valor.length === 3 || valor.length === 4) {
            cvvError.innerHTML = '<i class="fas fa-check-circle text-success"></i> CVV válido';
            cvvError.className = 'text-success small';
            return true;
        } else if (valor.length > 0) {
            cvvError.innerHTML = `<i class="fas fa-exclamation-triangle text-warning"></i> Faltan ${valor.length === 1 ? 2 : (valor.length === 2 ? 1 : 3)} dígitos`;
            cvvError.className = 'text-warning small';
            return false;
        }
    }
    return true;
}

function validarDatosTarjeta() {
    if (metodoSeleccionado !== 'tarjeta') return true;
    const numeroTarjeta = document.getElementById('numeroTarjeta');
    const fechaExpiracion = document.getElementById('fechaExpiracion');
    const cvv = document.getElementById('cvv');
    const numeros = numeroTarjeta.value.replace(/\s/g, '');
    if (numeros.length !== 16) {
        Swal.fire({icon:'warning',title:'Datos inválidos',text:'El número de tarjeta debe tener 16 dígitos'});
        numeroTarjeta.focus();
        return false;
    }
    const fechaPartes = fechaExpiracion.value.split('/');
    if (fechaPartes.length !== 2) {
        Swal.fire({icon:'warning',title:'Datos inválidos',text:'Ingresa una fecha de expiración válida (MM/YY)'});
        fechaExpiracion.focus();
        return false;
    }
    const mes = parseInt(fechaPartes[0]);
    const anio = 2000 + parseInt(fechaPartes[1]);
    const ahora = new Date();
    const fechaActual = new Date(ahora.getFullYear(), ahora.getMonth());
    const fechaTarjeta = new Date(anio, mes - 1);
    if (mes < 1 || mes > 12) {
        Swal.fire({icon:'warning',title:'Datos inválidos',text:'El mes debe estar entre 01 y 12'});
        fechaExpiracion.focus();
        return false;
    }
    if (fechaTarjeta < fechaActual) {
        Swal.fire({icon:'warning',title:'Tarjeta expirada',text:'La fecha de expiración ya pasó'});
        fechaExpiracion.focus();
        return false;
    }
    const cvvValor = cvv.value;
    if (cvvValor.length < 3) {
        Swal.fire({icon:'warning',title:'Datos inválidos',text:'El CVV debe tener al menos 3 dígitos'});
        cvv.focus();
        return false;
    }
    return true;
}

// ===============================
// FUNCIONES PRINCIPALES
// ===============================

function verificarTipoEntrega(){
    const tipoEntrega=localStorage.getItem('tipoEntrega');
    const contraentregaCard=document.getElementById('contraentregaCard');
    const envioRow=document.getElementById('envioRow');
    if(tipoEntrega!=='delivery'){
        if(contraentregaCard){contraentregaCard.style.opacity='0.5';contraentregaCard.style.pointerEvents='none'}
        if(envioRow)envioRow.style.display='none'
    }else{
        if(contraentregaCard){contraentregaCard.style.opacity='1';contraentregaCard.style.pointerEvents='auto'}
        if(envioRow)envioRow.style.display='flex'
    }
}

function cargarDatos(){
    const g=localStorage.getItem('carritoCliente');
    carrito=g?JSON.parse(g):[];
    
    const chk=localStorage.getItem('checkoutData');
    if(chk){
        checkoutData=JSON.parse(chk);
        console.log("✅ checkoutData cargado:", checkoutData);
        console.log("🔍 Documento encontrado:", checkoutData.documento);
    }else{
        console.log("❌ No hay checkoutData en localStorage");
    }
    
    const tipoEntrega=localStorage.getItem('tipoEntrega')||'recojo';
    if(tipoEntrega==='delivery'){
        costoEnvio=parseFloat(localStorage.getItem('costoEntrega'))||0;
        document.getElementById('envioRow').style.display='flex';
        document.getElementById('envioTexto').innerHTML='S/. '+costoEnvio.toFixed(2);
    }
    else{costoEnvio=0;document.getElementById('envioRow').style.display='none'}
    
    subtotal=carrito.reduce((s,i)=>s+(i.precio*i.cantidad),0);
    descuento=parseFloat(localStorage.getItem('descuento')||0);
    document.getElementById('subtotalTexto').innerHTML=`S/. ${subtotal.toFixed(2)}`;
    if(descuento>0){document.getElementById('descuentoResumen').style.display='flex';document.getElementById('descuentoTexto').innerHTML=`-S/. ${descuento.toFixed(2)}`}
    
    actualizarTotal();
    
    let html='';
    carrito.forEach(i=>{html+=`<div class="d-flex justify-content-between mb-2"><span class="small">${escapeHtml(i.nombre)} x${i.cantidad}</span><span class="small">S/. ${(i.precio*i.cantidad).toFixed(2)}</span></div>`});
    document.getElementById('resumenProductos').innerHTML=html;
}

function actualizarTotal(){
    total=subtotal-descuento+costoEnvio+cargoContraentrega;
    document.getElementById('totalFinal').innerHTML=`S/. ${total.toFixed(2)}`;
}

function selectPaymentMethod(metodo){
    metodoSeleccionado=metodo;
    document.querySelectorAll('.payment-method-card').forEach(c=>c.classList.remove('selected'));
    document.querySelector(`.payment-method-card[data-metodo="${metodo}"]`).classList.add('selected');
    document.getElementById(`${metodo}Radio`).checked=true;
    document.querySelectorAll('.payment-form').forEach(f=>f.style.display='none');
    document.getElementById(`${metodo}Form`).style.display='block';
    const cCosto=document.getElementById('contraentregaCosto');
    const tipo=localStorage.getItem('tipoEntrega')||'recojo';
    if(metodo==='contraentrega'&&tipo==='delivery'){cargoContraentrega=3;cCosto.style.display='flex'}
    else{cargoContraentrega=0;cCosto.style.display='none'}
    actualizarTotal();
}

// ===============================
// CONFIRMAR PEDIDO
// ===============================
async function confirmarPedido(){
    if(!metodoSeleccionado){
        Swal.fire({icon:'warning',title:'Selecciona método de pago'});
        return;
    }
    
    if(metodoSeleccionado === 'tarjeta') {
        if(!validarDatosTarjeta()) {
            return;
        }
    }
    
    if(!checkoutData.email && !checkoutData.telefono){
        Swal.fire({icon:'error',title:'Error',text:'Necesitas un correo o un celular para enviarte el comprobante. Regresa a checkout'});
        return;
    }
    
    const tipoEntrega=localStorage.getItem('tipoEntrega')||'recojo';
    if(metodoSeleccionado==='contraentrega'&&tipoEntrega!=='delivery'){
        Swal.fire({icon:'warning',title:'No disponible',text:'Contraentrega solo para delivery'});
        return;
    }
    
    const items=carrito.map(i=>({
        id:parseInt(i.id),
        nombre:i.nombre,
        precio:parseFloat(i.precio),
        cantidad:parseInt(i.cantidad)
    }));
    
    // Ubicación exacta que el cliente marcó en el mapa del carrito (si es delivery).
    // Sin esto, el backend geocodificaba solo el texto de la dirección y el punto
    // aparecía en otra zona.
    const latitudEntrega = checkoutData.latitud || localStorage.getItem('latitudEntrega') || '';
    const longitudEntrega = checkoutData.longitud || localStorage.getItem('longitudEntrega') || '';

    const pedidoData={
        items:items,
        total:total,
        tipo_entrega:tipoEntrega,
        direccion:checkoutData.direccion || '',
        distrito: checkoutData.distrito || localStorage.getItem('distritoEntrega') || '',
        costo_envio: costoEnvio,
        cargo_contraentrega: cargoContraentrega,
        latitud:latitudEntrega,
        longitud:longitudEntrega,
        comprobante: { tipo: checkoutData.tipo_comprobante || 'boleta' },
        metodo_pago:metodoSeleccionado,
        descuento:descuento,
        cliente:{
            nombres:checkoutData.nombres || '',
            apellidos:checkoutData.apellidos || '',
            email:checkoutData.email || '',
            telefono:checkoutData.telefono || '',
            documento: checkoutData.documento || '',
            tipo_documento: checkoutData.tipo_documento || '',
            razon_social: checkoutData.razon_social || '',
            direccion_fiscal: checkoutData.direccion_fiscal || '',
            preferencia_comprobante: checkoutData.preferencia_comprobante || ''
        }
    };
    
    console.log("📤 ENVIANDO PEDIDO:");
    console.log("   Cliente:", pedidoData.cliente);
    console.log("   Documento enviado:", pedidoData.cliente.documento);
    
    const btn=document.getElementById('btnConfirmar');
    const original=btn.innerHTML;
    btn.innerHTML='<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
    btn.disabled=true;
    
    try{
        const res=await fetch('/api/pedidos/crear',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify(pedidoData)
        });
        const data=await res.json();
        if(data.success){
            localStorage.removeItem('carritoCliente');
            localStorage.removeItem('checkoutData');
            localStorage.removeItem('cuponAplicado');
            localStorage.removeItem('descuento');
            localStorage.removeItem('tipoEntrega');
            localStorage.removeItem('direccionEntrega');
            
            const waUrl=data.whatsapp_url||'';
            let aviso='';
            if(data.correo_enviado){
                aviso='<br><br>📧 El comprobante fue enviado a tu correo';
            }else if(waUrl){
                aviso='<br><br>💬 Para recibir tu comprobante, abre WhatsApp y toca <b>Enviar</b>. El mensaje ya está listo.';
            }else{
                aviso=data.numero_comprobante ? '<br><br>📄 Comprobante: <b>'+escapeHtml(data.numero_comprobante)+'</b>' : '';
            }

            if(waUrl){
                // El comprobante por WhatsApp necesita un toque del cliente (WhatsApp
                // no permite enviar mensajes solo desde el servidor sin su API de pago).
                Swal.fire({
                    icon:'success',
                    title:'¡Pedido realizado!',
                    html:`✅ ¡Pedido realizado!<br>Total: S/. ${total.toFixed(2)}${aviso}`,
                    confirmButtonText:'<i class="fab fa-whatsapp me-1"></i>Recibir por WhatsApp',
                    confirmButtonColor:'#25D366',
                    showCancelButton:true,
                    cancelButtonText:'Ver mis pedidos',
                    allowOutsideClick:false
                }).then((r)=>{
                    if(r.isConfirmed){ window.open(waUrl,'_blank'); }
                    window.location.href='/mis-pedidos';
                });
            }else{
                Swal.fire({
                    icon:'success',
                    title:'¡Pedido realizado!',
                    html:`✅ ¡Pedido realizado!<br>Total: S/. ${total.toFixed(2)}${aviso}`,
                    confirmButtonText:'Ver mis pedidos',
                    confirmButtonColor:'#D4AF37'
                }).then(()=>{ window.location.href='/mis-pedidos'; });
            }
        }else{
            Swal.fire({icon:'error',title:'Error',text:data.error});
        }
    }catch(e){
        console.error("Error:", e);
        Swal.fire({icon:'error',title:'Error',text:'No se pudo conectar con el servidor'});
    }
    finally{
        btn.innerHTML=original;
        btn.disabled=false;
    }
}

function escapeHtml(t){
    if(!t) return '';
    return t.replace(/[&<>]/g,function(m){
        if(m==='&') return '&amp;';
        if(m==='<') return '&lt;';
        if(m==='>') return '&gt;';
        return m;
    });
}
