import requests
from bs4 import BeautifulSoup
import re
import google.generativeai as genai
import pandas as pd
import time
import random
import json
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
GEMINI_API_KEY = 'AIzaSyB961o81sr_ZYe7TDdzYoSpbiZnmnc2Tx0'
LINKEDIN_ACCESS_TOKEN = 'AQX0gupmnGNhmo3sVfBYcg66DuJf7-dKOcIzgY0qUOzrDpxIY6euoD_cakjh9gBUD9dc3PfaIaaxPWajDrlpRSOSz4csDCxqud0gztszYr-8RdAL8_4LTYuzQkkKu8Eog-um40iWVo_a-_hHLOO4FpffOGd1NEPKtc0AYG0VAQM0OTgO2yfW5z9RbOyqmSbSZlts8hSowzAC-ndOLxhBt9iGm3Lvkq-1jNSD2bN50eEXYadieJZpMgIUa1Ok6aRAhywj4C6yq4zOoTTRrwehQcpxOn8drl8nC97WowfmKG3gHNgy8OkL1mM3j1f1vtBeQTMlz2UYvEKYjRXg67jWXQUz4_G1Lg'
LINKEDIN_AUTHOR_URN = 'urn:li:person:fUeHya-Bcp'  # Your Person ID

genai.configure(api_key=GEMINI_API_KEY)

# --- UTILS ---

def read_processed_urls(sheet_path='processed_urls.csv'):
    try:
        df = pd.read_csv(sheet_path)
        return set(df['url'].tolist())
    except FileNotFoundError:
        return set()

def add_url_to_sheet(sheet_path, url):
    clean_url = url.rstrip('/')
    df = pd.DataFrame({'url': [clean_url]})
    try:
        try:
            pd.read_csv(sheet_path)
            # File exists, append without header
            df.to_csv(sheet_path, mode='a', header=False, index=False)
        except FileNotFoundError:
             # File doesn't exist, create with header
            df.to_csv(sheet_path, mode='w', header=True, index=False)
    except Exception as e:
        print(f"Error saving URL: {e}")

# --- TOPIC MANAGEMENT ---

class TopicManager:
    def __init__(self, history_file='topic_history.json'):
        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self):
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def get_banned_topics(self, days=5):
        """Returns topics used in the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        banned = []
        for entry in self.history:
            try:
                entry_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                if entry_date > cutoff:
                    banned.append(entry['topic'])
            except ValueError:
                continue # Skip malformed dates
        return banned

    def log_topic(self, topic):
        """Logs a new topic usage."""
        print(f"Logging topic usage: {topic}")
        self.history.append({
            'date': datetime.now().strftime("%Y-%m-%d"),
            'topic': topic
        })
        # Keep history clean, limit to last 50 entries
        if len(self.history) > 50:
            self.history = self.history[-50:]
        
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Error saving topic history: {e}")

def get_trending_topic(avoid_topics):
    """Asks Gemini for a trending topic, avoiding recent ones."""
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    avoid_str = ", ".join(avoid_topics) if avoid_topics else "None"
    
    prompt = f"""
    Suggest ONE currently trending search term/topic in the Technology sector for today ({datetime.now().strftime('%Y-%m-%d')}).
    
    Scope:
    - AI & Tech (Generative AI, Robotics, Hardware, Software)
    - Tech x Finance (FinTech, Crypto regulations, AI in banking)
    - Tech x Marketing (AdTech, Social Media algorithms, AI content)
    
    Context:
    - This is for a LinkedIn bot that finds news articles.
    - The topic must be popular enough to have news written about it TODAY.
    
    Constraints:
    - Respond with JUST the search term. No quotes, no explanations.
    - Do NOT suggest any of these previously covered topics: {avoid_str}
    - Keep it under 5 words.
    """
    
    try:
        print("Consulting AI for trending topics...")
        response = model.generate_content(prompt)
        topic = response.text.strip().replace('"', '').replace("'", "")
        print(f"AI Suggested Topic: {topic}")
        return topic
    except Exception as e:
        print(f"Topic generation error: {e}")
        return "Artificial Intelligence" # Safe fallback

# --- AI ENGINES ---

def filter_article_with_ai(title, content_snippet):
    """
    Asks Gemini if the article is worth posting.
    Returns: Boolean
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Act as a strictly critical Editor-in-Chief for a high-end Tech Consultancy.
    
    Article Title: {title}
    Snippet: {content_snippet[:1000]}
    
    Task: Decide if this article is worthy of a LinkedIn post for an AI/Tech professional audience.
    Criteria for YES:
    1. Discusses a MAJOR breakthrough, meaningful trend, or useful tool.
    2. Is not just generic marketing fluff or a "how to install python" tutorial.
    3. Has substance to comment on.
    
    Reply ONLY with 'YES' or 'NO'.
    """
    try:
        response = model.generate_content(prompt)
        decision = response.text.strip().upper()
        # print(f"AI Editor decision: {decision}")
        return "YES" in decision
    except Exception as e:
        print(f"Filter error: {e}")
        return True # Default to allow if error

def generate_viral_post(title, article_text, url):
    """
    Generates a high-quality LinkedIn post using advanced prompting.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = f"""
    ROLE: Expert AI Thought Leader & Tech Influencer.
    TONE: Professional yet conversational, insightful, forward-thinking.
    
    SOURCE MATERIAL:
    Title: {title}
    Content: {article_text[:2000]}
    
    TASK: Write a LinkedIn post that will get high engagement.
    
    STRUCTURE:
    1. **The Hook**: A standalone, punchy one-liner that disrupts common thinking or states a surprising fact. (Max 15 words)
    2. **The Spacer**: A blank line.
    3. **The Insight**: 2-3 short paragraphs explaining WHY this matters. Do not just summarize. Add value. Synthesize. Connect dots.
    4. **The Pivot**: "This changes how we think about [Concept]..."
    5. **The Question**: An engaging question to drive comments.
    6. **Hashtags**: 3-5 relevant, high-traffic hashtags.
    
    CONSTRAINTS:
    - NO "In this article" or "I was reading today". Start directly with the topic.
    - NO "Thrilled to announce" or generic corporate speak.
    - NO long walls of text. Use short sentences.
    - DO NOT include the URL in the text body (it will be attached as a link card).
    - Emoji usage: Moderate (2-3 max), used for emphasis, not decoration.
    
    OUTPUT FORMAT:
    Just the post text. No "Here is the post" preamble.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Generation error: {e}")
        return None

# --- CONTENT FETCHING ---

def fetch_content(search_term, strict_filter=True):
    print(f"Searching for news on: {search_term}...")
    url = f'https://news.google.com/search?q={search_term}&hl=en-US&gl=US&ceid=US:en'
    
    try:
        response = requests.get(url, timeout=15)
        # Hybrid extraction: Soup + Regex to ensure we miss nothing
        soup = BeautifulSoup(response.content, 'html.parser')
        html_str = str(response.content)
        
        potential_urls = set()
        
        # Method 1: BS4
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('./'):
                href = href.replace('./', 'https://news.google.com/')
            potential_urls.add(href)
            
        # Method 2: Regex (Fallback for weird DOM structures)
        regex_urls = re.findall(r'https?://news\.google\.com/[^\s<>"]+', html_str)
        potential_urls.update(regex_urls)
        
        # Filter for actual articles
        article_candidates = []
        for u in potential_urls:
            if 'articles' in u or '/read/' in u:
                article_candidates.append(u)
        
        print(f"Found {len(article_candidates)} potential links. Checking top candidates...")
        
        processed = read_processed_urls()
        
        count = 0
        for p_url in article_candidates:
            if count >= 15: break # Check max 15 links
            
            try:
                # Resolve redirect
                try:
                    final_res = requests.get(p_url, timeout=10)
                    final_url = final_res.url
                except:
                    continue

                # Skip exclusions
                exclude = ['nyt.com', 'wsj.com', 'bloomberg.com', 'youtube.com']
                if any(x in final_url for x in exclude):
                    continue
                
                if final_url in processed:
                    continue
                
                # Parse
                article_soup = BeautifulSoup(final_res.content, 'html.parser')
                title = article_soup.title.string if article_soup.title else ""
                if not title: continue
                
                texts = [p.get_text() for p in article_soup.find_all('p')]
                text_content = "\n".join(texts)
                
                # RELAXED LENGTH CHECK: Only 200 chars needed
                if len(text_content) < 200: 
                    continue

                print(f"  > Evaluating: {title[:50]}...")
                
                # AI Filter
                if strict_filter:
                    if filter_article_with_ai(title, text_content):
                        return {'title': title, 'text': text_content, 'url': final_url}
                    else:
                        print("    - Rejected by AI (Too generic/low quality)")
                        add_url_to_sheet('processed_urls.csv', final_url) # Don't check again
                else:
                    # SUPER PERMISSIVE MODE: Just take it!
                    print("    - Accepted (Panic Mode Active - Taking First Result)")
                    return {'title': title, 'text': text_content, 'url': final_url}
                
                count += 1
                
            except Exception as e:
                continue

    except Exception as e:
        print(f"Fetch error: {e}")
        
    return None

# --- MAIN ---

def main():
    print("=== LinkedIn Bot Pro (Autonomous v2) ===")
    
    tm = TopicManager()
    banned_topics = tm.get_banned_topics(days=5)
    
    # Strategy: 3 Layers of Fallback
    # 1. Specific Trending Topic (Strict Filter)
    # 2. Broader Category (Strict Filter)
    # 3. "Latest Tech News" (Loose Filter - Panic Mode)
    
    topics_to_try = []
    
    # Layer 1
    trending = get_trending_topic(banned_topics)
    topics_to_try.append((trending, False)) # Strict=False (User Request: Use first result)
    
    # Layer 2
    topics_to_try.append(("Artificial Intelligence News", False))
    topics_to_try.append(("Emerging Technology Trends", False))
    
    # Layer 3
    topics_to_try.append(("TechCrunch", False))
    
    article = None
    selected_topic = ""
    
    for topic, strict in topics_to_try:
        print(f"\n[Attempt] Topic: '{topic}' | Strict Filter: {strict}")
        article = fetch_content(topic, strict_filter=strict)
        if article:
            selected_topic = topic
            print(f"Content Found! Source: {article['title']}")
            break
        else:
            print("No suitable content found. Trying next fallback...")
            
    if not article:
        print("\nCRITICAL: Could not find ANY content after all fallbacks.")
        return

    # Post Generation
    print("\nGenerating viral post...")
    post_text = generate_viral_post(article['title'], article['text'], article['url'])
    
    if not post_text:
        print("Failed to generate post text.")
        return
    
    print("\n" + "="*50)
    print("PREVIEW:")
    print(post_text)
    print("="*50)
    print(f"ATTACHMENT: {article['url']}")
    
    confirm = input("\nPublish this post? (y/n): ").lower()
    if confirm == 'y':
        if post_article_to_linkedin(post_text, article['url'], article['title']):
            add_url_to_sheet('processed_urls.csv', article['url'])
            tm.log_topic(selected_topic)
    else:
        print("Cancelled.")

if __name__ == "__main__":
    main()
