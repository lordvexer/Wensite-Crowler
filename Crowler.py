import os
import getpass
import time
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

PC_name=getpass.getuser()



def check_pagination(url):
    # Check if pagination exists by inspecting the first page of results
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    pagination_links = soup.find_all('a', class_='pagination-link')  # Adjust based on actual HTML structure

    return len(pagination_links) > 0


def check_robots_txt(url):
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
    response = requests.get(robots_url)
    if response.status_code == 200:
        robots_txt = response.text
        if 'Disallow: /' in robots_txt:
            print("\033[91mCrawling denied by robots.txt\033[0m")
            decision = input("Do you want to continue crawling despite restrictions? (y/n): ").strip().lower()
            if decision != 'y':
                return False
        else:
            print("\033[92mCrawling allowed by robots.txt\033[0m")
        return True
    else:
        print("\033[93mrobots.txt file not found, proceeding with caution\033[0m")
        return True

# Optimized get_html function to reuse WebDriver instance
def get_html(url, use_selenium=False, scroll_speed=1, scroll_distance=100):
    if not use_selenium:
        response = requests.get(url)
        return BeautifulSoup(response.text, 'html.parser')
    else:
        options = Options()
        options.binary_location = f"C:\\Users\\{PC_name}\\AppData\\Local\\Chromium\\Application\\chrome.exe"
        driver_path = f"C:\\Users\\{PC_name}\\Desktop\\Crowler\\chromedriver127\\chromedriver.exe"
        
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        
        try:
            driver.get(url)
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script(f"window.scrollTo(0, {last_height});")
                time.sleep(scroll_speed)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            html_content = driver.page_source
        finally:
            driver.quit()

        return BeautifulSoup(html_content, 'html.parser')


def extract_products_from_page(soup, product_tag, product_class, name_tag, name_class, price_tag, price_class, rating_tag, rating_class, apply_filters, price_filter, rating_filter):
    products = soup.find_all(product_tag, class_=product_class)
    product_data = []
    
    for product in products:
        try:
            if name_class == price_class == rating_class:
                product_info = {
                    'Name': [],
                    'Price': [],
                    'Rating': []
                }
                # Find all elements under the product tag with the given class
                name_elements = product.find_all(name_tag, class_=name_class)
                price_elements = product.find_all(price_tag, class_=price_class)
                rating_elements = product.find_all(rating_tag, class_=rating_class)
                
                # Iterate over each set of elements and add them to product_info
                for name_elem, price_elem, rating_elem in zip(name_elements, price_elements, rating_elements):
                    product_info['Name'].append(name_elem.text.strip())
                    product_info['Price'].append(price_elem.text.strip())
                    product_info['Rating'].append(rating_elem.text.strip())
                
                product_data.append(product_info)
            else:
                product_name = product.find(name_tag, class_=name_class).text.strip()
                
                if price_tag and price_class:
                    product_price_element = product.find(price_tag, class_=price_class)
                    if product_price_element:
                        product_price = product_price_element.text.strip()
                        try:
                            product_price_value = float(product_price.replace(',', '').replace('تومان', '').strip())
                        except ValueError:
                            product_price_value = 'N/A'
                    else:
                        product_price = 'N/A'
                        product_price_value = 'N/A'
                else:
                    product_price = 'N/A'
                    product_price_value = 'N/A'
                
                if rating_tag and rating_class:
                    product_rating_element = product.find(rating_tag, class_=rating_class)
                    if product_rating_element:
                        product_rating = product_rating_element.text.strip()
                        try:
                            product_rating_value = float(product_rating)
                        except ValueError:
                            product_rating_value = 'N/A'
                    else:
                        product_rating = 'N/A'
                        product_rating_value = 'N/A'
                else:
                    product_rating = 'N/A'
                    product_rating_value = 'N/A'
                
                if apply_filters:
                    if isinstance(product_price_value, float) and isinstance(product_rating_value, (float, int)):
                        if (price_filter[0] <= product_price_value <= price_filter[1] and
                                rating_filter[0] <= product_rating_value <= rating_filter[1]):
                            product_data.append({
                                'Name': product_name,
                                'Price': product_price,
                                'Rating': product_rating
                            })
                    elif isinstance(product_price_value, float):
                        if price_filter[0] <= product_price_value <= price_filter[1]:
                            product_data.append({
                                'Name': product_name,
                                'Price': product_price,
                                'Rating': product_rating
                            })
                    elif isinstance(product_rating_value, (float, int)):
                        if rating_filter[0] <= product_rating_value <= rating_filter[1]:
                            product_data.append({
                                'Name': product_name,
                                'Price': product_price,
                                'Rating': product_rating
                            })
                    else:
                        product_data.append({
                            'Name': product_name,
                            'Price': product_price,
                            'Rating': product_rating
                        })
                else:
                    product_data.append({
                        'Name': product_name,
                        'Price': product_price,
                        'Rating': product_rating
                    })
        except AttributeError:
            continue
        except ValueError as e:
            print(f"Error processing product: {product_name} - {e}")
            continue
    
    return product_data


def crawl_website(start_url, num_pages, product_tag, product_class, name_tag, name_class, price_tag, price_class, rating_tag, rating_class, apply_filters, price_filter, rating_filter, use_selenium=False, scroll_speed=2, scroll_distance=1000, show_more_class=None):
    all_products = []

    # Prompt user for number of products to save
    num_to_save = int(input("Enter how many products you want to save: "))

    # Loop through each page to crawl
    for page in range(1, num_pages + 1):
        if num_pages > 1:
            url = f"{start_url}&page={page}"  # Adjust based on actual pagination structure
        else:
            url = start_url  # Use the same URL for lazy loading

        print(f"Crawling page: {page}")

        # Get HTML content using Selenium to ensure all lazy-loading content is loaded
        soup = get_html(url, use_selenium=use_selenium, scroll_speed=scroll_speed, scroll_distance=scroll_distance)

        # Click on "Show More" button if specified
        if show_more_class:
            try:
                while True:
                    button = soup.find('button', class_=show_more_class)
                    if not button:
                        break
                    if use_selenium:
                        # Use Selenium to click on the button
                        options = Options()
                        options.binary_location = f"C:\\Users\\{PC_name}\\AppData\\Local\\Chromium\\Application\\chrome.exe"
                        driver_path = f"C:\\Users\\{PC_name}\\Desktop\\Crowler\\chromedriver127\\chromedriver.exe"
                        
                        service = Service(executable_path=driver_path)
                        driver = webdriver.Chrome(service=service, options=options)
                        
                        try:
                            driver.get(url)
                            driver.find_element(By.CLASS_NAME, show_more_class).click()
                            time.sleep(3)  # Adjust as needed for content to load
                            soup = BeautifulSoup(driver.page_source, 'html.parser')
                        finally:
                            driver.quit()
                    else:
                        button.click()  # You may need to use Selenium for clicking
                        time.sleep(3)  # Adjust as needed for content to load
            except Exception as e:
                print(f"Error clicking 'Show More' button: {e}")

        # Extract products from fully loaded HTML
        products = extract_products_from_page(soup, product_tag, product_class, name_tag, name_class, price_tag, price_class, rating_tag, rating_class, apply_filters, price_filter, rating_filter)
        
        # Calculate remaining products to save
        remaining_to_save = num_to_save - len(all_products)
        
        # Limit to saving only the remaining products needed
        if remaining_to_save > 0:
            num_to_append = min(remaining_to_save, len(products))
            all_products.extend(products[:num_to_append])

        print(f"Extracted {len(products)} products from page {page}")

        # Stop if the desired number of products has been saved
        if len(all_products) >= num_to_save:
            break

        if num_pages == 1:
            break  # Stop after the first page if no pagination

    return all_products




def save_to_csv(products, filename):
    df = pd.DataFrame(products)
    df.to_csv(filename, index=False, encoding='utf-8-sig')  # Ensure proper encoding for Persian characters
    print(f"Saved {len(products)} products to {filename}")

if __name__ == '__main__':
    start_url = input("Enter the start URL (search results URL): ")
    num_pages = int(input("Enter the number of pages to crawl (enter 1 for lazy loading sites): "))
    output_file = input("Enter the output CSV filename (e.g., 'products.csv'): ")

    product_tag = input("Enter the HTML tag for products (e.g., 'div'): ").strip()
    product_class = input("Enter the class name for products (leave empty if none): ").strip()
    name_tag = input("Enter the HTML tag for product names (e.g., 'h2'): ").strip()
    name_class = input("Enter the class name for product names (leave empty if none): ").strip()
    price_tag = input("Enter the HTML tag for product prices (e.g., 'span'): ").strip()
    price_class = input("Enter the class name for product prices (leave empty if none): ").strip()
    rating_tag = input("Enter the HTML tag for product ratings (e.g., 'span'): ").strip()
    rating_class = input("Enter the class name for product ratings (leave empty if none): ").strip()
 
    apply_filters = input("Do you need filtering? (yes/no): ").strip().lower() == 'yes'
    
    if apply_filters:
        price_min = float(input("Enter the minimum price for filtering: "))
        price_max = float(input("Enter the maximum price for filtering: "))
        rating_min = input("Enter the minimum rating for filtering: ")
        rating_max = input("Enter the maximum rating for filtering: ")
        price_filter = (price_min, price_max)
        rating_filter = (rating_min, rating_max)
    else:
        price_filter = (0, float('inf'))  # No filtering
        rating_filter = (0, float('inf'))  # No filtering

    if num_pages > 1:
        use_selenium = False  # Assume pagination
        scroll_speed = None
        scroll_distance = None
    else:
        use_selenium = True   # Lazy loading site, crawl one page
        scroll_speed = float(input("Enter scrolling speed (e.g., 2): "))
        scroll_distance = int(input("Enter scrolling distance (e.g., 1000): "))

    has_show_more = input("Does the page have a 'Show More' button? (yes/no): ").strip().lower() == 'yes'
    if has_show_more:
        show_more_class = input("Enter the class name of the 'Show More' button: ").strip()
    else:
        show_more_class = None

    products = crawl_website(start_url, num_pages, product_tag, product_class, name_tag, name_class, price_tag, price_class, rating_tag, rating_class, apply_filters, price_filter, rating_filter, use_selenium=use_selenium, scroll_speed=scroll_speed, scroll_distance=scroll_distance, show_more_class=show_more_class)
    if products:
        save_to_csv(products, output_file)
    else:
        print("No products were found.")
