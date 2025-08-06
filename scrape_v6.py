import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FNRIFoodScraper:
    def __init__(self, headless=False, test_mode=True):
        """
        Initialize the FNRI Food Scraper
        
        Args:
            headless (bool): Run browser in headless mode
            test_mode (bool): If True, limit scraping for testing purposes
        """
        self.test_mode = test_mode
        self.basic_data = []
        self.detailed_data = []
        
        # Set up Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def wait_for_page_load(self, timeout=10):
        """Wait for page to fully load"""
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
            time.sleep(2)  # Additional wait for dynamic content
        except TimeoutException:
            logger.warning("Page load timeout - continuing anyway")
    
    def extract_basic_data(self, row):
        """Extract basic food data from table row"""
        try:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) >= 6:
                return {
                    'Food_ID': cols[0].text.strip(),
                    'Food_name_and_Description': cols[1].text.strip(),
                    'Scientific_name': cols[2].text.strip(),
                    'Alternate_Common_names': cols[3].text.strip(),
                    'Edible_portion': cols[4].text.strip(),
                    'Option': cols[5].text.strip()
                }
        except Exception as e:
            logger.error(f"Error extracting basic data: {e}")
        return None
    
    def find_clickable_element(self, row):
        """Find clickable element in row for detailed data"""
        selectors = [
            "a[data-toggle='modal']",
            "button[data-toggle='modal']", 
            ".btn-info",
            ".btn-primary",
            "a[href*='#']",
            "button"
        ]
        
        for selector in selectors:
            try:
                element = row.find_element(By.CSS_SELECTOR, selector)
                return element
            except NoSuchElementException:
                continue
        
        # Try food name link as fallback
        try:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) > 1:
                food_name_links = cols[1].find_elements(By.TAG_NAME, "a")
                if food_name_links:
                    return food_name_links[0]
        except:
            pass
        
        return None
    
    def wait_for_modal(self, modal_id=None, timeout=15):
        """Wait for modal to appear and return modal element"""
        logger.info(f"Waiting for modal (ID: {modal_id})...")
        
        # If we have a specific modal ID, target it directly
        if modal_id:
            try:
                # Wait for the specific modal to be visible
                modal = WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.ID, modal_id))
                )
                logger.info(f"✓ Found specific modal: {modal_id}")
                
                # Additional wait for modal content to fully load
                time.sleep(1)
                
                # Verify modal has content
                modal_body = modal.find_element(By.CSS_SELECTOR, ".modal-body, .modal-content")
                if modal_body and modal_body.text.strip():
                    logger.info(f"✓ Modal {modal_id} has content")
                    return modal
                else:
                    logger.warning(f"Modal {modal_id} found but empty")
                    
            except TimeoutException:
                logger.warning(f"Specific modal {modal_id} not found, trying general detection")
            except Exception as e:
                logger.warning(f"Error finding specific modal {modal_id}: {e}")
        
        # Fallback to general modal detection
        modal_selectors = [
            ".modal.show",
            ".modal.in", 
            ".modal[style*='display: block']",
            ".modal.fade.show",
            ".modal-dialog",
            "[role='dialog'][style*='display: block']"
        ]
        
        for selector in modal_selectors:
            try:
                modals = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for modal in modals:
                    if modal.is_displayed():
                        # Check if modal has actual content
                        try:
                            modal_body = modal.find_element(By.CSS_SELECTOR, ".modal-body, .modal-content")
                            if modal_body and modal_body.text.strip():
                                logger.info(f"✓ Found general modal with selector: {selector}")
                                return modal
                        except:
                            continue
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        logger.warning("No modal found with any selector")
        return None
    
    def extract_tab_data(self, tab_name, modal_id=None):
        """Extract nutritional data from a specific tab"""
        extracted_data = {}
        
        try:
            logger.info(f"Extracting data from {tab_name} tab...")
            
            # Find and click tab with improved targeting
            tab_selectors = []
            
            if modal_id:
                # Specific modal targeting
                tab_selectors.extend([
                    f"#{modal_id} a[href*='{tab_name.lower()}'], #{modal_id} a:contains('{tab_name}')",
                    f"#{modal_id} .nav-tabs a:contains('{tab_name}')",
                    f"#{modal_id} .nav-link:contains('{tab_name}')"
                ])
            
            # General selectors for visible modals
            tab_selectors.extend([
                f".modal.show a:contains('{tab_name}'), .modal[style*='display: block'] a:contains('{tab_name}')",
                f".modal-dialog a:contains('{tab_name}')"
            ])
            
            # Use XPath for more reliable text matching
            xpath_selectors = [
                f"//div[contains(@class, 'modal') and (contains(@class, 'show') or contains(@style, 'display: block'))]//a[contains(text(), '{tab_name}')]",
                f"//div[@id='{modal_id}']//a[contains(text(), '{tab_name}')]" if modal_id else None
            ]
            
            tab_button = None
            
            # Try XPath selectors first (more reliable for text matching)
            for xpath in xpath_selectors:
                if xpath is None:
                    continue
                try:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            tab_button = element
                            logger.info(f"Found tab with XPath: {xpath}")
                            break
                    if tab_button:
                        break
                except Exception as e:
                    logger.debug(f"XPath {xpath} failed: {e}")
                    continue
            
            if not tab_button:
                logger.warning(f"Tab '{tab_name}' not found - skipping")
                return extracted_data
            
            # Click tab with retry logic
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Scroll to tab and ensure it's visible
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", tab_button)
                    time.sleep(0.3)
                    
                    # Wait for element to be clickable
                    WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(tab_button))
                    
                    # Try JavaScript click first
                    self.driver.execute_script("arguments[0].click();", tab_button)
                    
                    # Wait for tab content to load
                    time.sleep(1)
                    
                    # Verify tab is active
                    if 'active' in tab_button.get_attribute('class'):
                        logger.info(f"✓ {tab_name} tab activated")
                        break
                    elif attempt < max_attempts - 1:
                        logger.warning(f"Tab click attempt {attempt + 1} failed, retrying...")
                        time.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Tab click attempt {attempt + 1} failed: {e}")
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
                    else:
                        logger.error(f"Failed to click {tab_name} tab after {max_attempts} attempts")
                        return extracted_data
            
            # Extract nutrient data with improved targeting
            nutrient_items = []
            
            # Target active tab content specifically
            content_selectors = []
            if modal_id:
                content_selectors.extend([
                    f"#{modal_id} .tab-pane.active .list-group-item",
                    f"#{modal_id} .tab-content .active .list-group-item"
                ])
            
            content_selectors.extend([
                ".modal.show .tab-pane.active .list-group-item",
                ".modal[style*='display: block'] .tab-pane.active .list-group-item",
                ".modal-dialog .tab-pane.active .list-group-item"
            ])
            
            for selector in content_selectors:
                try:
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if items and len(items) <= 50:  # Reasonable number check
                        nutrient_items = items
                        logger.info(f"Found {len(items)} nutrient items with: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Content selector failed: {selector} - {e}")
                    continue
            
            if not nutrient_items:
                logger.warning(f"No nutrient items found for {tab_name}")
                return extracted_data
            
            # Process nutrient data - preserve original structure
            processed_count = 0
            for i, item in enumerate(nutrient_items):
                if processed_count >= 30:  # Increased limit to capture all nutrients
                    break
                    
                try:
                    item_text = item.text.strip()
                    if not item_text:
                        continue
                    
                    # Try div structure first
                    divs = item.find_elements(By.TAG_NAME, "div")
                    
                    nutrient_name = None
                    nutrient_value = None
                    
                    if len(divs) >= 2:
                        nutrient_name = divs[0].text.strip()
                        nutrient_value = divs[1].text.strip()
                    elif ":" in item_text:
                        # Fallback to colon-separated format
                        parts = item_text.split(":", 1)
                        nutrient_name = parts[0].strip()
                        nutrient_value = parts[1].strip()
                    
                    if not nutrient_name or not nutrient_value:
                        continue
                    
                    # Only skip obviously non-food items (be very conservative)
                    skip_patterns = [
                        "amount per 100", "proximates", "other carbohydrate", 
                        "minerals", "vitamins", "lipids"
                    ]
                    
                    if any(pattern in nutrient_name.lower() for pattern in skip_patterns):
                        continue
                    
                    # Accept all nutrient data - don't filter by value format
                    # This preserves entries like "Water (g)", "Energy, calculated (kcal)", etc.
                    
                    # Create column name with minimal cleaning - preserve original structure
                    # Only replace spaces with underscores and remove problematic characters for CSV
                    clean_name = (nutrient_name
                                .replace(" ", "_")
                                .replace(",", "")
                                .replace("(", "").replace(")", "")
                                .replace(":", "")
                                .replace(".", "")
                                .replace("'", "")
                                .replace('"', ''))
                    
                    column_name = f"{tab_name.replace(' ', '_')}_{clean_name}"
                    extracted_data[column_name] = nutrient_value
                    processed_count += 1
                    
                    logger.debug(f"✓ {nutrient_name}: {nutrient_value}")
                
                except Exception as e:
                    logger.debug(f"Error processing nutrient item {i}: {e}")
                    continue
            
            logger.info(f"✓ Extracted {len(extracted_data)} nutrients from {tab_name}")
            
        except Exception as e:
            logger.error(f"Error processing tab {tab_name}: {e}")
        
        return extracted_data
    
    def close_modal(self):
        """Close modal dialog with improved reliability"""
        logger.debug("Closing modal...")
        
        try:
            # Force close with JavaScript (most reliable)
            self.driver.execute_script("""
                // Remove all modal backdrops
                var backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(function(backdrop) {
                    backdrop.remove();
                });
                
                // Hide and remove all modals
                var modals = document.querySelectorAll('.modal');
                modals.forEach(function(modal) {
                    modal.style.display = 'none';
                    modal.classList.remove('show', 'in', 'fade');
                    modal.setAttribute('aria-hidden', 'true');
                });
                
                // Reset body styles
                document.body.classList.remove('modal-open');
                document.body.style.paddingRight = '';
                document.body.style.overflow = '';
                document.body.style.position = '';
            """)
            
            time.sleep(0.5)
            logger.debug("✓ Modal closed")
            return True
            
        except Exception as e:
            logger.debug(f"Modal close failed: {e}")
            return False
    
    def process_row(self, row, row_index):
        """Process a single table row with improved error handling"""
        # Extract basic data
        basic_record = self.extract_basic_data(row)
        if not basic_record:
            return False
        
        self.basic_data.append(basic_record)
        
        food_name = basic_record['Food_name_and_Description'][:50]
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing row {row_index + 1}: {food_name}")
        logger.info(f"{'='*60}")
        
        # Ensure clean state
        self.close_modal()
        time.sleep(1)
        
        # Find and click element for detailed data
        clickable = self.find_clickable_element(row)
        if not clickable:
            logger.warning(f"No clickable element found for row {row_index + 1}")
            return True
        
        try:
            # Get target modal ID
            modal_id = clickable.get_attribute('data-target')
            if modal_id and modal_id.startswith('#'):
                modal_id = modal_id[1:]
            
            logger.info(f"Target modal ID: {modal_id}")
            
            # Scroll and click
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", clickable)
            time.sleep(0.5)
            
            # Wait for clickability and click
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(clickable))
            
            # Use JavaScript click
            self.driver.execute_script("arguments[0].click();", clickable)
            
            # Wait for modal with the specific ID
            modal = self.wait_for_modal(modal_id, timeout=20)
            
            if modal:
                logger.info(f"✓ Modal opened successfully")
                
                detailed_record = basic_record.copy()
                
                # Extract data from all tabs
                tabs = ["Proximates", "Other Carbohydrate", "Minerals", "Vitamins", "Lipids"]
                total_extracted = 0
                
                for tab_name in tabs:
                    logger.info(f"\nProcessing {tab_name} tab...")
                    tab_data = self.extract_tab_data(tab_name, modal_id)
                    detailed_record.update(tab_data)
                    total_extracted += len(tab_data)
                    logger.info(f"  → Extracted {len(tab_data)} nutrients from {tab_name}")
                
                logger.info(f"\n✓ Total nutrients extracted: {total_extracted}")
                
                if total_extracted > 0:
                    self.detailed_data.append(detailed_record)
                    logger.info(f"✓ Successfully processed {food_name}")
                    
                    # Show sample data
                    sample_keys = [k for k in detailed_record.keys() if 'Proximates_' in k][:3]
                    for key in sample_keys:
                        logger.info(f"  Sample: {key} = {detailed_record[key]}")
                else:
                    logger.warning(f"No nutritional data extracted for {food_name}")
            else:
                logger.error(f"Could not open modal for {food_name}")
            
        except Exception as e:
            logger.error(f"Error processing row {row_index + 1}: {e}")
        finally:
            # Always close modal
            self.close_modal()
            time.sleep(1)
        
        return True
    
    def navigate_to_next_page(self):
        """Navigate to next page if available"""
        try:
            pagination = self.driver.find_element(By.CSS_SELECTOR, ".pagination")
            next_candidates = pagination.find_elements(By.TAG_NAME, "a")
            
            for candidate in next_candidates:
                if candidate.text.strip() == ">":
                    parent_li = candidate.find_element(By.XPATH, "./..")
                    li_class = parent_li.get_attribute("class") or ""
                    
                    if "disabled" not in li_class.lower():
                        self.driver.execute_script("arguments[0].scrollIntoView();", candidate)
                        time.sleep(1)
                        candidate.click()
                        self.wait_for_page_load()
                        return True
            
            logger.info("Reached last page")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False
    
    def scrape_data(self):
        """Main scraping method"""
        try:
            logger.info("Navigating to FNRI food content list...")
            self.driver.get("https://i.fnri.dost.gov.ph/fct/library/food_content/")
            self.wait_for_page_load()
            
            page_num = 1
            
            while True:
                logger.info(f"\n{'='*80}")
                logger.info(f"SCRAPING PAGE {page_num}")
                logger.info(f"{'='*80}")
                
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                rows_to_process = rows[:3] if self.test_mode else rows
                
                for row_index, row in enumerate(rows_to_process):
                    if not self.process_row(row, row_index):
                        continue
                
                logger.info(f"\nPage {page_num} Summary:")
                logger.info(f"  Basic records: {len(self.basic_data)}")
                logger.info(f"  Detailed records: {len(self.detailed_data)}")
                
                # Test mode or pagination check
                if self.test_mode and page_num >= 1:
                    logger.info("Test mode - stopping after one page")
                    break
                
                if not self.navigate_to_next_page():
                    break
                
                page_num += 1
                
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            self.driver.quit()
    
    def save_data(self):
        """Save scraped data to CSV files"""
        if self.basic_data:
            df_basic = pd.DataFrame(self.basic_data)
            df_basic.to_csv("fnri_basic_food_data.csv", index=False)
            logger.info(f"Basic data saved! {len(self.basic_data)} records in fnri_basic_food_data.csv")
        
        if self.detailed_data:
            df_detailed = pd.DataFrame(self.detailed_data)
            df_detailed.to_csv("fnri_detailed_nutritional_data.csv", index=False)
            logger.info(f"Detailed data saved! {len(self.detailed_data)} records in fnri_detailed_nutritional_data.csv")
            
            logger.info(f"\nFinal Summary:")
            logger.info(f"  Basic records: {len(self.basic_data)}")
            logger.info(f"  Detailed records: {len(self.detailed_data)}")
            logger.info(f"  Success rate: {len(self.detailed_data)/len(self.basic_data)*100:.1f}%")
            
            if self.detailed_data:
                total_columns = len(self.detailed_data[0].keys())
                nutrient_columns = total_columns - 6  # Subtract basic fields
                logger.info(f"  Total columns: {total_columns}")
                logger.info(f"  Nutrient columns: {nutrient_columns}")
        else:
            logger.warning("No detailed nutritional data was scraped.")

def main():
    """Main function to run the scraper"""
    scraper = FNRIFoodScraper(headless=False, test_mode=True)
    
    try:
        scraper.scrape_data()
        scraper.save_data()
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    main()