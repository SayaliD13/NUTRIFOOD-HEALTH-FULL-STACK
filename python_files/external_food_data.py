"""External food-data verification helpers.
USDA requires an API key. Open Food Facts is read-only public data and does not require a key.
All failures are non-fatal so the primary analysis can still complete.
"""
import os
import re
import requests
from functools import lru_cache

USDA_API_KEY = (os.environ.get("USDA_API_KEY") or "").strip()
USDA_BASE = "https://api.nal.usda.gov/fdc/v1"
OFF_BASE = "https://world.openfoodfacts.org/api/v2"
OFF_HEADERS = {"User-Agent": os.environ.get("OPENFOODFACTS_USER_AGENT", "NutriFood-Health/1.0")}


def _clean_query(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:180]


def _num(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _nutrient_map(food):
    out = {}
    for n in food.get("foodNutrients", []) or []:
        name = str(n.get("nutrientName") or n.get("name") or "").lower()
        val = _num(n.get("value"))
        unit = n.get("unitName") or n.get("unit")
        if val is not None and name:
            out[name] = {"value": val, "unit": unit}
    return out


@lru_cache(maxsize=128)
def usda_search(food_name):
    if not USDA_API_KEY:
        return None
    q = _clean_query(food_name)
    if not q:
        return None
    try:
        r = requests.get(
            f"{USDA_BASE}/foods/search",
            params={"api_key": USDA_API_KEY, "query": q, "pageSize": 3},
            timeout=8,
        )
        r.raise_for_status()
        foods = r.json().get("foods") or []
        if not foods:
            return None
        f = foods[0]
        nutrients = _nutrient_map(f)
        return {
            "fdc_id": f.get("fdcId"),
            "description": f.get("description"),
            "data_type": f.get("dataType"),
            "nutrients": nutrients,
        }
    except (requests.RequestException, ValueError, TypeError):
        return None


def verify_nutrition(food_name, current=None):
    """Return a conservative USDA reference without overwriting photo estimates."""
    ref = usda_search(food_name)
    if not ref:
        return {"available": False, "source": "USDA FoodData Central"}
    nutrients = ref.get("nutrients", {})
    aliases = {
        "calories": ["energy"],
        "protein": ["protein"],
        "fat": ["total lipid (fat)"],
        "carbs": ["carbohydrate, by difference"],
        "fiber": ["fiber, total dietary"],
        "sugars": ["sugars, total including nlea"],
        "sodium": ["sodium, na"],
        "potassium": ["potassium, k"],
    }
    values = {}
    for key, names in aliases.items():
        for name in names:
            if name in nutrients:
                values[key] = nutrients[name]
                break
    return {
        "available": True,
        "source": "USDA FoodData Central",
        "fdc_id": ref.get("fdc_id"),
        "matched_food": ref.get("description"),
        "data_type": ref.get("data_type"),
        "reference_nutrients": values,
        "note": "USDA values are database reference values; the scanned portion may differ.",
    }


@lru_cache(maxsize=64)
def openfoodfacts_search(product_name):
    q = _clean_query(product_name)
    if not q:
        return None
    try:
        r = requests.get(
            f"{OFF_BASE}/search",
            params={"search_terms": q, "page_size": 3, "fields": "code,product_name,brands,ingredients_text,nutriments,allergens,labels"},
            headers=OFF_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        products = r.json().get("products") or []
        if not products:
            return None
        p = products[0]
        return {
            "code": p.get("code"),
            "product_name": p.get("product_name"),
            "brands": p.get("brands"),
            "ingredients_text": p.get("ingredients_text"),
            "allergens": p.get("allergens"),
            "labels": p.get("labels"),
            "nutriments": p.get("nutriments") or {},
        }
    except (requests.RequestException, ValueError, TypeError):
        return None


def enrich_packed_result(result):
    """Use OFF as supporting product evidence; never fabricate missing fields."""
    result = dict(result or {})
    product_name = _clean_query(result.get("product_name"))
    if not product_name or product_name.lower() in {"scanned product", "scanned/typed product", "product"}:
        return result
    off = openfoodfacts_search(product_name)
    if not off:
        return result
    result["product_database"] = {
        "source": "Open Food Facts",
        "product_name": off.get("product_name"),
        "brand": off.get("brands"),
        "ingredients_text": off.get("ingredients_text"),
        "allergens": off.get("allergens"),
        "labels": off.get("labels"),
        "nutriments": off.get("nutriments"),
        "code": off.get("code"),
    }
    if off.get("ingredients_text") and not result.get("ingredients_found"):
        result["ingredients_found"] = [x.strip() for x in re.split(r",|;", off["ingredients_text"]) if x.strip()][:40]
    return result
