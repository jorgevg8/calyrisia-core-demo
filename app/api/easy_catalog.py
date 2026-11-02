"""Rutas de carga asistida del catálogo y utilidades de extracción.

Las rutas conservan el aislamiento por negocio: el business_id se obtiene del
usuario autenticado y nunca del cuerpo enviado por el navegador.
"""
from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api import auth
from app.core.config import get_settings
from app.db import get_connection
from app.services.commercial_limits import get_business_plan, plan_limits
from app.services.context_manager import invalidate_business_context_cache

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - AI is optional for deterministic local parsing
    genai = None  # type: ignore
    genai_types = None  # type: ignore

router = APIRouter()


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    text = str(value).strip().replace("$", "").replace("USD", "").replace("usd", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d{1,2})?", text)
    if not match:
        return default
    try:
        return max(0.0, float(match.group(0)))
    except ValueError:
        return default


def _clean_item(row: dict[str, Any], default_category: str = "General", default_stock: float = 15.0) -> dict[str, Any] | None:
    name = re.sub(r"\s+", " ", str(row.get("name") or row.get("producto") or row.get("product") or "").strip())[:200]
    if not name:
        return None
    return {
        "name": name,
        "price": _number(row.get("price", row.get("precio")), 0.0),
        "stock": _number(row.get("stock", row.get("quantity", row.get("cantidad"))), default_stock),
        "category": str(row.get("category") or row.get("categoria") or default_category).strip()[:100] or default_category,
        "sku": str(row.get("sku") or "").strip()[:100] or None,
        "brand": str(row.get("brand") or row.get("marca") or "").strip()[:100] or None,
        "description": str(row.get("description") or row.get("descripcion") or "").strip()[:1000] or None,
    }


def smart_extract_products_from_text(
    raw_text: str,
    default_category: str = "General",
    default_stock: float = 15.0,
) -> list[dict[str, Any]]:
    """Extrae productos de líneas tabulares o texto simple sin requerir IA."""
    result: list[dict[str, Any]] = []
    for raw_line in (raw_text or "").splitlines():
        line = re.sub(r"^[\s•*▸\-]+", "", raw_line).strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^(nombre|name|producto|product)\b", line, re.IGNORECASE):
            continue

        sep = "|" if "|" in line else (";" if ";" in line else ("\t" if "\t" in line else None))
        if sep:
            parts = [part.strip() for part in line.split(sep)]
            row = {
                "name": parts[0] if parts else "",
                "price": parts[1] if len(parts) > 1 else 0,
                "stock": parts[2] if len(parts) > 2 else default_stock,
                "category": parts[3] if len(parts) > 3 else default_category,
                "sku": parts[4] if len(parts) > 4 else None,
            }
            item = _clean_item(row, default_category, default_stock)
            if item:
                result.append(item)
            continue

        work = line
        stock = default_stock
        stock_match = re.search(r"\b(?:stock|cantidad|existencia|uds?|unidades?)\s*[:=]?\s*(\d+(?:[.,]\d+)?)|\b(\d+(?:[.,]\d+)?)\s*(?:uds?|unidades?)\b", work, re.I)
        if stock_match:
            stock = _number(next((g for g in stock_match.groups() if g), None), default_stock)
            work = work[:stock_match.start()] + " " + work[stock_match.end():]
        price_match = re.search(
            r"(?:\$|USD\s*|precio\s*[:=]?\s*|\ba\s+)(\d+(?:[.,]\d{1,2})?)\s*(?:d[oó]lares?|usd)?\b",
            work,
            re.I,
        )
        if not price_match:
            price_match = re.search(r"(?:-|\s)(\d+(?:[.,]\d{1,2})?)\s*$", work)
        price = _number(price_match.group(1), 0.0) if price_match else 0.0
        if price_match:
            work = work[:price_match.start()] + " " + work[price_match.end():]
        # Una cantidad inicial como "20 franelas negras a 12 dólares" se
        # interpreta como stock y no como parte del nombre del producto.
        leading_qty = re.match(r"^\s*(\d{1,5})\s+(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])", work)
        if leading_qty and stock == default_stock:
            stock = float(leading_qty.group(1))
            work = work[leading_qty.end():]
        name = re.sub(r"\s+", " ", re.sub(r"[,:;\-]+\s*$", "", work)).strip()
        item = _clean_item({"name": name, "price": price, "stock": stock, "category": default_category}, default_category, default_stock)
        if item:
            result.append(item)
    return result[:1000]


def _parse_model_json(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end <= start:
            return []
        try:
            value = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        value = value.get("products") or value.get("items") or value.get("productos") or []
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _gemini_extract(prompt: str, image: tuple[bytes, str] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.gemini_api_key or genai is None or genai_types is None:
        return []
    client = genai.Client(api_key=settings.gemini_api_key)
    contents: Any = prompt
    if image:
        image_bytes, mime_type = image
        contents = [prompt, genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)]
    preferred = (settings.gemini_model or "").strip()
    models = [m for m in [preferred, "gemini-2.5-flash", "gemini-2.0-flash"] if m]
    seen: set[str] = set()
    for model in models:
        if model in seen:
            continue
        seen.add(model)
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )
            items = _parse_model_json(getattr(response, "text", "") or "")
            if items:
                return items
        except Exception:
            continue
    return []


def _template_products(business_type: str) -> list[dict[str, Any]]:
    kind = (business_type or "").lower()
    if any(x in kind for x in ("restaur", "comida", "pizza", "caf", "panader", "bar")):
        rows = [
            ("Hamburguesa Especial", 8.50, "Comida"), ("Hamburguesa Doble Queso", 11.00, "Comida"),
            ("Perro Caliente", 4.00, "Comida"), ("Papas Fritas", 3.50, "Acompañantes"),
            ("Nuggets de Pollo", 5.00, "Acompañantes"), ("Pizza Pepperoni", 7.00, "Comida"),
            ("Tequeños", 4.50, "Entradas"), ("Refresco 355 ml", 1.50, "Bebidas"),
            ("Malteada de Chocolate", 3.50, "Bebidas"), ("Brownie", 4.00, "Postres"),
        ]
    elif any(x in kind for x in ("ropa", "boutique", "moda", "calzado", "zapater")):
        rows = [
            ("Camisa Casual", 25.00, "Ropa"), ("Pantalón Jean", 32.00, "Ropa"),
            ("Vestido Casual", 28.00, "Ropa"), ("Blusa", 22.00, "Ropa"),
            ("Chaqueta Denim", 45.00, "Ropa"), ("Short Casual", 16.00, "Ropa"),
            ("Franela de Algodón", 12.00, "Ropa"), ("Zapatos Casuales", 48.00, "Calzado"),
            ("Cinturón", 15.00, "Accesorios"), ("Lentes de Sol", 18.00, "Accesorios"),
        ]
    elif any(x in kind for x in ("super", "market", "bode", "abasto", "viver")):
        rows = [
            ("Harina de Maíz 1 kg", 1.30, "Alimentos"), ("Arroz 1 kg", 1.20, "Alimentos"),
            ("Aceite Vegetal 1 L", 2.80, "Alimentos"), ("Queso Blanco 1 kg", 5.50, "Lácteos"),
            ("Café Molido 500 g", 4.20, "Alimentos"), ("Pasta 1 kg", 1.50, "Alimentos"),
            ("Leche 1 L", 1.80, "Lácteos"), ("Crema de Avellanas", 5.50, "Dulces"),
            ("Refresco 2 L", 2.50, "Bebidas"), ("Papel Higiénico", 2.00, "Higiene"),
        ]
    else:
        rows = [
            ("Cable USB-C", 6.00, "Accesorios"), ("Cargador 20W", 12.00, "Accesorios"),
            ("Auriculares Bluetooth", 22.00, "Audio"), ("Soporte para Teléfono", 8.50, "Accesorios"),
            ("Powerbank 10000mAh", 18.00, "Baterías"), ("Protector de Pantalla", 5.00, "Accesorios"),
            ("Funda Protectora", 7.50, "Fundas"), ("Memoria MicroSD 64GB", 9.00, "Memorias"),
            ("Mouse Inalámbrico", 11.50, "Computación"), ("Teclado Mecánico", 35.00, "Computación"),
        ]
    return [{"name": n, "price": p, "stock": 15.0, "category": c} for n, p, c in rows]


def _persist_items(conn: Any, business_id: UUID, items: list[dict[str, Any]]) -> dict[str, int]:
    if not items:
        raise HTTPException(status_code=422, detail="No se detectaron productos válidos.")
    if len(items) > 1000:
        raise HTTPException(status_code=413, detail="Puedes procesar hasta 1.000 productos por lote.")
    plan_code = get_business_plan(conn, business_id)
    limits = plan_limits(plan_code)
    cap = int(limits.get("products") or 0)
    created = updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text, name FROM products WHERE business_id = %s AND status = 'active'", (str(business_id),))
            existing = {re.sub(r"\s+", " ", str(row[1] or "").strip().lower()): str(row[0]) for row in cur.fetchall()}
            active_count = len(existing)
            for item in items:
                clean = _clean_item(item, str(item.get("category") or "General"), float(item.get("stock", 15) or 0))
                if not clean:
                    continue
                key = re.sub(r"\s+", " ", clean["name"].lower())
                product_id = existing.get(key)
                if product_id:
                    cur.execute(
                        "UPDATE products SET price = %s, category = %s, sku = COALESCE(%s, sku), updated_at = NOW() WHERE id = %s AND business_id = %s",
                        (clean["price"], clean["category"], clean.get("sku"), product_id, str(business_id)),
                    )
                    cur.execute("UPDATE inventory SET quantity = %s WHERE product_id = %s AND business_id = %s", (clean["stock"], product_id, str(business_id)))
                    if cur.rowcount == 0:
                        cur.execute(
                            "INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location) VALUES (gen_random_uuid(), %s, %s, %s, 0, 'tienda')",
                            (str(business_id), product_id, clean["stock"]),
                        )
                    updated += 1
                else:
                    if cap and active_count >= cap:
                        raise HTTPException(status_code=409, detail=f"Alcanzaste el límite de {cap} productos de tu plan {limits.get('label', '')}.")
                    product_id = str(uuid4())
                    cur.execute(
                        "INSERT INTO products (id, business_id, name, sku, price, category, status) VALUES (%s, %s, %s, %s, %s, %s, 'active')",
                        (product_id, str(business_id), clean["name"], clean.get("sku"), clean["price"], clean["category"]),
                    )
                    cur.execute(
                        "INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location) VALUES (gen_random_uuid(), %s, %s, %s, 0, 'tienda')",
                        (str(business_id), product_id, clean["stock"]),
                    )
                    existing[key] = product_id
                    active_count += 1
                    created += 1
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el catálogo: {exc}") from exc
    invalidate_business_context_cache(business_id)
    return {"created_products": created, "updated_products": updated, "total_processed": created + updated}


@router.post("/dashboard/catalog/ai-extract")
async def ai_extract_catalog(
    payload: dict[str, Any],
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict[str, Any]:
    business_id = UUID(current_user["business_id"])
    raw_text = str(payload.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Pega o escribe los productos que deseas cargar.")
    category = str(payload.get("default_category") or "General").strip()[:100] or "General"
    prompt = (
        "Extrae productos de este texto. Devuelve exclusivamente JSON con la forma "
        '{"products":[{"name":"...","price":0,"stock":0,"category":"...","sku":null}]}. '
        "No inventes productos ni precios; si falta el precio usa 0 y si falta stock usa 15. "
        f"Categoría predeterminada: {category}. Texto:\n{raw_text[:50000]}"
    )
    model_rows = await asyncio.to_thread(_gemini_extract, prompt)
    raw_items = model_rows or smart_extract_products_from_text(raw_text, category)
    items = [x for x in (_clean_item(row, category) for row in raw_items) if x]
    if not items:
        raise HTTPException(status_code=422, detail="No se detectaron productos. Usa una línea por producto e indica el precio.")
    if not bool(payload.get("auto_save", True)):
        return {"success": True, "items": items, "total_processed": len(items), "message": f"Se detectaron {len(items)} productos."}
    async with get_connection() as conn:
        counts = _persist_items(conn, business_id, items)
    return {"success": True, **counts, "message": f"Carga inteligente completada: {counts['created_products']} nuevos y {counts['updated_products']} actualizados."}


@router.post("/dashboard/catalog/vision-extract")
async def vision_extract_catalog(
    payload: dict[str, Any],
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict[str, Any]:
    business_id = UUID(current_user["business_id"])
    value = str(payload.get("image_base64") or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail="Selecciona una imagen para analizar.")
    mime_type = "image/jpeg"
    match = re.match(r"^data:(image/(?:png|jpeg|webp));base64,", value, re.I)
    if match:
        mime_type = match.group(1).lower()
        value = value[match.end():]
    try:
        image_bytes = base64.b64decode(re.sub(r"\s+", "", value), validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="La imagen no tiene un formato Base64 válido.") from exc
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La imagen no debe superar 8 MB.")
    category = str(payload.get("default_category") or "General").strip()[:100] or "General"
    prompt = (
        "Lee la imagen de una lista de precios, menú o inventario. Extrae solo los productos visibles. "
        'Devuelve exclusivamente JSON: {"products":[{"name":"...","price":0,"stock":15,"category":"...","sku":null}]}. '
        f"No inventes datos. Categoría predeterminada: {category}. Si no hay stock visible, usa 15."
    )
    rows = await asyncio.to_thread(_gemini_extract, prompt, (image_bytes, mime_type))
    items = [x for x in (_clean_item(row, category) for row in rows) if x]
    if not items:
        raise HTTPException(status_code=503, detail="No se pudieron extraer productos de la imagen. Comprueba GEMINI_API_KEY y vuelve a intentarlo.")
    if not bool(payload.get("auto_save", True)):
        return {"success": True, "items": items, "total_processed": len(items), "message": f"Se detectaron {len(items)} productos en la imagen."}
    async with get_connection() as conn:
        counts = _persist_items(conn, business_id, items)
    return {"success": True, **counts, "message": f"Imagen procesada: {counts['created_products']} productos nuevos y {counts['updated_products']} actualizados."}


@router.post("/dashboard/catalog/seed-template")
async def seed_catalog_template(
    payload: dict[str, Any] | None = None,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict[str, Any]:
    business_id = UUID(current_user["business_id"])
    payload = payload or {}
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT business_type FROM businesses WHERE id = %s", (str(business_id),))
            row = cur.fetchone()
        business_type = str(row[0] or "") if row else ""
        items = _template_products(str(payload.get("template_key") or business_type))
        default_stock = _number(payload.get("default_stock"), 20.0)
        for item in items:
            item["stock"] = default_stock
        counts = _persist_items(conn, business_id, items)
    return {"success": True, **counts, "message": f"Plantilla cargada: {counts['created_products']} productos nuevos y {counts['updated_products']} actualizados."}


def _read_upload_rows(filename: str, content: bytes) -> list[dict[str, Any]]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    rows: list[list[Any]] = []
    if suffix == "csv":
        text = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise HTTPException(status_code=422, detail="No se pudo leer el archivo CSV.")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    elif suffix in {"xlsx", "xlsm"}:
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
            sheet = workbook.active
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            workbook.close()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"No se pudo leer el Excel: {exc}") from exc
    else:
        raise HTTPException(status_code=415, detail="Formato no compatible. Sube un archivo CSV o XLSX.")
    if not rows:
        return []
    header = [str(x or "").strip().lower() for x in rows[0]]
    has_header = any(x in {"name", "nombre", "producto", "product", "price", "precio"} for x in header)
    if has_header:
        indexes = {name: i for i, name in enumerate(header) if name}
        if "categoría" in indexes and "category" not in indexes:
            indexes["category"] = indexes["categoría"]
        if "código" in indexes and "sku" not in indexes:
            indexes["sku"] = indexes["código"]
        rows = rows[1:]
    else:
        indexes = {"name": 0, "price": 1, "stock": 2, "category": 3, "sku": 4}
    def cell(row: list[Any], *names: str, default: Any = None) -> Any:
        for name in names:
            idx = indexes.get(name)
            if idx is not None and idx < len(row):
                return row[idx]
        return default
    result = []
    for row in rows:
        if not row:
            continue
        item = _clean_item({
            "name": cell(row, "name", "nombre", "producto", "product"),
            "price": cell(row, "price", "precio", default=0),
            "stock": cell(row, "stock", "quantity", "cantidad", default=15),
            "category": cell(row, "category", "categoria", "categoría", default="General"),
            "sku": cell(row, "sku", "codigo", "código"),
        })
        if item:
            result.append(item)
    return result


@router.post("/dashboard/catalog/upload-file")
async def upload_catalog_file(
    file: UploadFile = File(...),
    default_category: str = Form("General"),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    business_id = UUID(current_user["business_id"])
    content = await file.read(12 * 1024 * 1024 + 1)
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo no debe superar 12 MB.")
    rows = _read_upload_rows(file.filename or "catalog.csv", content)
    category = str(default_category or "General").strip()[:100] or "General"
    items = []
    for row in rows:
        row["category"] = row.get("category") or category
        clean = _clean_item(row, category)
        if clean:
            items.append(clean)
    if not items:
        raise HTTPException(status_code=422, detail="El archivo no contiene productos válidos. Debe incluir nombre y, opcionalmente, precio, stock y categoría.")
    async with get_connection() as conn:
        counts = _persist_items(conn, business_id, items)
    return {"success": True, **counts, "message": f"Archivo importado: {counts['created_products']} productos nuevos y {counts['updated_products']} actualizados."}
