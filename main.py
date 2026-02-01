import sys
from typing import List, Optional, Set
from playwright.sync_api import sync_playwright, Page
from dataclasses import dataclass, asdict
import pandas as pd
import argparse
import time
import os
import shutil
import urllib.parse

@dataclass
class Place:
    name: str = ""
    address: str = ""
    website: str = ""
    phone_number: str = ""
    whatsapp: str = ""
    reviews_count: Optional[int] = None
    reviews_average: Optional[float] = None
    store_shopping: str = "No"
    in_store_pickup: str = "No"
    store_delivery: str = "No"
    place_type: str = ""
    opens_at: str = ""
    introduction: str = ""

def extract_text(page: Page, xpath: str) -> str:
    try:
        locator = page.locator(xpath)
        if locator.count() > 0:
            return locator.first.inner_text()
    except:
        return ""
    return ""

def extract_place(page: Page) -> Place:
    name_xpath = '//h1[contains(@class, "DUwDvf")]'
    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
    whatsapp_xpath = '//button[contains(@data-item-id, "phone:whatsapp:")]//div[contains(@class, "fontBodyMedium")]'
    reviews_count_xpath = '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]//div//span//span//span[@aria-label]'
    reviews_average_xpath = '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]//div//span[@aria-hidden]'
    info_xpaths = ['//div[@class="LTs0Rc"][1]', '//div[@class="LTs0Rc"][2]', '//div[@class="LTs0Rc"][3]']
    opens_at_xpath = '//button[contains(@data-item-id, "oh")]//div[contains(@class, "fontBodyMedium")]'
    place_type_xpath = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'
    intro_xpath = '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]'

    place = Place()
    place.name = extract_text(page, name_xpath)
    place.address = extract_text(page, address_xpath)
    place.website = extract_text(page, website_xpath)
    place.phone_number = extract_text(page, phone_number_xpath)
    place.whatsapp = extract_text(page, whatsapp_xpath)
    place.place_type = extract_text(page, place_type_xpath)
    place.introduction = extract_text(page, intro_xpath) or "None Found"

    reviews_count_raw = extract_text(page, reviews_count_xpath)
    if reviews_count_raw:
        try:
            temp = reviews_count_raw.replace('\xa0', '').replace('(','').replace(')','').replace(',','')
            place.reviews_count = int(temp)
        except: pass

    reviews_avg_raw = extract_text(page, reviews_average_xpath)
    if reviews_avg_raw:
        try:
            temp = reviews_avg_raw.replace(' ','').replace(',','.')
            place.reviews_average = float(temp)
        except: pass

    for info_xpath in info_xpaths:
        info_raw = extract_text(page, info_xpath)
        if info_raw and '·' in info_raw:
            parts = info_raw.split('·')
            if len(parts) > 1:
                check = parts[1].lower()
                if 'shop' in check: place.store_shopping = "Yes"
                if 'pickup' in check: place.in_store_pickup = "Yes"
                if 'delivery' in check: place.store_delivery = "Yes"

    opens_at_raw = extract_text(page, opens_at_xpath)
    if opens_at_raw:
        place.opens_at = opens_at_raw.split('⋅')[1].replace("\u202f","") if '⋅' in opens_at_raw else opens_at_raw
    
    return place

def get_browser_path():
    if os.name == 'nt':
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ]
        for p in possible_paths:
            if os.path.exists(p): return p
    paths = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/firefox"]
    for p in paths:
        if os.path.exists(p): return p
    return shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("firefox")

def scrape_places(search_for: str, total: int) -> List[Place]:
    places: List[Place] = []
    seen_names: Set[str] = set()
    browser_exec_path = get_browser_path()
    print(f"--> Using Browser: {browser_exec_path}")

    with sync_playwright() as p:
        browser_type = p.firefox if "firefox" in str(browser_exec_path).lower() else p.chromium
        launch_args = ["--no-sandbox", "--disable-dev-shm-usage"]
        if "chromium" in str(browser_exec_path).lower():
            launch_args.extend(["--disable-gpu", "--disable-setuid-sandbox", "--no-zygote"])

        browser = browser_type.launch(executable_path=browser_exec_path, headless=True, args=launch_args)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        try:
            query = urllib.parse.quote_plus(search_for)
            search_url = f"https://www.google.com/maps/search/{query}"
            print(f"--> Use Direct Access Method")
            page.goto(search_url, timeout=120000)
            
            try:
                consent_btn = page.locator('//button').filter(has_text="Accept all")
                if consent_btn.count() > 0:
                    consent_btn.first.click()
                    time.sleep(5)
            except: pass

            page.wait_for_selector('//a[contains(@href, "/maps/place/")]', timeout=90000)
            
            while len(places) < total:
                listings = page.locator('//a[contains(@href, "/maps/place/")]').all()
                if len(listings) < total + 2: 
                    page.mouse.wheel(0, 5000)
                    time.sleep(3)
                    listings = page.locator('//a[contains(@href, "/maps/place/")]').all()

                for listing in listings:
                    if len(places) >= total: break
                    try:
                        listing.scroll_into_view_if_needed()
                        listing.click()
                        page.wait_for_selector('//h1[contains(@class, "DUwDvf")]', timeout=30000)
                        time.sleep(2)
                        place = extract_place(page)
                        if place.name and place.name not in seen_names:
                            seen_names.add(place.name)
                            places.append(place)
                            print(f"--> [{len(places)}/{total}] Extracted: {place.name}")
                    except: continue
                
                if len(places) < total:
                    page.mouse.wheel(0, 10000)
                    time.sleep(4)
        finally:
            browser.close()
    return places

def save_data(places: List[Place], output_path: str, append: bool = False):
    new_df = pd.DataFrame([asdict(place) for place in places])
    if new_df.empty:
        print("--> Error: No data found.")
        return

    if output_path.endswith('.xlsx'):
        if append and os.path.exists(output_path):
            try:
                old_df = pd.read_excel(output_path)
                df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=['name'])
            except: df = new_df
        else:
            df = new_df

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            worksheet = writer.sheets['Sheet1']
            for i, col in enumerate(df.columns):
                column_letter = chr(65 + i)
                if col.lower() == 'address':
                    worksheet.column_dimensions[column_letter].width = 25
                else:
                    max_len = 0
                    for val in df[col]:
                        val_str = str(val) if val is not None else ""
                        if len(val_str) > max_len:
                            max_len = len(val_str)
                    header_len = len(str(col))
                    worksheet.column_dimensions[column_letter].width = max(max_len, header_len) + 2
        print(f"--> Success: Saved {len(df)} unique records to {output_path}")
    else:
        if append and os.path.exists(output_path):
            try:
                old_df = pd.read_csv(output_path)
                df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=['name'])
            except: df = new_df
        else:
            df = new_df
        df.to_csv(output_path, index=False)
        print(f"--> Success: Saved {len(df)} unique records to {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str, help="Search query for Google Maps")
    parser.add_argument("-t", "--total", type=int, help="Total number of results to scrape")
    parser.add_argument("-o", "--output", type=str, default="result.csv", help="Output file path")
    parser.add_argument("--append", action="store_true", help="Append results")
    args = parser.parse_args()
    
    search_for = args.search or "turkish stores in toronto Canada"
    total = args.total or 1
    output_path = args.output
    append = args.append
    places = scrape_places(search_for, total)
    save_data(places, output_path, append=append)

if __name__ == "__main__":
    main()