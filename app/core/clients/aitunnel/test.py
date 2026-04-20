import base64

def save_b64_to_image(txt_file_path, output_image_path):
    # 1. Читаем содержимое текстового файла
    with open(txt_file_path, "r") as f:
        b64_string = f.read().strip()

    # 2. Очистка (на случай, если внутри записан Data URL)
    # Если строка начинается с "data:image/png;base64,", обрезаем эту часть
    if "," in b64_string:
        b64_string = b64_string.split(",")[1]

    try:
        # 3. Декодируем base64 в бинарные данные
        img_data = base64.b64decode(b64_string)

        # 4. Сохраняем в файл изображения
        with open(output_image_path, "wb") as img_file:
            img_file.write(img_data)
        
        print(f"Успех! Картинка сохранена как: {output_image_path}")
        
    except Exception as e:
        print(f"Ошибка при декодировании: {e}")

# Использование:
save_b64_to_image("image_31flash_image_b64.txt", "restored_image_31flash.png")