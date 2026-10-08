import pytesseract
from PIL import Image


def read_text_from_image(image_path):
    """Reads whatever text is printed in the photo (like an ingredient list).
    Returns the text in lowercase so keyword matching works easily.
    If the photo has no readable text, returns an empty string."""
    try:
        img = Image.open(image_path)
        extracted_text = pytesseract.image_to_string(img)
        return extracted_text.strip().lower()
    except Exception:
        return ""
