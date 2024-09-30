import firebase_admin
from firebase_admin import credentials, db
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

# Initialize Firebase Admin SDK
cred = credentials.Certificate("\\")
firebase_admin.initialize_app(cred, {
    'databaseURL': '\\'  # Correct URL
})

def close_popup(driver):
    try:
        popup = driver.find_element(By.CLASS_NAME, 'popup-onload')
        close_button = popup.find_element(By.CLASS_NAME, 'close')
        close_button.click()
        print("Popup closed")
    except NoSuchElementException:
        print("Popup not found, skipping...")

def sanitize_data(data):
    """
    Sanitize data to ensure keys and values are Firebase-compatible.
    Removes or replaces invalid characters in keys or values.
    """
    sanitized_data = {}
    for key, value in data.items():
        # Replace invalid characters with underscores in keys
        sanitized_key = re.sub(r'[.$\[\]/]', '_', key)
        if isinstance(value, str):
            # Optionally, sanitize values if needed (e.g., remove invalid characters)
            sanitized_value = re.sub(r'[.$\[\]/]', '_', value)
        else:
            sanitized_value = value
        sanitized_data[sanitized_key] = sanitized_value
    return sanitized_data

def scrape_data(state, commodity, market):
    initial_url = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
    driver = webdriver.Chrome()
    driver.get(initial_url)
    close_popup(driver)

    print("Selecting commodity...")
    commodity_dropdown = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'ddlCommodity')))
    Select(commodity_dropdown).select_by_visible_text(commodity)

    print("Selecting state...")
    state_dropdown = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'ddlState')))
    Select(state_dropdown).select_by_visible_text(state)

    print("Setting date...")
    desired_date = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
    date_input = driver.find_element(By.ID, "txtDate")
    driver.execute_script("arguments[0].value = arguments[1];", date_input, desired_date)

    print("Submitting form...")
    driver.find_element(By.ID, 'btnGo').click()

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'ddlMarket')))
    print("Selecting market...")
    market_dropdown = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'ddlMarket')))
    Select(market_dropdown).select_by_visible_text(market)

    driver.find_element(By.ID, 'btnGo').click()

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'cphBody_GridPriceData')))
    print("Data table loaded, scraping data...")

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    data_list = []
    for row in soup.find_all("tr"):
        data_list.append(row.text.replace("\n", "_").replace("  ", "").split("__"))

    json_list = []
    for row_data in data_list[4:len(data_list) - 1]:
        data_dict = {
            "S.No": row_data[1],
            "City": row_data[2],
            "Commodity": row_data[4],
            "Min Price": row_data[7],
            "Max Price": row_data[8],
            "Model Price": row_data[9],
            "Date": row_data[10]
        }
        json_list.append(data_dict)

    return json_list

def upload_to_firebase(data):
    ref = db.reference('market_prices')  # Firebase DB reference
    
    for entry in data:
        try:
            if isinstance(entry, dict):
                sanitized_entry = sanitize_data(entry)  # Sanitize the entry before upload
                ref.push(sanitized_entry)  # Push the sanitized entry to Firebase
                print(f"Uploaded entry: {sanitized_entry}")
            else:
                print(f"Skipping invalid data: {entry}")
        except Exception as e:
            print(f"Failed to upload data: {entry}, error: {str(e)}")

if __name__ == '__main__':
    state = "Karnataka"
    commodity = "Wheat"
    market = "Bangalore"

    # Scrape data
    scraped_data = scrape_data(state, commodity, market)

    # Upload to Firebase
    upload_to_firebase(scraped_data)
    print("Data uploaded to Firebase")
