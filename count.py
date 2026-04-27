
import json
INPUT_FILE = "output_detail_v2.json"
    # 1. JSON датаг унших
print(f"Файлаас дата уншиж байна: {INPUT_FILE}")
try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)
except FileNotFoundError:
    print("Оролтын JSON файл олдсонгүй!")

total_items = len(items)
print(f"Нийт {total_items} дата олдлоо.")   