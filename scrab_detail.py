import asyncio
import math
from playwright.async_api import async_playwright
from scrab_detail_file import BATCH_SIZE, CONCURRENCY_LIMIT, INPUT_FILE, OUTPUT_FILE

BASE = "https://www.unegui.mn"

# DETAIL_URL = BASE + "/adv/9224806_khud-zaisan/"  # жишээ link
DETAIL_URL = "https://www.unegui.mn/adv/10139016_khunnu-1-r-eelzhind-117-67mkv-4-oroo/"
INPUT_FILE = "unegui_data_20260221.json"   # Унших JSON файлын нэр
OUTPUT_FILE = "output_detail_v2.json"  # Хадгалах JSON файлын нэр

# Нэгэн зэрэг унших хуудасны тоо (Компьютерын хүчин чадлаас хамаарч ихэсгэж/багасгаж болно)
CONCURRENCY_LIMIT = 10
BATCH_SIZE = 1000           # Хэдэн дата уншаад файлаа хадгалах вэ


async def convert_keys(data: dict):
    mapping = {
        "Шал": "floor_type",
        "Тагт": "balcony",
        "Ашиглалтанд орсон он": "year_commissioned",
        "Гараж": "garage",
        "Цонх": "window_type",
        "Барилгын давхар": "building_floors",
        "Хаалга": "door_type",
        "Талбай": "area_sqm",
        "Хэдэн давхарт": "floor_number",
        "Төлбөрийн нөхцөл": "payment_terms",
        "Цонхны тоо": "window_count",
        "Барилгын явц": "building_status",
        "Цахилгаан шаттай эсэх": "has_elevator",
    }

    return {mapping.get(k, k): v for k, v in data.items()}


async def scrape_detail(item: str, semaphore):

    async with semaphore:
        async with async_playwright() as p:
            url = item["link"]
            print(f"Scraping detail for URL: {url}")
            browser = await p.chromium.launch(headless=True)

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(".announcement-content-container")

            data = await page.evaluate("""
            () => {
            const result = {};

            // ---------------------
            // Basic Info
            // ---------------------
            result.title = document.querySelector("#ad-title")?.innerText.trim();

            result.location = document.querySelector(
                ".announcement__location span"
            )?.innerText.trim();

            result.published_date = document.querySelector(
                ".date-meta"
            )?.innerText.replace("Нийтэлсэн:", "").trim();

            result.ad_number = document.querySelector(
                ".number-announcement [itemprop='sku']"
            )?.innerText.trim();

            result.views = document.querySelector(
                ".counter-views"
            )?.innerText.replace("Үзсэн :", "").trim();

            // ---------------------
            // Images
            // ---------------------
            result.images = Array.from(
                document.querySelectorAll(".announcement__images-item")
            ).map(img => img.getAttribute("data-full") || img.src);

            // ---------------------
            // Map / Coordinates
            // ---------------------
            const map = document.querySelector(".map-location__container");
            if (map) {
                result.latitude = map.dataset.defaultLat;
                result.longitude = map.dataset.defaultLng;
            }

            result.map_location_text = document.querySelector(
                ".map-location"
            )?.innerText.replace("Байршил:", "").trim();

            // ---------------------
            // Description
            // ---------------------
            result.description = document.querySelector(
                ".announcement-description"
            )?.innerText.trim();

            // ---------------------
            // Characteristics
            // ---------------------
            result.characteristics = {};
            document.querySelectorAll(
                ".announcement-characteristics li"
            ).forEach(li => {
                const key = li.querySelector(".key-chars")?.innerText.replace(":", "").trim();
                const value = li.querySelector(".value-chars")?.innerText.trim();
                if (key && value) {
                    result.characteristics[key] = value;
                }
            });

            return result;
        }
        """)

            await browser.close()
            print("browser closed")
            result = await convert_keys(data["characteristics"])
            data["characteristics"] = result
            data["title"] = item["title"]
            data["price"] = item["price"]
            data["date"] = item["date"]
            data["place"] = item["place"] 
            data["id"]  = item["id"]
            data["link"] = item["link"]
            return data


async def main():
    print(f"Файлаас дата уншиж байна: {INPUT_FILE}")
    data = []
    import json
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)

    except FileNotFoundError:
        print("Оролтын JSON файл олдсонгүй!")
        return

    total_items = len(items)
    print(f"Нийт {total_items} дата олдлоо.")

    # Зэрэг ажиллах хязгаар
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    # 3. Багцлан боловсруулах (Batch processing)
    total_batches = math.ceil(total_items / BATCH_SIZE)

    for i in range(total_batches):
        start_idx = i * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_items)
        current_batch = items[start_idx:end_idx]

        print(
            f"--- Batch {i+1}/{total_batches} ажиллаж байна. (Мөрүүд: {start_idx} - {end_idx}) ---")

        # Тухайн багцад байгаа бүх task-ийг үүсгээд зэрэг ажиллуулах
        tasks = [scrape_detail(item, semaphore)
                 for item in current_batch]
        result = await asyncio.gather(*tasks)

        # Багц дууссаны дараа үр дүнгээ файлаа хадгалах
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        print(f"Batch {i+1} амжилттай хадгалагдлаа.")
if __name__ == "__main__":
    asyncio.run(main())
