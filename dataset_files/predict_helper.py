import os
import json
import numpy as np
try:
    import tensorflow as tf
except ImportError:
    tf = None

BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_FOLDER, "food_model.keras")
CLASS_NAMES_PATH = os.path.join(BASE_FOLDER, "class_names.json")

# NOTE: must match IMAGE_SIZE used in train_cnn.py when the model was trained.
# The transfer-learning model in this project is trained at 160x160.
# (If you're still using the OLD from-scratch model, change this to (96, 96).)
IMAGE_SIZE = (160, 160)

_model = None
_class_names = None


def load_model_once():
    global _model, _class_names
    if tf is None:
        raise RuntimeError("TensorFlow is not installed; Kaggle fallback is unavailable.")
    if _model is None:
        _model = tf.keras.models.load_model(MODEL_PATH)
        with open(CLASS_NAMES_PATH) as f:
            _class_names = json.load(f)
    return _model, _class_names


def predict_food_image(image_path):
    """Always returns a real answer - never blocks with 'could not identify'.
    If the model isn't confident, is_confident=False is returned so the UI
    can show a gentle heads-up, but the best-guess label is still given so
    the user always gets a result."""
    model, class_names = load_model_once()

    img = tf.keras.utils.load_img(image_path, target_size=IMAGE_SIZE)
    img_array = tf.keras.utils.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)

    predictions = model.predict(img_array, verbose=0)[0]

    sorted_indexes = np.argsort(predictions)[::-1]
    top_index = int(sorted_indexes[0])
    top_label = class_names[top_index]
    top_confidence = round(float(predictions[top_index]) * 100, 1)

    second_index = int(sorted_indexes[1]) if len(class_names) > 1 else top_index
    second_label = class_names[second_index]
    second_confidence = round(float(predictions[second_index]) * 100, 1)

    return {
        "label": top_label,
        "confidence": top_confidence,
        "second_label": second_label,
        "second_confidence": second_confidence,
        # this flag is only used to show a soft "try a clearer photo" hint -
        # it is NEVER used to hide/refuse a result anymore.
        "is_confident": top_confidence >= 55.0,
    }
