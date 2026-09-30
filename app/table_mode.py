from app.config import settings


def normalized_app_mode() -> str:
    mode = (settings.app_mode or "prod").strip().lower()
    if mode not in {"prod", "test"}:
        raise ValueError("APP_MODE invalido. Usa 'prod' o 'test'.")
    return mode


def facturas_tables() -> tuple[str, str]:
    mode = normalized_app_mode()
    if mode == "test":
        return settings.facturas_table_test, settings.facturas_det_table_test
    return settings.facturas_table_prod, settings.facturas_det_table_prod
