"""Pruebas A-E del descuento de stock del checkout (MySQL real).

Se usa la ruta directa de `stock` (monolito / microservicio caido), que es la
misma que respalda al endpoint HTTP: actualizacion condicional + tabla de
reservas con clave de idempotencia. Cada prueba crea un producto temporal y
lo elimina al terminar.
"""
import importlib.util
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "www"))

import stock  # noqa: E402


@pytest.fixture(scope="module")
def gateway():
    import app as gateway_app

    try:
        with gateway_app.app.app_context():
            motor = gateway_app.db.get_engine(bind="inventario")
            with motor.connect() as con:
                con.execute(text("SELECT 1 FROM inventario_productos LIMIT 1"))
    except Exception as e:  # pragma: no cover - depende del entorno
        pytest.skip(f"MySQL de inventario no disponible: {str(e)[:120]}")
    yield gateway_app


@pytest.fixture
def motor(gateway):
    with gateway.app.app_context():
        return gateway.db.engines["inventario"]


@pytest.fixture
def producto(gateway, motor):
    nombre = f"TEST-RESERVA-{uuid.uuid4().hex[:10]}"
    with motor.begin() as con:
        con.execute(
            text(
                "INSERT INTO inventario_productos (nombre, cantidad, precio, estado) "
                "VALUES (:n, 0, 1.00, 1)"
            ),
            {"n": nombre},
        )
        pid = con.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    yield pid
    with motor.begin() as con:
        con.execute(text("DELETE FROM reservas_stock WHERE producto_id=:p"),
                    {"p": pid})
        con.execute(text("DELETE FROM inventario_productos WHERE id=:p"), {"p": pid})


def _stock(motor, pid):
    with motor.connect() as con:
        return con.execute(
            text("SELECT cantidad FROM inventario_productos WHERE id=:p"), {"p": pid}
        ).scalar()


def _fijar_stock(motor, pid, cantidad):
    with motor.begin() as con:
        con.execute(text("UPDATE inventario_productos SET cantidad=:c WHERE id=:p"),
                    {"c": cantidad, "p": pid})


def _reservas(motor, referencia):
    with motor.connect() as con:
        return con.execute(
            text("SELECT COUNT(*) FROM reservas_stock WHERE referencia=:r"),
            {"r": referencia},
        ).scalar()


@pytest.fixture(autouse=True)
def api_inventario_real(gateway, monkeypatch):
    """Conecta el cliente REST del gateway con el test_client del servicio."""
    monkeypatch.setenv("MS_CONSUMIDOR", "0")
    ruta = RAIZ / "servicio-inventario" / "app.py"
    spec = importlib.util.spec_from_file_location(
        f"ms_inventario_checkout_{uuid.uuid4().hex}", ruta)
    servicio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(servicio)

    def post(ruta_api, payload, timeout=3.0):
        respuesta = servicio.app.test_client().post(
            ruta_api, json=payload,
            headers={"X-Service-Token": servicio.SERVICE_TOKEN})
        return respuesta.status_code, respuesta.get_json() or {}

    monkeypatch.setattr(stock, "_post", post)


def _ref(prefijo):
    return f"{prefijo}-{uuid.uuid4().hex}"


def test_a_pedido_exitoso_descuenta_una_sola_vez(gateway, motor, producto):
    _fijar_stock(motor, producto, 10)
    referencia = _ref("a")

    resultado = stock.reservar_stock(referencia, [{"id": producto, "cantidad": 3}])

    assert resultado["ok"] is True, resultado
    assert resultado["duplicado"] is False
    assert _stock(motor, producto) == 7


def test_b_evento_repetido_no_descuenta_de_nuevo(gateway, motor, producto):
    _fijar_stock(motor, producto, 10)
    referencia = _ref("b")
    items = [{"id": producto, "cantidad": 3}]

    primero = stock.reservar_stock(referencia, items)
    segundo = stock.reservar_stock(referencia, items)

    assert primero["ok"] is True
    assert segundo["ok"] is True
    assert segundo["duplicado"] is True
    assert _stock(motor, producto) == 7
    assert _reservas(motor, referencia) == 1


def test_c_stock_insuficiente_no_deja_descuento_parcial(gateway, motor, producto):
    _fijar_stock(motor, producto, 2)
    referencia = _ref("c")

    resultado = stock.reservar_stock(referencia, [{"id": producto, "cantidad": 5}])

    assert resultado["ok"] is False
    assert resultado["codigo"] == "stock_insuficiente"
    assert _stock(motor, producto) == 2
    assert _reservas(motor, referencia) == 0


def test_d_solicitudes_simultaneas_no_venden_de_mas(gateway, motor, producto):
    _fijar_stock(motor, producto, 5)

    def comprar(referencia):
        with gateway.app.app_context():
            return stock.reservar_stock(
                referencia, [{"id": producto, "cantidad": 4}])

    referencias = [_ref("d1"), _ref("d2")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(comprar, referencias))

    exitos = [r for r in resultados if r.get("ok")]
    rechazos = [r for r in resultados if not r.get("ok")]
    assert len(exitos) == 1, resultados
    assert len(rechazos) == 1, resultados
    assert rechazos[0]["codigo"] == "stock_insuficiente"
    assert _stock(motor, producto) == 1


def test_e_sin_inventario_no_se_confirma_la_compra(gateway, motor, producto,
                                                    monkeypatch):
    _fijar_stock(motor, producto, 10)

    def sin_motor():
        raise RuntimeError("inventario y base de datos no disponibles")

    monkeypatch.setattr(stock, "_post",
                        lambda *a, **k: (None, {"error": "timeout del inventario"}))
    monkeypatch.setattr(stock, "_motor_inventario", sin_motor)
    resultado = stock.reservar_stock(
        _ref("e"), [{"id": producto, "cantidad": 3}])

    assert resultado["ok"] is False
    assert resultado["codigo"] == "inventario_no_disponible"
    assert _stock(motor, producto) == 10


def test_e_fallo_posterior_libera_la_reserva(gateway, motor, producto):
    _fijar_stock(motor, producto, 10)
    referencia = _ref("e2")
    assert stock.reservar_stock(
        referencia, [{"id": producto, "cantidad": 3}])["ok"] is True
    assert _stock(motor, producto) == 7

    liberacion = stock.liberar_stock(referencia)

    assert liberacion["ok"] is True
    assert _stock(motor, producto) == 10
    # La compensacion es idempotente: repetirla no regala stock.
    assert stock.liberar_stock(referencia)["ok"] is True
    assert _stock(motor, producto) == 10
    # Un reintento con la misma clave ya no puede reutilizar la reserva.
    reintento = stock.reservar_stock(
        referencia, [{"id": producto, "cantidad": 3}])
    assert reintento["ok"] is False
    assert reintento["codigo"] == "reserva_liberada"


def test_confirmar_vincula_el_pedido_y_sobrevive_a_la_liberacion(gateway, motor,
                                                                 producto):
    _fijar_stock(motor, producto, 10)
    referencia = _ref("f")
    assert stock.reservar_stock(
        referencia, [{"id": producto, "cantidad": 3}])["ok"] is True

    confirmacion = stock.confirmar_stock(referencia, 99, documento_tipo="pedido")
    assert confirmacion["ok"] is True

    duplicado = stock.reservar_stock(
        referencia, [{"id": producto, "cantidad": 3}])
    assert duplicado["ok"] is True
    assert duplicado["duplicado"] is True
    assert duplicado["estado"] == "confirmado"
    assert duplicado["documento_id"] == 99

    # Un pedido confirmado no se libera por accidente.
    stock.liberar_stock(referencia)
    assert _stock(motor, producto) == 7


def test_items_duplicados_se_agrupan_antes_de_validar_stock(gateway, motor,
                                                            producto):
    _fijar_stock(motor, producto, 5)
    referencia = _ref("g")

    resultado = stock.reservar_stock(
        referencia,
        [{"id": producto, "cantidad": 3}, {"id": producto, "cantidad": 3}],
    )

    assert resultado["ok"] is False
    assert resultado["codigo"] == "stock_insuficiente"
    assert _stock(motor, producto) == 5
