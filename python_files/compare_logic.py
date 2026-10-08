from python_files.packed_food_data import RISKY_INGREDIENT_LIST
from python_files.ocr_helper import read_text_from_image


def analyze_one_product(image_path):
    """Reads the label text from one packet photo and finds risky ingredients in it."""
    text_found = read_text_from_image(image_path)

    found_risks = []
    for keyword, reason in RISKY_INGREDIENT_LIST.items():
        if keyword in text_found:
            found_risks.append({"ingredient": keyword, "reason": reason})

    return {
        "risky_ingredients": found_risks,
        "risk_score": len(found_risks),
        "text_was_readable": len(text_found) > 5
    }


def compare_products(image_path_list):
    """Takes a list of 2 to 4 packet image paths and compares them by risk score
    (fewer risky ingredients found = healthier choice)."""
    results = []

    for path in image_path_list:
        analysis = analyze_one_product(path)
        results.append(analysis)

    readable_results = [r for r in results if r["text_was_readable"]]

    if len(readable_results) < 2:
        return {
            "products": results,
            "best_index": None,
            "message": "Could not clearly read enough labels. Try clearer, well-lit photos of the ingredient list."
        }

    best_index = results.index(min(readable_results, key=lambda r: r["risk_score"]))

    return {
        "products": results,
        "best_index": best_index,
        "message": "Comparison based on number of risky ingredients found on each label."
    }
