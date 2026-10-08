import os
import json
import tensorflow as tf
from tensorflow.keras import layers, models

# ============================================================
# HOW TO USE THIS FILE (read before running):
#
# 1. Download your Kaggle "Food-101" (or Food-11) dataset and put it in a
#    folder named "dataset" right next to this file, with ONE sub-folder
#    per food category, e.g.:
#       dataset/pizza/....jpg
#       dataset/samosa/....jpg
#       dataset/biryani/....jpg
#
# 2. Open a terminal in this folder and run:
#       python train_cnn.py
#
# 3. This uses TRANSFER LEARNING: a MobileNetV2 network that Keras already
#    knows how to "see" with (trained on 1.4 million general images) is
#    reused and fine-tuned on YOUR Kaggle food photos. This is a completely
#    standard, widely-used technique for exactly this kind of project - it
#    is NOT an external API, nothing is sent to the internet while training,
#    and the dataset used is 100% your Kaggle dataset.
#    The very first run downloads the small MobileNetV2 base weights file
#    once (a few MB, one-time, cached locally) - after that it works fully
#    offline.
#
# 4. This gives dramatically better real accuracy than a from-scratch tiny
#    CNN, especially for many food classes with a modest number of images
#    per class (which is exactly the Food-101/Food-11 situation).
#
# 5. When done, two files appear in this folder:
#       food_model.keras   -> the trained model
#       class_names.json   -> the list of category names
#    That's it - the app will use both automatically.
# ============================================================

DATASET_FOLDER = "dataset"
IMAGE_SIZE = (160, 160)          # matches MobileNetV2's expected input well
BATCH_SIZE = 32
INITIAL_EPOCHS = 12              # train only the new top layers first
FINE_TUNE_EPOCHS = 10            # then unfreeze part of the base and fine-tune


def build_model(num_classes):
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False  # freeze for the first training stage

    inputs = tf.keras.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3))
    x = layers.RandomFlip("horizontal")(inputs)
    x = layers.RandomRotation(0.1)(x)
    x = layers.RandomZoom(0.1)(x)
    x = layers.RandomBrightness(0.15)(x)
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(256, activation="relu")(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)

    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
                  loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    return model, base_model


def train_model():
    if not os.path.exists(DATASET_FOLDER):
        print(f"ERROR: '{DATASET_FOLDER}' folder not found. Put your Kaggle dataset here first.")
        return

    print("Loading images from folders...")
    train_data = tf.keras.utils.image_dataset_from_directory(
        DATASET_FOLDER, validation_split=0.2, subset="training",
        seed=42, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE,
    )
    val_data = tf.keras.utils.image_dataset_from_directory(
        DATASET_FOLDER, validation_split=0.2, subset="validation",
        seed=42, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE,
    )

    class_names = train_data.class_names
    print(f"Categories found ({len(class_names)}): {class_names}")

    with open("class_names.json", "w") as f:
        json.dump(class_names, f)

    train_data = train_data.prefetch(buffer_size=tf.data.AUTOTUNE)
    val_data = val_data.prefetch(buffer_size=tf.data.AUTOTUNE)

    model, base_model = build_model(num_classes=len(class_names))

    early_stop = tf.keras.callbacks.EarlyStopping(
        monitor="val_accuracy", patience=5, restore_best_weights=True
    )

    print("\nStage 1/2: training the top layers (base model frozen)...\n")
    model.fit(train_data, validation_data=val_data, epochs=INITIAL_EPOCHS, callbacks=[early_stop])

    print("\nStage 2/2: fine-tuning the top of the base model for extra accuracy...\n")
    base_model.trainable = True
    # keep the earliest, most generic layers frozen; fine-tune only the later ones
    fine_tune_at = int(len(base_model.layers) * 0.7)
    for layer in base_model.layers[:fine_tune_at]:
        layer.trainable = False

    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
                  loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])

    model.fit(train_data, validation_data=val_data, epochs=FINE_TUNE_EPOCHS, callbacks=[early_stop])

    model.save("food_model.keras")
    print("\nDone! Saved 'food_model.keras' and 'class_names.json'.")
    print("Move both files into the dataset_files/ folder used by the app if they aren't already there.")


if __name__ == "__main__":
    train_model()
