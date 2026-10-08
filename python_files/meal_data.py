# Nutrition reference data for each of the 11 Food-11 categories.
# These are typical average values for a standard serving of that food type.
# The image model predicts the category name, and this file supplies the
# matching nutrition facts.

FOOD_NUTRITION_DATA = {
    "Bread": {
        "food_name": "Bread", "calories": 265, "carbs": 49, "fiber": 2.7, "sugars": 5,
        "protein": 9, "fat": 3.2, "saturated_fat": 0.7, "trans_fat": 0.0, "cholesterol": 0,
        "sodium": 490, "potassium": 115, "vitamin_c": 0, "calcium": 15, "iron": 10,
        "safety_status": "Moderate - eat in control"
    },
    "Dairy Product": {
        "food_name": "Dairy Product", "calories": 150, "carbs": 12, "fiber": 0, "sugars": 12,
        "protein": 8, "fat": 8, "saturated_fat": 5, "trans_fat": 0.2, "cholesterol": 24,
        "sodium": 105, "potassium": 322, "vitamin_c": 2, "calcium": 28, "iron": 0,
        "safety_status": "Safe in moderation"
    },
    "Dessert": {
        "food_name": "Dessert", "calories": 350, "carbs": 45, "fiber": 1.5, "sugars": 30,
        "protein": 4, "fat": 17, "saturated_fat": 9, "trans_fat": 1.5, "cholesterol": 40,
        "sodium": 200, "potassium": 120, "vitamin_c": 0, "calcium": 8, "iron": 4,
        "safety_status": "High sugar - occasional only"
    },
    "Egg": {
        "food_name": "Egg", "calories": 155, "carbs": 1.1, "fiber": 0, "sugars": 1.1,
        "protein": 13, "fat": 11, "saturated_fat": 3.3, "trans_fat": 0.02, "cholesterol": 373,
        "sodium": 124, "potassium": 126, "vitamin_c": 0, "calcium": 5, "iron": 6,
        "safety_status": "Safe Balanced"
    },
    "Fried food": {
        "food_name": "Fried Food", "calories": 480, "carbs": 42, "fiber": 3, "sugars": 3,
        "protein": 15, "fat": 29, "saturated_fat": 6, "trans_fat": 2, "cholesterol": 45,
        "sodium": 680, "potassium": 300, "vitamin_c": 4, "calcium": 8, "iron": 8,
        "safety_status": "Unsafe - high fat"
    },
    "Meat": {
        "food_name": "Meat", "calories": 250, "carbs": 0, "fiber": 0, "sugars": 0,
        "protein": 26, "fat": 17, "saturated_fat": 6, "trans_fat": 0.3, "cholesterol": 90,
        "sodium": 75, "potassium": 380, "vitamin_c": 0, "calcium": 2, "iron": 15,
        "safety_status": "Safe in moderation"
    },
    "Noodles-Pasta": {
        "food_name": "Noodles / Pasta", "calories": 220, "carbs": 43, "fiber": 2.5, "sugars": 2,
        "protein": 8, "fat": 1.3, "saturated_fat": 0.2, "trans_fat": 0.0, "cholesterol": 0,
        "sodium": 350, "potassium": 60, "vitamin_c": 0, "calcium": 2, "iron": 8,
        "safety_status": "Safe Balanced"
    },
    "Rice": {
        "food_name": "Rice", "calories": 205, "carbs": 45, "fiber": 0.6, "sugars": 0.1,
        "protein": 4.3, "fat": 0.4, "saturated_fat": 0.1, "trans_fat": 0.0, "cholesterol": 0,
        "sodium": 2, "potassium": 55, "vitamin_c": 0, "calcium": 2, "iron": 2,
        "safety_status": "Safe Balanced"
    },
    "Seafood": {
        "food_name": "Seafood", "calories": 206, "carbs": 0, "fiber": 0, "sugars": 0,
        "protein": 22, "fat": 12, "saturated_fat": 3, "trans_fat": 0.0, "cholesterol": 55,
        "sodium": 380, "potassium": 380, "vitamin_c": 2, "calcium": 4, "iron": 6,
        "safety_status": "Healthy"
    },
    "Soup": {
        "food_name": "Soup", "calories": 120, "carbs": 15, "fiber": 2, "sugars": 4,
        "protein": 6, "fat": 4, "saturated_fat": 1.2, "trans_fat": 0.0, "cholesterol": 8,
        "sodium": 830, "potassium": 250, "vitamin_c": 8, "calcium": 4, "iron": 6,
        "safety_status": "Safe - watch sodium"
    },
    "Vegetable-Fruit": {
        "food_name": "Vegetable / Fruit", "calories": 80, "carbs": 18, "fiber": 4, "sugars": 10,
        "protein": 2, "fat": 0.3, "saturated_fat": 0.05, "trans_fat": 0.0, "cholesterol": 0,
        "sodium": 10, "potassium": 350, "vitamin_c": 40, "calcium": 3, "iron": 4,
        "safety_status": "Healthy"
    }
}

def get_food_nutrition(label):
    """Always returns a usable nutrition dict for whatever label the model/
    text-match gives us - even if that exact label isn't in our table yet
    (e.g. after retraining on a bigger Kaggle dataset with more specific
    dish names). This is what stops the app from ever saying 'no result'
    for a real prediction."""
    if label in FOOD_NUTRITION_DATA:
        return FOOD_NUTRITION_DATA[label].copy()

    for key in FOOD_NUTRITION_DATA:
        if key.lower() == label.lower():
            return FOOD_NUTRITION_DATA[key].copy()

    
    return {
        "food_name": label.replace("_", " ").replace("-", " ").title(),
        "calories": 250, "carbs": 30, "fiber": 2, "sugars": 5,
        "protein": 10, "fat": 10, "saturated_fat": 3, "trans_fat": 0.2,
        "cholesterol": 30, "sodium": 300, "potassium": 200, "vitamin_c": 5,
        "calcium": 10, "iron": 5,
        "safety_status": "Estimated - exact nutrition data for this item isn't in our table yet",
    }


def get_goal_note(nutrition, personal_info):
    """Adds one extra line based on the user's saved fitness goal - only
    if they actually filled Personal Info. If they skipped it, this
    returns None and the normal common safety_status is the only answer
    shown (same for every user)."""
    if not personal_info or not personal_info.get('is_filled'):
        return None

    goal = (personal_info.get('goal_type') or '').lower()
    calories = nutrition.get('calories', 0)
    protein = nutrition.get('protein', 0)
    carbs = nutrition.get('carbs', 0)

    if 'fat loss' in goal and calories > 300:
        return "This is on the higher side for your fat-loss goal - keep the portion small."
    if 'muscle' in goal and protein < 10:
        return "Low protein for your muscle-building goal - add a protein side with this."
    if 'stamina' in goal and carbs < 15:
        return "Low in carbs for your stamina goal - you may need extra energy food too."
    return "This fits fine with your saved goal in a normal portion."


# used when the user types the meal name instead of / along with a picture
MEAL_TEXT_KEYWORDS = {
    "bread": "Bread", "toast": "Bread", "bun": "Bread",
    "milk": "Dairy Product", "cheese": "Dairy Product", "yogurt": "Dairy Product", "curd": "Dairy Product",
    "cake": "Dessert", "ice cream": "Dessert", "sweet": "Dessert", "chocolate": "Dessert",
    "egg": "Egg", "omelette": "Egg",
    "fry": "Fried food", "fried": "Fried food", "chips": "Fried food", "pakora": "Fried food",
    "chicken": "Meat", "mutton": "Meat", "meat": "Meat",
    "noodles": "Noodles-Pasta", "pasta": "Noodles-Pasta", "maggi": "Noodles-Pasta",
    "rice": "Rice", "biryani": "Rice", "pulao": "Rice",
    "fish": "Seafood", "prawns": "Seafood", "seafood": "Seafood",
    "soup": "Soup",
    "salad": "Vegetable-Fruit", "vegetable": "Vegetable-Fruit", "fruit": "Vegetable-Fruit",
    "apple": "Vegetable-Fruit", "banana": "Vegetable-Fruit"
}
