"""Fast local checks for Telegram checkout marker and receipt detection."""
from decimal import Decimal

from app.api.telegram import _clean_for_telegram, _looks_like_payment_submission, _parse_payment_marker


def main() -> None:
    amount, items = _parse_payment_marker([
        '[BOTON_PAGO: 21.50|ITEMS:[{"name":"Camisa","qty":1}] ]'
    ])
    assert amount == Decimal("21.50"), amount
    assert items and items[0]["name"] == "Camisa", items

    clean, marker_amount, _ = _clean_for_telegram("Total a pagar USD 21.50 [BOTON_PAGO: 21.50]")
    assert "BOTON_PAGO" not in clean
    assert marker_amount == Decimal("21.50")

    assert _looks_like_payment_submission("Ya pagué, referencia bancaria 12345678")
    assert _looks_like_payment_submission("Aquí está el comprobante")
    assert not _looks_like_payment_submission("¿Cómo pago por Pago Móvil?")
    print("OK: marcador de pago, limpieza de respuesta y detección de referencia.")


if __name__ == "__main__":
    main()
