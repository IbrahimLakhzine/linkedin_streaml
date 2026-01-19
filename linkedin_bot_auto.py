import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from requests_oauthlib import OAuth2Session
import google.generativeai as genai
import pandas as pd

# Constants
GEMINI_API_KEY = 'AIzaSyCT7Kkc5Sd10Egf5k8Cc3eyaz4T5N0IKlk'  # Replace with your valid Gemini API key
LINKEDIN_CLIENT_ID = '78pz3yi7wreoza'
LINKEDIN_CLIENT_SECRET = 'WPL_AP1.TNKBz3giqsCwTbT6.TXgD+w=='
LINKEDIN_REDIRECT_URI = 'https://www.linkedin.com/in/ibrahim-lakhzine-9739a112b/'
LINKEDIN_ACCESS_TOKEN = 'AQX0gupmnGNhmo3sVfBYcg66DuJf7-dKOcIzgY0qUOzrDpxIY6euoD_cakjh9gBUD9dc3PfaIaaxPWajDrlpRSOSz4csDCxqud0gztszYr-8RdAL8_4LTYuzQkkKu8Eog-um40iWVo_a-_hHLOO4FpffOGd1NEPKtc0AYG0VAQM0OTgO2yfW5z9RbOyqmSbSZlts8hSowzAC-ndOLxhBt9iGm3Lvkq-1jNSD2bN50eEXYadieJZpMgIUa1Ok6aRAhywj4C6yq4zOoTTRrwehQcpxOn8drl8nC97WowfmKG3gHNgy8OkL1mM3j1f1vtBeQTMlz2UYvEKYjRXg67jWXQUz4_G1Lg'  # Obtain this through the OAuth flow

genai.configure(api_key=GEMINI_API_KEY)

# Function to get trending tech topic
def get_trending_tech_topic():
    print("Consulting AI for trending tech topics...")
    model = genai.GenerativeModel("gemini-1.5-flash") # Using 1.5 flash for speed/cost, or could use 2.5
    
    prompt = f"""
    Give me one trending technical specific search term for Google News related to AI, Tech, or Finance for today ({datetime.now().strftime('%Y-%m-%d')}). 
    Output ONLY the search term (e.g., 'Gemini 1.5 Pro launch' or 'Nvidia stock surge'). Do not add quotes.
    """
    try:
        response = model.generate_content(prompt)
        topic = response.text.strip().replace('"', '').replace("'", "")
        print(f"AI Suggested Topic: {topic}")
        return topic
    except Exception as e:
        print(f"Error generating topic: {e}")
        return "Artificial Intelligence News"

# Function to read processed URLs from a sheet

def read_processed_urls(sheet_path):
    try:
        df = pd.read_csv(sheet_path)
        return set(df['url'].tolist())
    except FileNotFoundError:
        return set()

# Function to add a URL to the sheet

def add_url_to_sheet(sheet_path, url):
    # Ensure URL does not end with a slash
    clean_url = url.rstrip('/')
    df = pd.DataFrame({'url': [clean_url]})
    
    # Check if file exists to handle header correctly
    try:
        pd.read_csv(sheet_path)
        # File exists, append without header
        df.to_csv(sheet_path, mode='a', header=False, index=False)
    except FileNotFoundError:
        # File doesn't exist, create with header
        df.to_csv(sheet_path, mode='w', header=True, index=False)

# Function to fetch AI/ML news articles from Google News and summarize the first article

def fetch_ai_trends_from_google_and_summarize(search_subject='AI+OR+machine+learning', sheet_path='processed_urls.csv'):
    # Replace spaces with + for URL compatibility within the function now
    search_query = search_subject.replace(' ', '+')
    url = f'https://news.google.com/search?q={search_query}&hl=en-US&gl=US&ceid=US:en'
    
    print(f"Searching for: {search_subject}...")
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract all HTTPS URLs using regex
    html_content = str(soup)
    https_urls = re.findall(r'https?://[^\s<>"]+', html_content, re.IGNORECASE)
    
    # Define exclusion patterns
    exclude_patterns = [
        'gstatic.com',
        'googleusercontent.com',
        'google.com/search',
        'google.com/url',
        'accounts.google.com',
        'play.google.com',
        'blogger.googleusercontent.com',
        'cdn-apple.com',
        'cloudfront.net',
        'springernature.com',
        'b-cdn.net',
        'transforms.svdcdn.com',
        'contentstack.com',
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico',
        'favicon',
        'image', '/img/', '/images/',
        'media.',
        'thumbnail',
        'storage.googleapis.com',
        'lh3.googleusercontent.com',
        'accounts.',
        'login.',
        'auth.',
        'amp/',
        '.amp',  
        'rss/',
        'feed/',
        'signup',
        'subscribe',
        'advertisement',
        'analytics'
    ]
    
    processed_urls = read_processed_urls(sheet_path)
    relevant_urls = []
    seen_urls = set()
    
    for url in https_urls:
        if any(pattern in url.lower() for pattern in exclude_patterns):
            continue
        if any(keyword in url.lower() for keyword in ['ai', 'artificial-intelligence', 'machine-learning', 'tech', 'finance', 'crypto', 'robotics']): # Expanded keywords
            clean_url = url.split('?')[0].split('#')[0].rstrip('/')
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                if clean_url not in processed_urls:
                    relevant_urls.append(url)
    
    # Fallback: if no keywords match but it's a valid article link (panic mode logic from Pro version, simplified)
    if not relevant_urls:
         for url in https_urls:
            if any(pattern in url.lower() for pattern in exclude_patterns): continue
            if '/read/' in url or 'articles' in url:
                clean_url = url.split('?')[0].split('#')[0].rstrip('/')
                if clean_url not in seen_urls and clean_url not in processed_urls:
                    relevant_urls.append(url)

    selected_url = None
    for url in relevant_urls:
        clean_url = url.split('?')[0].split('#')[0].rstrip('/')
        if clean_url not in processed_urls:
            print(f"Checking URL: {clean_url}")
            try:
                response = requests.get(clean_url, timeout=10) # Added timeout
                if response.status_code == 200:
                    selected_url = clean_url
                    print(f"Good URL found: {clean_url}")
                    # Add URL to sheet regardless of request outcome to stop loops
                    add_url_to_sheet(sheet_path, clean_url)
                    break
                else:
                    print(f"HTTP error encountered: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Request exception encountered: {e}")

    print("Most Recent AI News Article:")
    if selected_url:
        print(selected_url)
    else:
        print("No new unprocessed URLs found or all URLs resulted in errors.")
    
    return selected_url

# Function to post content to LinkedIn

def post_to_linkedin(content, access_token):
    linkedin_api_url = 'https://api.linkedin.com/v2/ugcPosts'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    post_data = {
        "author": "urn:li:person:fUeHya-Bcp",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": content
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    response = requests.post(linkedin_api_url, headers=headers, json=post_data)
    if response.status_code == 201:
        print("Post successfully created on LinkedIn.")
    else:
        print(f"Failed to create post: {response.status_code}", response.json())

# Function to generate LinkedIn posts using Gemini

def generate_linkedin_post(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.title.string if soup.title else ""
        article_text = ""
        for paragraph in soup.find_all('p'):
            article_text += paragraph.get_text() + "\n"
        print(title)
        # print(article_text) # Hidden to reduce noise
        
        # Find the position of the first period after 500 characters
        end_position = article_text[:500].rfind('.') + 1
        # If no period is found, default to 500 characters
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
7. don't include source URL at all or something like refer to the blog post (url)
8. never do like this and talk on my behalf "Tired of AI limited to text?  My latest article explores building Multimodal RAG systems – enabling your AI to process ANY file type (images, PDFs, audio, etc.)!  This builds upon previous work on multimodal LLMs and embedding models." 'My latest article' talk in general about the article 
9. use something like  'follow me for more on AI news' 
10. be creative 
11. add questions to keep people engaged
Format the post with line breaks and emojis where appropriate.
12. dont add something like Here's an engaging LinkedIn post based on the article:

give just the post"""     

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        
        linkedin_post = response.text
        
        print("\nGenerated LinkedIn Post:")
        print("-" * 50)
        print(linkedin_post)
        print("-" * 50)
        
        return linkedin_post
        
    except Exception as e:
        print(f"Error generating LinkedIn post: {str(e)}")
        return None

def main():
    print("Welcome to LinkedIn Content Automation (Auto Mode)!")
    
    # OLD: Manual Input
    # search_subject = input("Enter your search subject (e.g., 'AI+OR+machine+learning'): ")
    
    # NEW: Automated Input
    search_subject = get_trending_tech_topic()
    
    if search_subject=='':
        # Fallback
        search_subject = "Artificial Intelligence News"
    
    # Fetch and process the article (using the new automated topic)
    selected_url = fetch_ai_trends_from_google_and_summarize(search_subject)
    
    if selected_url:
        # Generate and post content
        linkedin_post = generate_linkedin_post(selected_url)
        if linkedin_post:
            confirm = input("\nPublish this post? (y/n): ").lower()
            if confirm == 'y':
                post_to_linkedin(linkedin_post, LINKEDIN_ACCESS_TOKEN)
            else:
                print("Cancelled.")
    else:
        print("No new articles found for the given subject.")

if __name__ == "__main__":
    main()
