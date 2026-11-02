(function () {
    const metaCliente = document.querySelector('meta[name="cliente-logueado"]');
    const metaClienteId = document.querySelector('meta[name="cliente-carrito-id"]');
    const metaCsrf = document.querySelector('meta[name="csrf-token"]');
    const autenticado = !!metaCliente && metaCliente.content === '1';
    const clienteActual = metaClienteId ? metaClienteId.content : '';
    let colaGuardado = Promise.resolve();

    function leerLocal() {
        try {
            const items = JSON.parse(localStorage.getItem('carritoCliente') || '[]');
            return Array.isArray(items) ? items : [];
        } catch (_) {
            return [];
        }
    }

    function guardarServidor(items) {
        if (!autenticado) return Promise.resolve(false);
        const payload = (Array.isArray(items) ? items : []).map(item => ({
            id: Number(item.id),
            cantidad: Number(item.cantidad)
        })).filter(item => Number.isInteger(item.id) && item.id > 0
            && Number.isInteger(item.cantidad) && item.cantidad > 0);

        colaGuardado = colaGuardado.catch(() => {}).then(() => fetch('/api/mi-carrito', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': metaCsrf ? metaCsrf.content : ''
            },
            body: JSON.stringify({ items: payload })
        })).then(async response => {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return true;
        }).catch(error => {
            console.warn('[carrito] no se pudo sincronizar con el servidor:', error);
            return false;
        });
        return colaGuardado;
    }

    window.guardarCarritoCliente = function (items) {
        const lista = Array.isArray(items) ? items : [];
        localStorage.setItem('carritoCliente', JSON.stringify(lista));
        if (autenticado && clienteActual) {
            localStorage.setItem('clienteCarritoId', clienteActual);
        }
        window.dispatchEvent(new CustomEvent('carritoClienteActualizado'));
        return guardarServidor(lista);
    };

    async function inicializarCarritoServidor() {
        if (!autenticado) return;
        try {
            const response = await fetch('/api/mi-carrito', {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' }
            });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            const remoto = Array.isArray(data.items) ? data.items : [];
            const propietarioLocal = localStorage.getItem('clienteCarritoId');
            if (propietarioLocal && propietarioLocal !== clienteActual) {
                localStorage.removeItem('carritoCliente');
            }
            const local = leerLocal();
            const combinados = new Map();

            remoto.forEach(item => combinados.set(Number(item.id), item));
            // Si ambos existen, conserva la cantidad que el cliente ve ahora;
            // también incorpora productos que solo estaban guardados en el servidor.
            local.forEach(item => combinados.set(Number(item.id), item));

            const lista = Array.from(combinados.values());
            localStorage.setItem('clienteCarritoId', clienteActual);
            localStorage.setItem('carritoCliente', JSON.stringify(lista));
            await guardarServidor(lista);
            window.dispatchEvent(new CustomEvent('carritoClienteActualizado'));
        } catch (error) {
            console.warn('[carrito] no se pudo cargar desde el servidor:', error);
        }
    }

    window.carritoServidorListo = inicializarCarritoServidor();
})();
