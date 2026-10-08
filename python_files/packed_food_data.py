# Simple keyword based ingredient checker.
# key = ingredient keyword (lowercase), value = plain-language risk reason.
# Not a real ingredient scanner yet - this is rule based for the 50% stage.

RISKY_INGREDIENT_LIST = {
    "palm oil": "High in saturated fat, not great if you eat it daily",
    "trans fat": "Bad for heart health, best avoided",
    "high fructose corn syrup": "Type of added sugar, raises blood sugar quickly",
    "artificial sweetener": "May cause stomach issues in some people",
    "msg": "Can cause headache or discomfort in sensitive people",
    "sodium nitrite": "Preservative linked to health risks if eaten often",
    "artificial color": "No nutrition value, only for looks",
    "refined sugar": "Adds empty calories, spikes sugar level",
    "hydrogenated oil": "Same family as trans fat, bad for heart"
}

# used when a picture is uploaded instead of typed ingredients
# dummy packed food samples, same idea as MEAL_FOOD_DATA
PACKED_FOOD_SAMPLES = {
    "chips": {
        "product_name": "Salted Potato Chips", "calories": 536, "sugars": 2, "sodium": 620,
        "found_ingredients": ["palm oil", "artificial color", "msg"]
    },
    "biscuit": {
        "product_name": "Cream Biscuit Pack", "calories": 470, "sugars": 28, "sodium": 210,
        "found_ingredients": ["refined sugar", "hydrogenated oil"]
    },
    "juice": {
        "product_name": "Packaged Fruit Juice", "calories": 120, "sugars": 24, "sodium": 15,
        "found_ingredients": ["high fructose corn syrup", "artificial color"]
    },
    "cereal": {
        "product_name": "Breakfast Cereal Pack", "calories": 380, "sugars": 18, "sodium": 190,
        "found_ingredients": ["refined sugar"]
    }
}
