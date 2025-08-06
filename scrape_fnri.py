from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time

# Launch Chrome browser
driver = webdriver.Chrome()

try:
    # Go to FNRI food content list
    driver.get("https://i.fnri.dost.gov.ph/fct/library/food_content/")
    
    # Wait for table to load
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    
    data = []
    page_num = 1
    
    while True:
        print(f"📄 Scraping page {page_num}...")
        
        # Wait a bit for page to fully load
        time.sleep(2)
        
        # Get current page rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        
        # Extract data from current page
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) >= 6:  # Ensure we have enough columns
                record = {
                    'Food_ID': cols[0].text.strip(),
                    'Food name and Description': cols[1].text.strip(),
                    'Scientific name': cols[2].text.strip(),
                    'Alternate/Common name(s)': cols[3].text.strip(),
                    'Edible portion': cols[4].text.strip(),
                    'Option': cols[5].text.strip()
                }
                data.append(record)
        
        print(f"   Extracted {len(rows)} rows from page {page_num} (Total so far: {len(data)})")
        
        # Try to find and click the "Next" button (>)
        try:
            # Look for the Bootstrap pagination structure
            # The ">" (next) button should be in the pagination
            next_btn = None
            
            # First, try to find the pagination container
            pagination = driver.find_element(By.CSS_SELECTOR, ".pagination")
            
            # Look for the ">" symbol or "Next" text in pagination links
            next_candidates = pagination.find_elements(By.TAG_NAME, "a")
            
            for candidate in next_candidates:
                text = candidate.text.strip()
                # Look for ">" symbol or check if it's the next button
                if text == ">" or "next" in text.lower():
                    # Check if the parent li is not disabled
                    parent_li = candidate.find_element(By.XPATH, "./..")
                    li_class = parent_li.get_attribute("class") or ""
                    
                    if "disabled" not in li_class.lower():
                        next_btn = candidate
                        break
            
            # Alternative: try to find the next page number
            if not next_btn:
                # Get current active page number
                try:
                    active_page = pagination.find_element(By.CSS_SELECTOR, ".active a")
                    current_page_num = int(active_page.text.strip())
                    next_page_num = current_page_num + 1
                    
                    # Look for the next page number
                    for candidate in next_candidates:
                        if candidate.text.strip() == str(next_page_num):
                            next_btn = candidate
                            break
                except:
                    pass
            
            if not next_btn:
                print("✅ No next button found - reached last page.")
                break
            
            # Check if we can click the next button
            parent_li = next_btn.find_element(By.XPATH, "./..")
            li_class = parent_li.get_attribute("class") or ""
            
            if "disabled" in li_class.lower():
                print("✅ Next button is disabled - reached last page.")
                break
            
            # Store reference to current first row for staleness check
            first_row = rows[0] if rows else None
            
            # Scroll to the next button and click it
            driver.execute_script("arguments[0].scrollIntoView();", next_btn)
            time.sleep(1)
            
            print(f"   Clicking next button: '{next_btn.text.strip()}'")
            
            # Click the next button
            try:
                next_btn.click()
            except Exception as e:
                print(f"   Regular click failed, trying JavaScript click: {e}")
                driver.execute_script("arguments[0].click();", next_btn)
            
            # Wait for page to change
            if first_row:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.staleness_of(first_row)
                    )
                except TimeoutException:
                    print("   Staleness check timed out, waiting with sleep...")
                    time.sleep(3)
            else:
                time.sleep(3)
            
            # Wait for new content to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
                )
            except TimeoutException:
                print("   Timeout waiting for new content, continuing...")
                time.sleep(2)
            
            page_num += 1
            
            # Safety check - don't run indefinitely
            if page_num > 200:  # Adjust this limit as needed
                print("⚠️  Reached page limit (200), stopping to prevent infinite loop.")
                break
                
        except Exception as e:
            print(f"❌ Error while paginating: {e}")
            
            # Try to get pagination info for debugging
            try:
                # Look for "Showing X to Y of Z records" text
                info_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Showing')]")
                for elem in info_elements:
                    if "records" in elem.text.lower():
                        print(f"   Pagination info: {elem.text}")
                        break
            except:
                pass
            
            break

finally:
    driver.quit()

# Save all rows to CSV
if data:
    df = pd.DataFrame(data)
    df.to_csv("fnri_all_food_data.csv", index=False)
    print(f"✅ Scraping finished! {len(data)} records saved to fnri_all_food_data.csv")
    
    # Print summary
    print(f"📊 Summary:")
    print(f"   Total records: {len(data)}")
    print(f"   Pages scraped: {page_num - 1}")
    if data:
        print(f"   Sample record: {data[0]}")
else:
    print("❌ No data was scraped.")