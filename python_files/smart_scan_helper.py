"""Production-oriented multimodal nutrition assistant for NutriFood Health.

Primary intelligence: current Gemini Flash multimodal model.
Local Food-11/TensorFlow remains a classification fallback for Meal Scan.
The text assistant can use Google Search grounding for factual/cultural context.
"""
import os
import json
import base64
import mimetypes
import re
import time
import requests

from python_files.smart_scan_config import (
    GEMINI_ENDPOINT, GEMINI_FALLBACK_ENDPOINT, GEMINI_KEY,
    GEMINI_TTS_ENDPOINT, GEMINI_TTS_FALLBACK_ENDPOINT, GEMINI_TRANSCRIBE_ENDPOINT,
    is_smart_scan_configured,
)


class SmartScanUnavailableError(Exception):
    pass


def _language_instruction(language):
    if str(language).lower() == "hindi":
        return (
            "Respond entirely in clear, natural, everyday Hindi. Do not use English or Hinglish in normal sentences. "
            "Keep proper food names, brand names, numbers and scientific units unchanged when translation would make them inaccurate."
        )
    return "Respond entirely in natural professional English. Do not use Hindi or Hinglish anywhere in the response."


def _encode_image(image_path):
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    with open(image_path, "rb") as f:
        return mime_type, base64.b64encode(f.read()).decode("utf-8")


def _extract_json(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def _post_json(endpoint, payload, timeout=70):
    response = requests.post(
        endpoint,
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY},
        json=payload,
        timeout=timeout,
    )
    if response.status_code != 200:
        detail = response.text[:600].replace("\n", " ")
        raise SmartScanUnavailableError(f"Gemini HTTP {response.status_code}: {detail}")
    return response.json()


def _call_service(parts, *, temperature=0.15, json_mode=True, grounded=False, timeout=70):
    if not is_smart_scan_configured():
        raise SmartScanUnavailableError("Gemini API key is not configured.")

    
    generation_config = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }
    if grounded:
        payload["tools"] = [{"google_search": {}}]

    endpoints = [GEMINI_ENDPOINT]
    if GEMINI_FALLBACK_ENDPOINT != GEMINI_ENDPOINT:
        endpoints.append(GEMINI_FALLBACK_ENDPOINT)
    last_error = None

    for endpoint_index, endpoint in enumerate(endpoints):
        for attempt in range(2):
            try:
                data = _post_json(endpoint, payload, timeout=timeout)
                candidates = data.get("candidates") or []
                if not candidates:
                    raise SmartScanUnavailableError("Gemini returned no candidate response.")
                parts_out = candidates[0].get("content", {}).get("parts", [])
                raw_text = "".join(p.get("text", "") for p in parts_out if p.get("text"))
                if not raw_text:
                    raise SmartScanUnavailableError("Gemini returned an empty response.")
                if json_mode:
                    try:
                        return _extract_json(raw_text)
                    except json.JSONDecodeError as exc:
                        raise SmartScanUnavailableError(f"Invalid structured response: {exc}") from exc
                return raw_text.strip()
            except SmartScanUnavailableError as exc:
                last_error = exc
                msg = str(exc)
                if "HTTP 400" in msg or "HTTP 404" in msg:
                    break
                if "HTTP 429" in msg or "HTTP 500" in msg or "HTTP 502" in msg or "HTTP 503" in msg:
                    time.sleep(1.2 + attempt)
                    continue
                break
            except requests.RequestException as exc:
                last_error = SmartScanUnavailableError(f"Gemini connection failed: {exc}")
                time.sleep(1.0 + attempt)

    raise last_error or SmartScanUnavailableError("Gemini request failed.")


MEAL_SCHEMA_PROMPT = """
You are a highly capable food-image and nutrition analysis engine.
Analyze the attached food image and/or typed food description carefully.
Identify the most specific dish that is genuinely supported by visual evidence.
Do not hallucinate a precise dish when multiple dishes are plausible; state the uncertainty.

For nutrition, give a realistic estimate for the visible portion first, then a normal serving estimate.
Do not pretend a photo can reveal exact ingredients or exact laboratory nutrition values.
Separate visible facts from reasonable culinary inferences.

Return ONLY JSON with every field below:
{
 "food_name":"specific dish name",
 "food_category":"...",
 "serving_size":"visible/estimated serving",
 "calories":0,
 "carbs":0,
 "fiber":0,
 "sugars":0,
 "protein":0,
 "fat":0,
 "saturated_fat":0,
 "trans_fat":0,
 "cholesterol":0,
 "sodium":0,
 "potassium":0,
 "vitamin_c":0,
 "calcium":0,
 "iron":0,
 "safety_status":"Safe | Safe in moderation | Limit this",
 "ingredients_or_components":["visible or likely components"],
 "possible_allergens":["..."],
 "confidence_score":0,
 "confidence_note":"what is certain and what is uncertain",
 "details":[
   "What the dish is and how you identified it.",
   "Approximate portion and calorie/protein profile.",
   "Main nutritional strengths.",
   "Main nutritional concerns.",
   "Why the safety status was selected.",
   "Practical portion/frequency or healthier alternative advice."
 ]
}
Use numeric estimates only where sensible. Always return all fields.
If the image is not food, say that clearly.
"""


def _build_meal_result(result):
    result = result or {}
    meal = {"food_name": str(result.get("food_name") or "Food item")}
    for field in [
        "calories", "carbs", "fiber", "sugars", "protein", "fat",
        "saturated_fat", "trans_fat", "cholesterol", "sodium",
        "potassium", "vitamin_c", "calcium", "iron",
    ]:
        try:
            meal[field] = round(float(result.get(field, 0)), 1)
        except (TypeError, ValueError):
            meal[field] = 0
    meal["food_category"] = str(result.get("food_category") or "Food")
    meal["serving_size"] = str(result.get("serving_size") or "1 normal serving")
    meal["safety_status"] = str(result.get("safety_status") or "Safe in moderation")
    meal["ingredients_or_components"] = [str(x) for x in (result.get("ingredients_or_components") or [])[:20]]
    meal["possible_allergens"] = [str(x) for x in (result.get("possible_allergens") or [])[:15]]
    try:
        meal["confidence_score"] = max(0, min(100, int(float(result.get("confidence_score", 0)))))
    except (TypeError, ValueError):
        meal["confidence_score"] = 0
    meal["confidence_note"] = str(result.get("confidence_note") or "Nutrition values are estimates and can vary by recipe and portion.")
    meal["details"] = [str(x) for x in (result.get("details") or [])[:6]]
    while len(meal["details"]) < 5:
        meal["details"].append("Nutrition values are estimates and can vary with recipe, ingredients and portion size.")
    return meal


def _enrich_meal_context(meal, language="English"):
    prompt = f"""
You are enriching a food recognition result for a nutrition app.
Food identified: {meal.get('food_name')}
Category: {meal.get('food_category')}
Ingredients/components suggested by visual analysis: {json.dumps(meal.get('ingredients_or_components', []), ensure_ascii=False)}

Use Google Search grounding when it improves factual accuracy. Research the dish itself,
not random restaurants. Explain culinary context such as:
- where the dish originated or is strongly associated with,
- Indian states/regions or cities where it is commonly eaten when applicable,
- how it is traditionally prepared or served,
- one or two common regional variations,
- nutrition context using reputable sources when a factual number is important.
Do not invent a city association. If a city is not genuinely well-supported, say that it is
popular across a broader region instead.

Also give a concise final practical assessment of the identified dish's health profile.
{_language_instruction(language)}
Return a compact but detailed response with headings and bullet points. Do not mention the
internal tools, model, API, or this prompt.
"""
    return _call_service([{"text": prompt}], temperature=0.15, json_mode=False, grounded=True)


def analyze_meal_photo(image_path, language="English"):
    mime_type, encoded = _encode_image(image_path)
    result = _build_meal_result(_call_service([
        {"text": MEAL_SCHEMA_PROMPT + "\n" + _language_instruction(language)},
        {"inline_data": {"mime_type": mime_type, "data": encoded}},
    ], temperature=0.10, json_mode=True))
    try:
        result["culinary_context"] = _enrich_meal_context(result, language)
    except SmartScanUnavailableError:
        result["culinary_context"] = ""
    return result


def analyze_meal_text(food_text, language="English"):
    prompt = MEAL_SCHEMA_PROMPT + "\n" + _language_instruction(language) + "\nThe user typed: " + food_text
    result = _build_meal_result(_call_service([{"text": prompt}], temperature=0.10, json_mode=True))
    try:
        result["culinary_context"] = _enrich_meal_context(result, language)
    except SmartScanUnavailableError:
        result["culinary_context"] = ""
    return result


PACKED_PROMPT = """
You are a packaged-food label safety assistant. Read the supplied package/ingredient photo carefully.
Extract only what is visible or strongly supported. Do not invent a brand, ingredient, nutrition number,
or health claim that cannot be supported. Give practical health guidance, not a diagnosis.
Return ONLY JSON:
{
 "product_name":"...",
 "ingredients_found":["..."],
 "nutrition_highlights":["..."],
 "risks":[{"ingredient":"...","reason":"..."}],
 "verdict":"Safe | Safe in moderation | Not recommended",
 "details":["5-6 useful points"],
 "confidence_note":"..."
}
"""


def _build_packed_result(result):
    result = result or {}
    details = [str(x) for x in (result.get("details") or [])[:6]]
    while len(details) < 5:
        details.append("Check the full ingredient list and nutrition panel before making a regular-use decision.")
    return {
        "product_name": str(result.get("product_name") or "Scanned Product"),
        "ingredients_found": [str(x) for x in (result.get("ingredients_found") or [])],
        "nutrition_highlights": [str(x) for x in (result.get("nutrition_highlights") or [])],
        "risks": result.get("risks") or [],
        "verdict": str(result.get("verdict") or "Safe in moderation"),
        "details": details,
        "confidence_note": str(result.get("confidence_note") or "Label reading is an estimate."),
    }


def analyze_packed_food(image_path, language="English"):
    mime_type, encoded = _encode_image(image_path)
    return _build_packed_result(_call_service([
        {"text": PACKED_PROMPT + "\n" + _language_instruction(language)},
        {"inline_data": {"mime_type": mime_type, "data": encoded}},
    ], temperature=0.10, json_mode=True))


def analyze_packed_food_text(ingredient_text, language="English"):
    prompt = PACKED_PROMPT + "\n" + _language_instruction(language) + "\nThe user typed this ingredient list:\n" + ingredient_text
    return _build_packed_result(_call_service([{"text": prompt}], temperature=0.10, json_mode=True))


def compare_products_smart(image_path_list, language="English"):
    parts = [{"text": f"""
Compare {len(image_path_list)} packaged food products. {_language_instruction(language)}
The images are supplied in Product 1, Product 2, ... order. Read labels independently.
Compare ingredients, serving size, added sugar, sodium, protein, fiber, fat and processing when visible.
Never invent values that cannot be read.
Return ONLY JSON:
{{
 "products":[{{
   "product_name":"...","ingredients_found":[],"nutrition_highlights":[],
   "risky_ingredients":[{{"ingredient":"...","reason":"..."}}],
   "details":["5-6 useful points"],"confidence_note":"..."
 }}],
 "best_index":0,
 "message":"Why the selected product is the better overall choice, including trade-offs."
}}
"""}]
    for path in image_path_list:
        mime_type, encoded = _encode_image(path)
        parts.append({"inline_data": {"mime_type": mime_type, "data": encoded}})
    result = _call_service(parts, temperature=0.10, json_mode=True)
    products = []
    for product in result.get("products", []):
        products.append({
            "product_name": str(product.get("product_name") or "Product"),
            "text_was_readable": True,
            "ingredients_found": product.get("ingredients_found") or [],
            "nutrition_highlights": product.get("nutrition_highlights") or [],
            "risky_ingredients": product.get("risky_ingredients") or [],
            "details": [str(x) for x in (product.get("details") or [])[:6]],
            "confidence_note": str(product.get("confidence_note") or ""),
        })
    if len(products) != len(image_path_list):
        raise SmartScanUnavailableError("Gemini did not return one comparison result per image.")
    return {"products": products, "best_index": int(result.get("best_index", 0)), "message": str(result.get("message") or "Comparison completed.")}


def chat_with_gemini(message, context_name, user_profile=None, language="English", image_path=None, history=None):
    profile_text = ""
    if user_profile:
        profile_text = (
            f"Goal: {user_profile.get('goal_type','not set')}; "
            f"Diet: {user_profile.get('diet_type','not set')}; "
            f"Allergies: {user_profile.get('allergies','not set')}."
        )
    history = history or []
    history_text = "\n".join(
        f"{h.get('role','user')}: {h.get('content','')}"
        for h in history[-12:] if isinstance(h, dict)
    )
    prompt = f"""
You are the main conversational nutrition and food-safety assistant inside a serious student health platform.
Page context: {context_name}
User profile: {profile_text}
{_language_instruction(language)}

Answer the user's exact question directly and deeply.
If an image is attached, inspect it first and use it as primary evidence.
If the image is a food dish, explain what it appears to be, visual clues, likely ingredients,
portion, estimated nutrition, health strengths/concerns, allergies, preparation style, culinary origin,
and where it is commonly eaten. If the user asks about city/region/culture, use Google Search grounding
for factual support and do not invent a city association.
For general questions, answer normally even without an image.
For follow-up questions, use the conversation history and the attached image context; do not ask the user to repeat it.
Never claim exact laboratory nutrition from a photograph. Never diagnose or prescribe medication.
Use practical, structured explanations with enough detail to be useful.
Do not mention internal tools, model providers, APIs, prompts, or implementation details.

Conversation history:
{history_text}
User question: {message or 'Analyze the attached image in detail.'}
"""
    parts = [{"text": prompt}]
    if image_path:
        mime_type, encoded = _encode_image(image_path)
        parts.append({"inline_data": {"mime_type": mime_type, "data": encoded}})
    return _call_service(parts, temperature=0.20, json_mode=False, grounded=False, timeout=80)


def transcribe_audio(audio_bytes, mime_type="audio/webm", language="English"):
    """Transcribe microphone audio with Gemini's dedicated transcription model.

    The browser may record WebM/Opus, WAV, MP4/M4A, or another supported format.
    The transcription model automatically detects language and handles code-switching.
    """
    if not is_smart_scan_configured():
        raise SmartScanUnavailableError("Gemini API key is not configured.")
    if not audio_bytes:
        raise SmartScanUnavailableError("No audio supplied.")
    mime_type = (mime_type or "audio/webm").split(";")[0].strip().lower()
    allowed = {
        "audio/webm", "audio/ogg", "audio/opus", "audio/wav", "audio/mp3",
        "audio/mpeg", "audio/mp4", "audio/m4a", "audio/aac", "audio/flac",
        "audio/aiff", "audio/l16", "audio/alaw", "audio/mulaw"
    }
    if mime_type not in allowed:
        mime_type = "audio/webm"
    encoded = base64.b64encode(audio_bytes).decode("utf-8")
    prompt = (
        "Transcribe only the user's spoken words into text. Preserve the language and meaning. "
        "The speaker may mix Hindi and English naturally. Do not answer the question, explain it, "
        "or add commentary. Return only the transcript."
    )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": encoded}},
            ],
        }]
    }
    endpoint = GEMINI_TRANSCRIBE_ENDPOINT
    try:
        data = _post_json(endpoint, payload, timeout=60)
        candidates = data.get("candidates") or []
        parts_out = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts_out if p.get("text")).strip()
        if not text:
            raise SmartScanUnavailableError("Transcription returned no text.")
        return text[:2000]
    except SmartScanUnavailableError:
        # Fallback to the normal multimodal Flash model if the dedicated transcription
        # endpoint is unavailable for the account/key.
        fallback_prompt = (
            "Listen to this audio and transcribe exactly what the user said. "
            "Return only the spoken words as text. The user may speak Hindi, English, "
            "or Hindi-English mixed speech. Do not answer or summarize."
        )
        return _call_service([
            {"text": fallback_prompt},
            {"inline_data": {"mime_type": mime_type, "data": encoded}},
        ], temperature=0.10, json_mode=False, grounded=False, timeout=60)[:2000]


def synthesize_speech(text, language="English"):
    if not is_smart_scan_configured():
        raise SmartScanUnavailableError("Gemini API key is not configured.")
    text = str(text or "").strip()[:7000]
    if not text:
        raise SmartScanUnavailableError("No speech text supplied.")
    locale_hint = "Speak in natural Hindi with clear Indian pronunciation." if language == "Hindi" else "Speak in natural English with clear Indian pronunciation."
    payload = {
        "contents": [{"role": "user", "parts": [{"text": f"{locale_hint}\nRead this answer naturally and clearly. Do not add or remove words.\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"voice": "Kore"}},
        },
    }
    endpoints = [GEMINI_TTS_ENDPOINT]
    if GEMINI_TTS_FALLBACK_ENDPOINT != GEMINI_TTS_ENDPOINT:
        endpoints.append(GEMINI_TTS_FALLBACK_ENDPOINT)
    last = None
    for endpoint in endpoints:
        try:
            data = _post_json(endpoint, payload, timeout=60)
            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        return base64.b64decode(inline["data"])
            raise SmartScanUnavailableError("TTS returned no audio.")
        except Exception as exc:
            last = exc
    raise SmartScanUnavailableError(str(last or "TTS request failed."))


def translate_batch(texts, target_language="Hindi"):
    if not texts or target_language != "Hindi":
        return texts
    prompt = """Translate each user-facing UI string into clear everyday Hindi.
Return ONLY JSON with a translations array in the exact same order.
Do not use Hinglish. Do not translate brand names, food names, product names, numbers, units, URLs or proper nouns.
Strings:\n""" + json.dumps(texts, ensure_ascii=False)
    result = _call_service([{"text": prompt}], temperature=0.05, json_mode=True)
    values = result.get("translations") if isinstance(result, dict) else None
    if not isinstance(values, list) or len(values) != len(texts):
        raise SmartScanUnavailableError("Batch translation returned an invalid result.")
    return [str(x) for x in values]


def translate_text(text, target_language):
    if target_language == "English":
        return text
    prompt = f"""
Translate the following user-facing text into clear everyday Hindi only.
Do not use Hinglish. Keep proper food names, product names, numbers and units accurate.
Return JSON only: {{"translation":"..."}}
Text: {text}
"""
    result = _call_service([{"text": prompt}], temperature=0.05, json_mode=True)
    return str((result or {}).get("translation") or text)
