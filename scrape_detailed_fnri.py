import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FNRIFoodScraper:
    def __init__(self, headless=True, test_mode=True): # Changed headless to True by default
        """
        Initialize the FNRI Food Scraper
        
        Args:
            headless (bool): Run browser in headless mode
            test_mode (bool): If True, limit scraping for testing purposes
        """
        self.test_mode = test_mode
        self.basic_data = []
        self.detailed_data = []
        self.base_url = "https://i.fnri.dost.gov.ph/fct/library/food_content/"
        
        # Set up Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--dns-prefetch-disable")
        chrome_options.add_argument("--disable-browser-side-navigation")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20) # Increased timeout for robustness
    
    def wait_for_page_load(self, timeout=20): # Increased timeout
        """Wait for page to fully load"""
        try:
            # Wait for the main content table to be present
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
            logger.info("Main table loaded.")
            # time.sleep(1) # Removed, relying on explicit waits more
        except TimeoutException:
            logger.warning("Page load timeout - continuing anyway (main table not found immediately).")
    
    def debug_modal_structure(self):
        """Debug modal structure to understand the HTML layout"""
        try:
            logger.info("=== DEBUGGING MODAL STRUCTURE ===")
            
            # Wait a bit longer for modal to fully load
            time.sleep(3) # Keep this short sleep for initial modal rendering
            
            # Try different modal selectors
            modal_selectors = [
                ".modal.show", ".modal.fade.show", "[role='dialog']",
                ".modal-dialog", ".modal-content", ".modal[style*='display: block']"
            ]
            
            modal_found = False
            for selector in modal_selectors:
                try:
                    modals = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if modals:
                        modal_found = True
                        logger.info(f"Found {len(modals)} modal(s) with selector: {selector}")
                        
                        for i, modal in enumerate(modals):
                            if modal.is_displayed():
                                logger.info(f"Modal {i+1} HTML structure (first 1000 chars):")
                                modal_html = modal.get_attribute('outerHTML')[:1000] # Use outerHTML for full element
                                logger.info(modal_html)
                                
                                # Look for tab structure
                                tabs = modal.find_elements(By.CSS_SELECTOR, "a[data-toggle='tab'], .nav-link, .tab-link")
                                if tabs:
                                    logger.info(f"Found {len(tabs)} tabs:")
                                    for tab in tabs:
                                        logger.info(f"  Tab: {tab.text.strip()} (data-target: {tab.get_attribute('data-target')}, href: {tab.get_attribute('href')})")
                                
                                # Look for content structure
                                content_areas = modal.find_elements(By.CSS_SELECTOR, ".tab-pane, .tab-content > div, .modal-body")
                                logger.info(f"Found {len(content_areas)} content areas")
                                
                                # Look for data elements
                                data_elements = modal.find_elements(By.CSS_SELECTOR, ".list-group-item, tr, .data-row, dt, dd")
                                logger.info(f"Found {len(data_elements)} potential data elements")
                                
                                if data_elements:
                                    logger.info("Sample data elements (first 5):")
                                    for j, elem in enumerate(data_elements[:5]):
                                        logger.info(f"  Element {j+1}: {elem.text.strip()[:100]}")
                                
                                break # Found a displayed modal, no need to check other selectors
                        if modal_found:
                            break
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
            
            if not modal_found:
                logger.error("NO MODAL FOUND! Checking page source...")
                page_source = self.driver.page_source
                if 'modal' in page_source.lower():
                    logger.info("Modal HTML exists in page source")
                    # Extract modal section
                    modal_start = page_source.lower().find('<div class="modal')
                    if modal_start > -1:
                        modal_section = page_source[modal_start:modal_start+2000]
                        logger.info(f"Modal HTML: {modal_section}")
                else:
                    logger.error("No modal HTML found in page source")
            
            logger.info("=== END MODAL DEBUG ===")
            
        except Exception as e:
            logger.error(f"Error in debug_modal_structure: {e}")
    
    def extract_basic_data(self, row):
        """Extract basic food data from table row"""
        try:
            cols = self.wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, 'td')), row)
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
        # More comprehensive selectors based on common patterns
        selectors = [
            "a[data-toggle='modal']", "button[data-toggle='modal']",
            "a[href*='#modal']", "a[href*='detail']",
            ".btn-info", ".btn-primary", ".btn-sm",
            "a[onclick*='modal']", "button[onclick*='modal']"
        ]
        
        for selector in selectors:
            try:
                elements = row.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        logger.info(f"Found clickable element with selector: {selector}")
                        return element
            except NoSuchElementException:
                continue
        
        # Try food name link as fallback
        try:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) > 1:
                links = cols[1].find_elements(By.TAG_NAME, "a")
                for link in links:
                    if link.is_displayed():
                        logger.info("Using food name link as clickable element")
                        return link
        except:
            pass
        
        logger.warning("No clickable element found")
        return None
    
    def wait_for_modal(self):
        """Wait for modal to appear and return modal element"""
        logger.info("Waiting for modal to appear...")
        
        # Multiple strategies to wait for modal
        modal_selectors = [
            ".modal.show", ".modal.fade.show", 
            ".modal[style*='display: block']", ".modal-content",
            "[role='dialog']", ".modal.in"
        ]
        
        for i, selector in enumerate(modal_selectors):
            try:
                logger.debug(f"Trying modal selector {i+1}: {selector}")
                modal = self.wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                logger.info(f"Modal found with selector: {selector}")
                
                # Additional wait for content to load, though explicit waits are preferred for specific elements
                time.sleep(1) 
                return modal
            except TimeoutException:
                logger.debug(f"Modal selector {selector} timed out")
                continue
        
        # If no modal found with standard selectors, try generic modal detection
        try:
            logger.info("Trying generic modal detection...")
            modals = self.driver.find_elements(By.CSS_SELECTOR, ".modal")
            for modal in modals:
                if modal.is_displayed():
                    logger.info("Found displayed modal with generic selector")
                    time.sleep(1) # Small pause
                    return modal
        except Exception as e:
            logger.debug(f"Generic modal detection failed: {e}")
        
        logger.error("No modal found with any selector")
        return None
    
    def extract_tab_data(self, tab_name):
        """Extract nutritional data from a specific tab"""
        extracted_data = {}
        logger.info(f"Attempting to extract data from '{tab_name}' tab...")
        
        try:
            # More comprehensive tab selectors
            tab_selectors = [
                f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{tab_name.lower()}') and @data-toggle='tab']",
                f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{tab_name.lower()}') and @data-toggle='tab']",
                f"//li/a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{tab_name.lower()}')]",
                f"//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{tab_name.lower()}')]/ancestor::a",
                f"//*[@data-target='#{tab_name.lower().replace(' ', '')}' or @href='#{tab_name.lower().replace(' ', '')}']"
            ]
            
            tab_button = None
            for i, selector in enumerate(tab_selectors):
                try:
                    logger.debug(f"Trying tab selector {i+1}: {selector}")
                    # Use WebDriverWait to ensure the tab button is present and clickable
                    tab_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    logger.info(f"Found tab button: {tab_button.text.strip()}")
                    break
                except (TimeoutException, NoSuchElementException):
                    logger.debug(f"Tab selector {i+1} failed or element not clickable.")
                    continue
            
            if not tab_button:
                logger.warning(f"Tab '{tab_name}' not found or not clickable. Listing available tabs...")
                try:
                    all_tabs = self.driver.find_elements(By.CSS_SELECTOR, ".nav-link, .tab-link, a[data-toggle='tab'], button[data-toggle='tab']")
                    logger.info(f"Available tabs: {[tab.text.strip() for tab in all_tabs if tab.text.strip()]}")
                except:
                    pass
                return extracted_data
            
            # Scroll tab into view and click
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab_button)
            time.sleep(0.2) # Small pause after scroll
            
            try:
                tab_button.click()
                logger.info(f"Clicked {tab_name} tab.")
            except ElementClickInterceptedException:
                logger.warning(f"Click intercepted for {tab_name} tab. Trying JavaScript click.")
                self.driver.execute_script("arguments[0].click();", tab_button)
                logger.info(f"Clicked {tab_name} tab with JavaScript.")
            
            # Wait for tab content to load and become visible
            # We need to target the content div that becomes active.
            # This is often linked to the data-target or href of the tab button.
            tab_id = tab_button.get_attribute("href")
            if tab_id and "#" in tab_id:
                tab_id = tab_id.split("#")[-1]
            elif tab_button.get_attribute("data-target"):
                tab_id = tab_button.get_attribute("data-target").replace("#", "")
            else:
                # Fallback to a generic active tab pane selector
                tab_id = None

            if tab_id:
                try:
                    self.wait.until(EC.visibility_of_element_located((By.ID, tab_id)))
                    logger.info(f"Tab content for '{tab_name}' (ID: {tab_id}) is visible.")
                except TimeoutException:
                    logger.warning(f"Tab content for '{tab_name}' (ID: {tab_id}) did not become visible within timeout.")
            else:
                # Fallback if no explicit tab_id, wait for a generic active tab pane
                self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".tab-pane.active, .tab-content > .active")))
                logger.info(f"Generic active tab content is visible for '{tab_name}'.")

            time.sleep(1) # Small delay for rendering dynamic content within the tab

            # Try multiple strategies to find nutrient data
            strategies = [
                self._extract_from_list_groups,
                self._extract_from_table,
                self._extract_from_divs,
                self._extract_generic_data
            ]
            
            for strategy in strategies:
                try:
                    data = strategy(tab_name)
                    if data:
                        extracted_data.update(data)
                        logger.info(f"Successfully extracted {len(data)} items from '{tab_name}' using {strategy.__name__}.")
                        break
                except Exception as e:
                    logger.debug(f"Strategy {strategy.__name__} failed for '{tab_name}': {e}")
                    continue
            
            if not extracted_data:
                logger.warning(f"No data extracted from '{tab_name}' tab.")
            
        except Exception as e:
            logger.error(f"Error processing tab '{tab_name}': {e}")
            
        return extracted_data
    
    def _extract_from_list_groups(self, tab_name):
        """Extract data from list-group-item elements"""
        data = {}
        
        # Try to find active tab content first
        content_selectors = [
            f"#{tab_name.lower().replace(' ', '').replace('carbohydrate', 'carb')} .list-group-item",
            ".modal .tab-pane.active .list-group-item",
            ".modal .tab-content .active .list-group-item",
            ".modal .show.active .list-group-item",
            ".list-group-item" # Broader search within the modal if specific active tab isn't found
        ]
        
        items = []
        for selector in content_selectors:
            try:
                items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if items:
                    logger.info(f"Found {len(items)} list items with selector: {selector} for {tab_name}.")
                    break
            except:
                continue
        
        for item in items:
            try:
                text = item.text.strip()
                if not text or len(text) < 3:
                    continue
                
                # Try different structures
                divs = item.find_elements(By.TAG_NAME, "div")
                if len(divs) >= 2:
                    name = divs[0].text.strip()
                    value = divs[1].text.strip()
                elif ":" in text:
                    parts = text.split(":", 1)
                    name = parts[0].strip()
                    value = parts[1].strip()
                elif "\n" in text:
                    lines = text.split("\n")
                    if len(lines) >= 2:
                        name = lines[0].strip()
                        value = lines[1].strip()
                    else:
                        continue
                else:
                    continue
                
                if name and value and any(char.isdigit() for char in value):
                    clean_name = self._clean_column_name(name)
                    column_name = f"{tab_name.replace(' ', '_')}_{clean_name}"
                    data[column_name] = value
                    logger.debug(f"Extracted: {name} = {value}")
            
            except StaleElementReferenceException:
                logger.warning("Stale element reference encountered, re-finding elements if needed (not implemented for individual items). Skipping item.")
                continue # Skip this item, will be re-evaluated on next iteration if list is re-fetched
            except Exception as e:
                logger.debug(f"Error processing list item: {e}")
                continue
        
        return data
    
    def _extract_from_table(self, tab_name):
        """Extract data from table rows"""
        data = {}
        
        try:
            # Look for tables in active content
            tables = self.driver.find_elements(By.CSS_SELECTOR, ".modal .tab-pane.active table, .modal table")
            
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        name = cells[0].text.strip()
                        value = cells[1].text.strip()
                        
                        if name and value and any(char.isdigit() for char in value):
                            clean_name = self._clean_column_name(name)
                            column_name = f"{tab_name.replace(' ', '_')}_{clean_name}"
                            data[column_name] = value
                            logger.debug(f"Table extracted: {name} = {value}")
        
        except Exception as e:
            logger.debug(f"Table extraction failed: {e}")
        
        return data
    
    def _extract_from_divs(self, tab_name):
        """Extract data from div structures"""
        data = {}
        
        try:
            # Look for div pairs in active content
            content_divs = self.driver.find_elements(By.CSS_SELECTOR, ".modal .tab-pane.active div, .modal .active div")
            
            for div in content_divs:
                text = div.text.strip()
                if not text or len(text) > 100: # Skip long texts or empty
                    continue
                
                # Look for patterns like "Nutrient Name: Value"
                if ":" in text and any(char.isdigit() for char in text):
                    parts = text.split(":", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        value = parts[1].strip()
                        
                        clean_name = self._clean_column_name(name)
                        column_name = f"{tab_name.replace(' ', '_')}_{clean_name}"
                        data[column_name] = value
                        logger.debug(f"Div extracted: {name} = {value}")
        
        except Exception as e:
            logger.debug(f"Div extraction failed: {e}")
        
        return data
    
    def _extract_generic_data(self, tab_name):
        """Generic data extraction as fallback"""
        data = {}
        
        try:
            # Get all text content from active area and try to parse
            active_elements = self.driver.find_elements(By.CSS_SELECTOR, ".modal .tab-pane.active *, .modal .active *")
            
            for element in active_elements:
                text = element.text.strip()
                if not text or len(text) > 200:
                    continue
                
                # Look for nutrient-like patterns
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Pattern: "Name Value" or "Name: Value"
                    for separator in [':', '\t', '  ']: # Double space for some patterns
                        if separator in line:
                            parts = line.split(separator, 1)
                            if len(parts) == 2:
                                name = parts[0].strip()
                                value = parts[1].strip()
                                
                                # Validate it looks like nutrient data (heuristic)
                                if (len(name) > 2 and len(name) < 50 and 
                                    any(char.isdigit() for char in value) and
                                    any(unit in value.lower() for unit in ['g', 'mg', 'kcal', '%', 'μg', 'ug', 'tr', 'iu'])):
                                    
                                    clean_name = self._clean_column_name(name)
                                    column_name = f"{tab_name.replace(' ', '_')}_{clean_name}"
                                    data[column_name] = value
                                    logger.debug(f"Generic extracted: {name} = {value}")
                                    break # Stop after finding a match in this line
        
        except Exception as e:
            logger.debug(f"Generic extraction failed: {e}")
        
        return data
    
    def _clean_column_name(self, name):
        """Clean nutrient name for use as column name"""
        return (name.replace(" ", "_")
                .replace(",", "")
                .replace("(", "").replace(")", "")
                .replace("-", "_").replace("/", "_")
                .replace(":", "").replace(".", "")
                .replace("[", "").replace("]", "")
                .replace("&", "and")
                .strip("_")) # Remove leading/trailing underscores
    
    def close_modal(self):
        """Close modal dialog aggressively"""
        logger.info("Closing modal...")
        
        # Check if modal is currently open by looking for its presence and display style
        modal_open = self.driver.execute_script("""
            var modal = document.querySelector('.modal.show, .modal.in, .modal[style*="display: block"]');
            return modal !== null;
        """)
        if not modal_open:
            logger.info("No active modal detected, skipping close.")
            return True

        # JavaScript force close (most reliable)
        try:
            self.driver.execute_script("""
                var backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(function(backdrop) {
                    backdrop.remove();
                });
                
                var modals = document.querySelectorAll('.modal');
                modals.forEach(function(modal) {
                    modal.style.display = 'none';
                    modal.classList.remove('show', 'in');
                    modal.setAttribute('aria-hidden', 'true');
                });
                
                document.body.classList.remove('modal-open');
                document.body.style.paddingRight = '';
                document.body.style.overflow = '';
            """)
            self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".modal.show, .modal.in")))
            logger.info("Modal closed with JavaScript and verified invisible.")
            return True
        except TimeoutException:
            logger.warning("Modal did not become invisible after JS close.")
        except Exception as e:
            logger.debug(f"JavaScript close failed: {e}")
        
        # Try close buttons as fallback
        close_selectors = [
            ".modal .close", ".modal button[data-dismiss='modal']",
            ".modal .btn-close", ".modal button[aria-label='Close']"
        ]
        
        for selector in close_selectors:
            try:
                # Wait for the button to be clickable
                btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".modal.show, .modal.in")))
                    logger.info(f"Modal closed with button: {selector}")
                    return True
            except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                continue
            except Exception as e:
                logger.debug(f"Error clicking close button with selector {selector}: {e}")
        
        # Escape key as a last resort
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".modal.show, .modal.in")))
            logger.info("Modal closed with Escape key.")
            return True
        except TimeoutException:
            logger.warning("Modal did not become invisible after Escape key press.")
        except Exception as e:
            logger.debug(f"Escape key failed: {e}")
        
        logger.error("Failed to close modal after all attempts.")
        return False
    
    def process_row(self, row, row_index):
        """Process a single table row"""
        # Extract basic data
        basic_record = self.extract_basic_data(row)
        if not basic_record:
            logger.warning(f"Could not extract basic data from row {row_index + 1}")
            return False
            
        # Add basic record immediately to ensure it's captured even if detailed fails
        self.basic_data.append(basic_record)
        
        food_name = basic_record['Food_name_and_Description'][:50]
        logger.info(f"Processing row {row_index + 1}: {food_name}...")
        
        # Ensure no existing modals are interfering before clicking
        self.close_modal()
        time.sleep(0.5) # Small pause to allow UI to settle

        # Re-find the row element to avoid StaleElementReferenceException
        # This is crucial if the DOM changes after closing a modal
        try:
            current_row_id = basic_record['Food_ID']
            row = self.wait.until(EC.presence_of_element_located((By.XPATH, f"//td[text()='{current_row_id}']/ancestor::tr")))
            logger.debug(f"Re-found row for Food ID: {current_row_id}")
        except TimeoutException:
            logger.error(f"Could not re-find row for Food ID: {current_row_id}. Skipping detailed scrape for this row.")
            return False
        except Exception as e:
            logger.error(f"Error re-finding row: {e}")
            return False
            
        # Find and click element
        clickable = self.find_clickable_element(row)
        if not clickable:
            logger.warning(f"No clickable element found for row {row_index + 1} ({food_name})")
            return True
            
        try:
            # Scroll and click
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", clickable)
            self.wait.until(EC.element_to_be_clickable(clickable)) # Wait for element to be clickable
            
            # Click with retry
            click_success = False
            for attempt in range(3):
                try:
                    clickable.click()
                    click_success = True
                    logger.info(f"Clicked element for {food_name}")
                    break
                except ElementClickInterceptedException:
                    logger.warning(f"Click intercepted for {food_name}. Attempt {attempt + 1}. Trying JavaScript click.")
                    self.driver.execute_script("arguments[0].click();", clickable)
                    click_success = True
                    break
                except StaleElementReferenceException:
                    logger.warning(f"Stale element for {food_name}. Re-finding clickable element.")
                    # Re-find row and clickable element
                    row = self.wait.until(EC.presence_of_element_located((By.XPATH, f"//td[text()='{current_row_id}']/ancestor::tr")))
                    clickable = self.find_clickable_element(row)
                    if clickable:
                        logger.info(f"Re-found clickable element for {food_name}.")
                        continue # Retry click
                    else:
                        logger.error(f"Could not re-find clickable element for {food_name}. Giving up.")
                        break
                except Exception as e:
                    logger.debug(f"Click attempt {attempt + 1} failed for {food_name}: {e}")
                    time.sleep(0.5) # Small pause before retry
            
            if not click_success:
                logger.error(f"Failed to click element for {food_name} after multiple attempts.")
                return False

            # Wait for modal
            modal = self.wait_for_modal()
            if modal:
                # Debug structure for first row
                if row_index == 0:
                    self.debug_modal_structure()
                
                detailed_record = basic_record.copy()
                
                # Extract data from all tabs
                tabs = ["Proximates", "Other Carbohydrate", "Minerals", "Vitamins", "Lipids"]
                for tab_name in tabs:
                    logger.info(f"Processing {tab_name} tab for {food_name}...")
                    tab_data = self.extract_tab_data(tab_name)
                    detailed_record.update(tab_data)
                    logger.info(f"Extracted {len(tab_data)} items from {tab_name} for {food_name}.")
                
                self.detailed_data.append(detailed_record)
                logger.info(f"Successfully processed {food_name} - Total fields: {len(detailed_record)}")
            else:
                logger.error(f"Could not open modal for {food_name}")
            
            # Close modal
            if not self.close_modal():
                logger.error(f"Failed to close modal for {food_name}. This may affect subsequent scraping.")
            time.sleep(1) # Small pause after closing modal before next row

        except Exception as e:
            logger.error(f"Error processing detailed data for row {row_index + 1} ({food_name}): {e}")
            import traceback
            traceback.print_exc()
            self.close_modal() # Try to close modal even on error
            time.sleep(1)
        
        return True
    
    def navigate_to_next_page(self):
        """Navigate to next page if available"""
        try:
            # Wait for pagination to be present
            pagination = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".pagination")))
            
            # Look for the 'Next' link specifically, or the right-arrow '>'
            next_link_selectors = [
                ".pagination a[rel='next']", # Common for next page link
                ".pagination li.next a",    # Bootstrap 3/4 next button pattern
                ".pagination a[aria-label='Next']",
                ".pagination a[aria-label='»']", # Common for right arrow icon
                ".pagination a[text()='Next']",
                ".pagination a[text()='>']"
            ]
            
            next_button = None
            for selector in next_link_selectors:
                try:
                    # Look for elements that are clickable and not disabled
                    elements = pagination.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        parent_li = element.find_element(By.XPATH, "./..") # Check parent li for disabled class
                        if "disabled" not in (parent_li.get_attribute("class") or "").lower() and element.is_displayed() and element.is_enabled():
                            next_button = element
                            break
                    if next_button:
                        break
                except NoSuchElementException:
                    continue

            if next_button:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.5) # Short pause for scroll
                try:
                    next_button.click()
                except ElementClickInterceptedException:
                    logger.warning("Next page button click intercepted. Trying JavaScript click.")
                    self.driver.execute_script("arguments[0].click();", next_button)
                self.wait_for_page_load() # Wait for the new page to load its content
                logger.info("Navigated to next page.")
                return True
            else:
                logger.info("No next page link found or it's disabled.")
                return False
                
        except TimeoutException:
            logger.warning("Pagination element not found within timeout.")
            return False
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False
    
    def scrape_data(self):
        """Main scraping method"""
        try:
            logger.info("Navigating to FNRI food content list...")
            self.driver.get(self.base_url)
            self.wait_for_page_load()
            
            page_num = 1
            detailed_records_on_page = 0
            
            while True:
                logger.info(f"Scraping page {page_num}...")
                
                # Get current page rows (re-fetch to avoid stale elements after modal interactions)
                rows = self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr")))
                logger.info(f"Found {len(rows)} rows on page {page_num}")
                
                if not rows:
                    logger.warning("No rows found on page. Ending scrape.")
                    break
                    
                # Limit rows for testing
                rows_to_process = rows[:2] if self.test_mode else rows
                logger.info(f"Processing {len(rows_to_process)} rows...")
                
                for row_index, row in enumerate(rows_to_process):
                    # To handle StaleElementReferenceException, re-fetch the row if necessary.
                    # This is implicitly handled if process_row re-finds the row by ID.
                    success = self.process_row(row, row_index)
                    if success:
                        detailed_records_on_page += 1
                        # Save every 10 detailed records
                        if len(self.detailed_data) % 10 == 0 and len(self.detailed_data) > 0:
                            logger.info(f"Checkpoint: Saving data after {len(self.detailed_data)} detailed records...")
                            self.save_data()
                    else:
                        logger.warning(f"Failed to process row {row_index + 1}. Attempting to continue.")

                logger.info(f"Page {page_num} complete - Basic records: {len(self.basic_data)}, Detailed records: {len(self.detailed_data)}")
                
                # Check if we should continue
                if self.test_mode and page_num >= 1: # Only scrape 1 page in test mode
                    logger.info("Test mode - stopping after one page.")
                    break
                    
                if not self.navigate_to_next_page():
                    break # No more pages
                    
                page_num += 1
                detailed_records_on_page = 0 # Reset for the new page
                    
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                self.driver.quit()
            except:
                pass
    
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
            
            # Print summary
            logger.info(f"Summary:")
            logger.info(f"  Basic records: {len(self.basic_data)}")
            logger.info(f"  Detailed records: {len(self.detailed_data)}")
            
            if self.detailed_data:
                sample_columns = list(self.detailed_data[0].keys())
                logger.info(f"  Total columns: {len(sample_columns)}")
                logger.info(f"  Sample columns: {sample_columns[:10]}...")
        else:
            logger.warning("No detailed data was scraped yet.")

def main():
    """Main function to run the scraper"""
    # Run in headless mode by default for speed, set test_mode=False to scrape all
    scraper = FNRIFoodScraper(headless=True, test_mode=False) 
    
    try:
        scraper.scrape_data()
        scraper.save_data() # Final save at the end
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user. Saving current data...")
        scraper.save_data()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        scraper.save_data() # Attempt to save data on unexpected error
    finally:
        try:
            if scraper.driver:
                scraper.driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()