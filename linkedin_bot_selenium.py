import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=GEMINI_API_KEY)

class LinkedInAutomation:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None

    def setup_driver(self):
        options = Options()
        # options.add_argument('--headless')  # Uncomment for headless mode
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-notifications')
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def login_to_linkedin(self):
        try:
            self.driver.get('https://www.linkedin.com/login')
            time.sleep(random.uniform(2, 4))

            # Enter email
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.send_keys(self.email)

            # Enter password
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(self.password)

            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()

            time.sleep(random.uniform(3, 5))
            return True
        except Exception as e:
            print(f"Login failed: {str(e)}")
            return False

    def create_post(self, content):
        try:
            # Go to LinkedIn home page
            self.driver.get('https://www.linkedin.com/feed/')
            time.sleep(random.uniform(2, 4))

            # Click on start post button
            start_post_button = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button[data-control-name='create_post']")))
            start_post_button.click()
            time.sleep(random.uniform(2, 3))

            # Find the post textarea and enter content
            post_field = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[data-placeholder='What do you want to talk about?']")))
            post_field.send_keys(content)
            time.sleep(random.uniform(2, 3))

            # Click post button
            post_button = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button[data-control-name='share.post']")))
            post_button.click()
            time.sleep(random.uniform(3, 5))

            print("Post successfully created on LinkedIn.")
            return True
        except Exception as e:
            print(f"Failed to create post: {str(e)}")
            return False

    def fetch_ai_trends_from_google(self, search_subject='AI+OR+machine+learning', sheet_path='processed_urls.csv'):
        try:
            url = f'https://news.google.com/search?q={search_subject}&hl=en-US&gl=US&ceid=US:en'
            self.driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Get page source and parse with BeautifulSoup
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract article links
            articles = soup.find_all('article')
            for article in articles:
                link = article.find('a')
                if link and 'href' in link.attrs:
                    url = 'https://news.google.com' + link['href'][1:]
                    return url

            return None
        except Exception as e:
            print(f"Error fetching news: {str(e)}")
            return None

    def generate_linkedin_post(self, url):
        try:
            self.driver.get(url)
            time.sleep(random.uniform(3, 5))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            title = soup.title.string if soup.title else ""
            article_text = ""
            for paragraph in soup.find_all('p'):
                article_text += paragraph.get_text() + "\n"

            # Find the position of the first period after 500 characters
            end_position = article_text[:500].rfind('.') + 1
            if end_position == 0:
                end_position = 500
            
            prompt = f"""Based on this article:
Title: {title}
Content: {article_text[:end_position]}

Please create an engaging LinkedIn post The post should have a hook,rehook,body,call to action:
0. Captures attention with a strong opening line
1. Highlights the key points of the article
2. Adds professional insights
3. Uses appropriate hashtags
4. Includes a call to action
5. Keeps the length appropriate for LinkedIn (under 1300 characters)
6. Maintains a professional tone
7. Don't include source URL
8. Use a professional tone
9. Add 'Follow for more AI insights'
10. Be creative
11. Add questions to keep people engaged
Format the post with line breaks and emojis where appropriate."""

            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            
            return response.text
            
        except Exception as e:
            print(f"Error generating LinkedIn post: {str(e)}")
            return None

    def close(self):
        if self.driver:
            self.driver.quit()

def main():
    # Get LinkedIn credentials from environment variables
    linkedin_email = os.getenv('LINKEDIN_EMAIL')
    linkedin_password = os.getenv('LINKEDIN_PASSWORD')

    if not all([linkedin_email, linkedin_password]):
        raise ValueError("LinkedIn credentials not found in environment variables")

    bot = LinkedInAutomation(linkedin_email, linkedin_password)
    
    try:
        print("Setting up automation...")
        bot.setup_driver()

        print("Logging in to LinkedIn...")
        if not bot.login_to_linkedin():
            raise Exception("Failed to login to LinkedIn")

        print("Welcome to LinkedIn Content Automation!")
        search_subject = input("Enter your search subject (e.g., 'AI+OR+machine+learning'): ")
        if not search_subject:
            raise ValueError("Search subject cannot be empty")

        # Replace spaces with + for URL compatibility
        search_subject = search_subject.replace(' ', '+')
        
        print("\nFetching AI news articles...")
        article_url = bot.fetch_ai_trends_from_google(search_subject)
        
        if article_url:
            print(f"\nGenerating post for article: {article_url}")
            linkedin_post = bot.generate_linkedin_post(article_url)
            
            if linkedin_post:
                print("\nCreating LinkedIn post...")
                bot.create_post(linkedin_post)
            else:
                print("Failed to generate post content")
        else:
            print("No suitable articles found")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    finally:
        print("\nClosing automation...")
        bot.close()

if __name__ == "__main__":
    main()
