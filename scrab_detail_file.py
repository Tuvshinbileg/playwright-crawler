import asyncio
import json
import math
from playwright.async_api import async_playwright

# Тохиргоонууд
INPUT_FILE = "unegui_data_20260221.json"   # Унших JSON файлын нэр
OUTPUT_FILE = "output.json" # Хадгалах JSON файлын нэр
CONCURRENCY_LIMIT = 15      # Нэгэн зэрэг унших хуудасны тоо (Компьютерын хүчин чадлаас хамаарч ихэсгэж/багасгаж болно)
BATCH_SIZE = 1000           # Хэдэн дата уншаад файлаа хадгалах вэ

async def convert_keys(data: dict):
    if not data:
        return {}
        
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

async def scrape_detail(url: str, context):
    """Тухайн URL-аас мэдээлэл татах функц. Browser биш Context хүлээж авна."""
    page = await context.new_page()
    try:
        # timeout-ийг 60 секунд болгосон. Учир нь олон хуудас зэрэг уншихад интернэт удааширч болно
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector(".announcement-content-container", timeout=30000)

        data = await page.evaluate("""
        () => {
            const result = {};
            // Basic Info
            result.ad_title = document.querySelector("#ad-title")?.innerText.trim();
            result.location = document.querySelector(".announcement__location span")?.innerText.trim();
            result.published_date = document.querySelector(".date-meta")?.innerText.replace("Нийтэлсэн:", "").trim();
            result.ad_number = document.querySelector(".number-announcement [itemprop='sku']")?.innerText.trim();
            result.views = document.querySelector(".counter-views")?.innerText.replace("Үзсэн :", "").trim();

            // Images
            result.images = Array.from(document.querySelectorAll(".announcement__images-item"))
                                 .map(img => img.getAttribute("data-full") || img.src);

            // Map / Coordinates
            const map = document.querySelector(".map-location__container");
            if (map) {
                result.latitude = map.dataset.defaultLat;
                result.longitude = map.dataset.defaultLng;
            }
            result.map_location_text = document.querySelector(".map-location")?.innerText.replace("Байршил:", "").trim();

            // Description
            result.description = document.querySelector(".announcement-description")?.innerText.trim();

            // Characteristics
            result.characteristics = {};
            document.querySelectorAll(".announcement-characteristics li").forEach(li => {
                const key = li.querySelector(".key-chars")?.innerText.replace(":", "").trim();
                const value = li.querySelector(".value-chars")?.innerText.trim();
                if (key && value) {
                    result.characteristics[key] = value;
                }
            });

            return result;
        }
        """)
        
        # Key хөрвүүлэх
        result_chars = await convert_keys(data.get("characteristics", {}))
        data["characteristics"] = result_chars
        return data

    except Exception as e:
        print(f"[Алдаа] {url} уншихад алдаа гарлаа: {str(e)}")
        return {"error": str(e)}
    finally:
        # Ямар ч тохиолдолд Page(Tab)-ийг хааж RAM-аа суллах ёстой
        await page.close()

async def process_item(item: dict, context, semaphore: asyncio.Semaphore):
    """Нэг обьектийг боловсруулах үйлдэл (Семафороор хязгаарлагдана)"""
    async with semaphore:
        url = item.get("link")
        if url:
            # Хэрэв өмнө нь уншчихсан (detail байгаа) бол алгасах
            if "detail" in item and not item.get("detail", {}).get("error"):
                return
            
            detail_data = await scrape_detail(url, context)
            item["detail"] = detail_data

async def main():
    # 1. JSON датаг унших
    print(f"Файлаас дата уншиж байна: {INPUT_FILE}")
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        print("Оролтын JSON файл олдсонгүй!")
        return

    total_items = len(items)
    print(f"Нийт {total_items} дата олдлоо.")

    # 2. Playwright эхлүүлэх
    async with async_playwright() as p:
        # headless=True байх нь хурдан бөгөөд бага нөөц шаардана
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        
        # Зэрэг ажиллах хязгаар
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

        # 3. Багцлан боловсруулах (Batch processing)
        total_batches = math.ceil(total_items / BATCH_SIZE)
        
        for i in range(total_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_items)
            current_batch = items[start_idx:end_idx]
            
            print(f"--- Batch {i+1}/{total_batches} ажиллаж байна. (Мөрүүд: {start_idx} - {end_idx}) ---")
            
            # Тухайн багцад байгаа бүх task-ийг үүсгээд зэрэг ажиллуулах
            tasks = [process_item(item, context, semaphore) for item in current_batch]
            result = await asyncio.gather(*tasks)
            
            # Багц дууссаны дараа үр дүнгээ файлаа хадгалах
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
                
            print(f"Batch {i+1} амжилттай хадгалагдлаа.")

        await browser.close()
    
    print("Бүх үйлдэл амжилттай дууслаа!")

if __name__ == "__main__":
    asyncio.run(main())