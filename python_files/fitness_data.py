# All functions with well known formulas.

ACTIVITY_MULTIPLIER = {
    "Sedentary (little or no exercise)": 1.2,
    "Light (exercise 1-3 days/week)": 1.375,
    "Moderate (exercise 3-5 days/week)": 1.55,
    "Active (exercise 6-7 days/week)": 1.725,
    "Very Active (hard exercise + physical job)": 1.9
}


def calculate_bmi(weight_kg, height_cm):
    height_m = height_cm / 100
    bmi_value = weight_kg / (height_m * height_m)
    bmi_value = round(bmi_value, 1)

    if bmi_value < 18.5:
        category = "Underweight"
    elif bmi_value < 25:
        category = "Normal"
    elif bmi_value < 30:
        category = "Overweight"
    else:
        category = "Obese"

    return bmi_value, category


def calculate_calorie_need(gender, weight_kg, height_cm, age, activity_level):
    # Mifflin-St Jeor formula
    if gender == "Male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    multiplier = ACTIVITY_MULTIPLIER.get(activity_level, 1.2)
    daily_calories = round(bmr * multiplier)
    return daily_calories


def calculate_water_intake(weight_kg):
    # rough rule: 35 ml per kg of body weight
    water_ml = round(weight_kg * 35)
    water_liters = round(water_ml / 1000, 2)
    return water_liters


def calculate_step_goal(goal_type):
    
    step_goal_map = {
        "Fat Loss & Lean Body": 10000,
        "Muscle Building": 7000,
        "Stamina & Endurance": 12000,
        "General Wellness": 8000
    }
    return step_goal_map.get(goal_type, 8000)
