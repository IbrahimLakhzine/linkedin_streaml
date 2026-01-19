import requests
from bs4 import BeautifulSoup

def test_google_news_scraping(topic="Artificial Intelligence"):
    url = f'https://news.google.com/search?q={topic}&hl=en-US&gl=US&ceid=US:en'
    print(f"Testing URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        print(f"Found {len(links)} links total.")
        
        article_links = []
        for i, link in enumerate(links):
            href = link.get('href', '')
            if i < 30:
                print(f"Link {i}: {href}")
            if 'articles/' in href:
                if href.startswith('./'):
                    full_url = href.replace('./', 'https://news.google.com/')
                elif href.startswith('/'):
                    full_url = 'https://news.google.com' + href
                else:
                    full_url = href
                article_links.append(full_url)
        
        print(f"Found {len(article_links)} potential article links.")
        for l in article_links[:5]:
            print(f"  - {l}")
            
        if article_links:
            test_link = article_links[0]
            print(f"\nTesting first link redirect: {test_link}")
            try:
                res = requests.get(test_link, headers=headers, timeout=5)
                print(f"Final URL: {res.url}")
                print(f"Content length: {len(res.text)}")
                
                inner_soup = BeautifulSoup(res.content, 'html.parser')
                p_tags = inner_soup.find_all('p')
                print(f"Found {len(p_tags)} paragraph tags.")
            except Exception as e:
                print(f"Error following redirect: {e}")
                
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_google_news_scraping()
