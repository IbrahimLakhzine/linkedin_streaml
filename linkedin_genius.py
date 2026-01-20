import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import json
import time
import io
from PIL import Image, ImageDraw, ImageFont
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- SETUP PAGE ---
st.set_page_config(
    page_title="LinkedIn Genius",
    page_icon="🕴️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURATION ---
def get_secret(key, default=None):
    try:
        # st.secrets behaves like a dict but can raise an error if no secrets file exists at all
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # Fallback if secrets are not configured or st.secrets raises an error
        pass
    return os.getenv(key, default)

# Initial load from env/secrets
LINKEDIN_ACCESS_TOKEN = get_secret('LINKEDIN_ACCESS_TOKEN')
LINKEDIN_AUTHOR_URN = get_secret('LINKEDIN_AUTHOR_URN')

# --- UI SETTINGS (SIDEBAR) ---
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    ui_api_key = st.text_input(
        "Gemini API Key", 
        value=get_secret('GEMINI_API_KEY', ""),
        type="password",
        help="Enter your Gemini API key here. It will override the default key if provided."
    )

    # Use UI key if provided, else fallback to secrets
    GEMINI_API_KEY = ui_api_key if ui_api_key else get_secret('GEMINI_API_KEY')

    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        st.warning("⚠️ Gemini API Key is missing. Please enter it above or add it to your secrets.")


# --- UTILS ---

def get_trending_tech_topic():
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Give me one trending technical specific search term for Google News related to AI, Tech, or Finance for today ({datetime.now().strftime('%Y-%m-%d')}). 
    Output ONLY the search term. No quotes.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '').replace("'", "")
    except:
        return "Artificial Intelligence News"

def read_processed_urls(sheet_path='processed_urls.csv'):
    try:
        df = pd.read_csv(sheet_path)
        return set(df['url'].tolist())
    except FileNotFoundError:
        return set()

def add_url_to_sheet(url, sheet_path='processed_urls.csv'):
    clean_url = url.split('?')[0].split('#')[0].rstrip('/')
    df = pd.DataFrame({'url': [clean_url]})
    try:
        pd.read_csv(sheet_path)
        df.to_csv(sheet_path, mode='a', header=False, index=False)
    except FileNotFoundError:
        df.to_csv(sheet_path, mode='w', header=True, index=False)

def fetch_article_content(topic):
    search_query = topic.replace(' ', '+')
    url = f'https://news.google.com/search?q={search_query}&hl=en-US&gl=US&ceid=US:en'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Robust Regex Extraction from Bot Auto
        html_content = str(soup)
        https_urls = re.findall(r'https?://[^\s<>"]+', html_content, re.IGNORECASE)
        
        exclude_patterns = [
            'gstatic.com', 'googleusercontent.com', 'google.com/search', 'google.com/url',
            'accounts.google.com', 'play.google.com', 'blogger.googleusercontent.com',
            'cdn-apple.com', 'cloudfront.net', 'springernature.com', 'b-cdn.net',
            'transforms.svdcdn.com', 'contentstack.com', '.jpg', '.jpeg', '.png', '.gif', 
            '.webp', '.ico', 'favicon', 'image', '/img/', '/images/', 'media.', 
            'thumbnail', 'storage.googleapis.com', 'lh3.googleusercontent.com', 
            'accounts.', 'login.', 'auth.', 'amp/', '.amp', 'rss/', 'feed/', 
            'signup', 'subscribe', 'advertisement', 'analytics'
        ]
        
        processed_urls = read_processed_urls()
        relevant_urls = []
        seen_urls = set()
        
        # Keyword filtering
        keywords = ['ai', 'artificial-intelligence', 'machine-learning', 'tech', 'finance', 'crypto', 'robotics']
        
        for url in https_urls:
            if any(pattern in url.lower() for pattern in exclude_patterns):
                continue
            if any(kw in url.lower() for kw in keywords):
                clean_url = url.split('?')[0].split('#')[0].rstrip('/')
                if clean_url not in seen_urls and clean_url not in processed_urls:
                    seen_urls.add(clean_url)
                    relevant_urls.append(url)
        
        # Panic Mode Fallback
        if not relevant_urls:
            for url in https_urls:
                if any(pattern in url.lower() for pattern in exclude_patterns): continue
                if '/read/' in url or 'articles' in url:
                    clean_url = url.split('?')[0].split('#')[0].rstrip('/')
                    if clean_url not in seen_urls and clean_url not in processed_urls:
                        relevant_urls.append(url)
        
        # Pick the first good one
        for target_url in relevant_urls:
            try:
                res = requests.get(target_url, headers=headers, timeout=10)
                if res.status_code == 200:
                    article_soup = BeautifulSoup(res.content, 'html.parser')
                    title = article_soup.title.string if article_soup.title else "News"
                    texts = [p.get_text() for p in article_soup.find_all(['p', 'div'])]
                    content = "\n".join(texts)
                    
                    return {
                        'title': title, 
                        'text': content[:2000], # Keep summary for Gemini
                        'url': res.url
                    }
            except:
                continue
                
    except Exception as e:
        st.error(f"Fetch Error: {e}")
        
    return None

def generate_post_text(content, type="article", quiz_data=None):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = ""
    
    if type == "article":
        prompt = f"""Act as a LinkedIn Influencer. Write a VIRAL post based on this news:
        Title: {content['title']}
        Content Preview: {content['text'][:1000]}
        
        The post MUST follow this structure:
        0. Hook: Captures attention with a strong opening line.
        1. Rehook: Keeps them reading.
        2. Body: Highlights key points + professional insights.
        3. Question: Ask something to drive engagement.
        4. CTA: "Follow me for more on AI and Tech news!"
        5. Hashtags: Use 3-5 relevant hashtags.
        
        Rules:
        - Max 1300 chars.
        - Professional yet creative tone.
        - Don't include the source URL in the text.
        - Don't say "My latest article", talk about the news in general.
        - Use line breaks and emojis.
        - Return ONLY the post text.
        """
    elif type == "image":
        prompt = f"""
        Act as a LinkedIn Influencer. Write a VIRAL post based on this image description:
        Description: {content}
        
        Rules:
        - Hook: Relate the image to a broader professional lesson.
        - Insight + Question + Hashtags.
        - Max 1200 chars.
        - No "Here is a post".
        """
    elif type == "quiz":
        prompt = f"""
        Act as a LinkedIn Influencer. Write an ENGAGING post to accompany this quiz challenge:
        Category: {quiz_data['category']}
        Question: {quiz_data['question']}
        Options: {quiz_data['options']}
        
        Rules:
        - Start with a hook like "Can you solve this?" or "Test your skills!"
        - Challenge followers to comment their answer (A, B, C, or D)
        - Promise to reveal the answer in comments or next post
        - Use relevant hashtags (#{quiz_data['category'].replace(' ', '')} #TechQuiz #CodingChallenge)
        - Max 800 chars.
        - No "Here is a post".
        """
        
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        if "429" in str(e) or "ResourceExhausted" in str(e):
            st.error("🚀 API Quota reached (Rate Limit). Please wait 60 seconds and try again.")
        return f"Error generating post: {e}"

def refine_post_with_ai(current_text, instructions):
    """Refine the generated post using AI based on user instructions."""
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Refine this LinkedIn post based on the following instructions:
    
    Current Post:
    {current_text}
    
    Instructions:
    {instructions}
    
    Rules:
    - Maintain a professional and engaging LinkedIn tone.
    - Return ONLY the updated post text.
    - Do not include any explanations, intros, or conversational filler.
    - Preserve the overall structure (Hook, Rehook, Body, Question, CTA, Hashtags).
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Refinement failed: {e}")
        return current_text

def upload_image_to_linkedin(image_bytes, mime_type="image/jpeg"):
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    register_data = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": LINKEDIN_AUTHOR_URN,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    
    reg_resp = requests.post(register_url, headers=headers, json=register_data)
    if reg_resp.status_code != 200:
        st.error(f"Image Register Failed: {reg_resp.text}")
        return None
        
    upload_data = reg_resp.json()
    upload_url = upload_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
    asset_urn = upload_data['value']['asset']
    
    upload_resp = requests.put(upload_url, data=image_bytes, headers={'Content-Type': 'application/octet-stream'})
    
    if upload_resp.status_code not in [200, 201]:
        st.error(f"Image Upload Failed: {upload_resp.status_code}")
        return None
        
    return asset_urn

def post_to_linkedin_api(text, asset_urn=None):
    api_url = 'https://api.linkedin.com/v2/ugcPosts'
    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    
    share_media_category = "NONE"
    media_list = []
    
    if asset_urn:
        share_media_category = "IMAGE"
        media_list = [{"status": "READY", "media": asset_urn, "title": {"text": "Image"}}]

    specific_content = {
        "com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": text},
            "shareMediaCategory": share_media_category
        }
    }
    
    if media_list:
        specific_content["com.linkedin.ugc.ShareContent"]["media"] = media_list
        
    post_data = {
        "author": LINKEDIN_AUTHOR_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": specific_content,
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    
    resp = requests.post(api_url, headers=headers, json=post_data)
    return resp.status_code == 201

# --- QUIZ FUNCTIONS ---

def generate_quiz_question(category):
    """Generate a quiz question with 4 options using Gemini."""
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = f"""
    Create a challenging but fair multiple-choice quiz question for {category}.
    
    Requirements:
    - The question should test practical knowledge
    - Include code snippet if relevant (for Python/coding topics)
    - Provide exactly 4 options (A, B, C, D)
    - One correct answer, three plausible wrong answers
    
    Return ONLY valid JSON in this exact format:
    {{
        "question": "What is the output of this code?",
        "code": "print(len([1,2,3]))",
        "options": ["A) 1", "B) 2", "C) 3", "D) Error"],
        "answer": "C"
    }}
    
    If no code is needed, set "code" to empty string.
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean up markdown if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except Exception as e:
        st.error(f"Quiz generation error: {e}")
        return None

def create_quiz_image(quiz_data, category):
    """Create a styled quiz image using Gemini with reference template."""
    import os
    
    # Build the quiz content for the prompt
    question = quiz_data.get('question', 'Test your knowledge')
    code = quiz_data.get('code', '')
    options = quiz_data.get('options', ['A) Option 1', 'B) Option 2', 'C) Option 3', 'D) Option 4'])
    
    # Format code block text
    code_text = code if code else "(No code snippet for this question)"
    options_text = "\n".join(options)
    
    prompt = f"""
    Create a quiz challenge image in EXACTLY the same style and format as the reference image I'm providing.
    
    Keep the same:
    - Dark background color
    - Title style at the top with "{category} Challenge"
    - Code box layout with dark background
    - Answer options A, B, C, D with colored labels on the left
    - Same font styles and colors
    - Same overall layout and spacing
    
    But change the content to:
    - Title: "{category} Challenge"
    - Question: {question}
    - Code block content: {code_text}
    - Options:
    {options_text}
    
    Keep the professional tech quiz aesthetic. Generate only the image, no text response.
    """
    
    try:
        from google import genai
        from google.genai import types
        
        # Get the template image path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "quiz_template.png")
        
        # Load the reference image
        template_image = Image.open(template_path)
        
        # Create client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Generate image using the template as reference
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, template_image],
        )
        
        # Extract the generated image
        for part in response.parts:
            if part.inline_data is not None:
                generated_image = part.as_image()
                # Convert to bytes
                img_byte_arr = io.BytesIO()
                generated_image.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue(), generated_image
        
        raise Exception("No image in response")
            
    except Exception as e:
        st.warning(f"Gemini image generation failed ({e}). Using Pillow fallback...")
        return create_quiz_image_pillow(quiz_data, category)

def create_quiz_image_pillow(quiz_data, category):
    """Create a styled quiz image using Pillow with proper text handling."""
    import textwrap
    
    width = 1000  # Wider for longer code lines
    
    # Colors
    bg_color = (26, 26, 46)
    title_color = (255, 193, 7)
    text_color = (255, 255, 255)
    code_bg = (40, 42, 54)
    option_colors = [(255, 87, 87), (87, 255, 87), (87, 180, 255), (255, 255, 87)]
    
    # Load fonts - smaller for fitting more content
    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        question_font = ImageFont.truetype("arial.ttf", 18)
        code_font = ImageFont.truetype("consola.ttf", 14)
        option_font = ImageFont.truetype("arial.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        question_font = ImageFont.load_default()
        code_font = ImageFont.load_default()
        option_font = ImageFont.load_default()
    
    # Get content
    question = quiz_data.get('question', 'Question not found')
    code = quiz_data.get('code', '')
    options = quiz_data.get('options', ['A) Option 1', 'B) Option 2', 'C) Option 3', 'D) Option 4'])
    
    # Process text
    question_lines = textwrap.wrap(question, width=80)
    code_lines = code.split('\n')[:20] if code else []  # Support up to 20 lines
    
    # Calculate dynamic height
    height = 80  # Title + padding
    height += len(question_lines) * 24 + 15  # Question
    if code_lines:
        height += len(code_lines) * 18 + 40  # Code block
    height += len(options) * 45 + 30  # Options (smaller spacing)
    height = max(height, 400)
    
    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    y_pos = 25
    
    # Draw title
    title = f"{category} Challenge"
    draw.text((30, y_pos), title, fill=title_color, font=title_font)
    y_pos += 40
    
    # Draw question (wrapped)
    for line in question_lines:
        draw.text((30, y_pos), line, fill=text_color, font=question_font)
        y_pos += 22
    y_pos += 10
    
    # Draw code block if exists
    if code_lines:
        code_height = len(code_lines) * 18 + 25
        code_rect = [25, y_pos, width - 25, y_pos + code_height]
        draw.rounded_rectangle(code_rect, radius=8, fill=code_bg)
        
        for i, line in enumerate(code_lines):
            draw.text((40, y_pos + 12 + i * 18), line[:90], fill=(139, 233, 253), font=code_font)
        y_pos += code_height + 15
    
    # Draw options - single line each, truncated if too long
    for i, opt in enumerate(options):
        color = option_colors[i % 4]
        y = y_pos + i * 42
        
        # Draw colored circle with letter
        circle_x, circle_y = 30, y
        circle_size = 30
        draw.ellipse([circle_x, circle_y, circle_x + circle_size, circle_y + circle_size], fill=color)
        
        letter = chr(65 + i)
        # Center text in circle using anchor='mm'
        draw.text((circle_x + circle_size/2, circle_y + circle_size/2), letter, fill=(0, 0, 0), font=option_font, anchor="mm")
        
        # Get option text (remove prefix if present)
        opt_text = opt[3:] if len(opt) > 2 and opt[1] == ')' else opt
        
        # Truncate long options with ellipsis
        max_chars = 85
        if len(opt_text) > max_chars:
            opt_text = opt_text[:max_chars-3] + "..."
        
        draw.text((circle_x + circle_size + 15, circle_y + 5), opt_text, fill=text_color, font=option_font)
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue(), img

def show_post_preview(image=None, image_bytes=None):
    """Display a LinkedIn-style preview of the post.
    Edits are automatically saved to st.session_state['generated_post']
    """
    if 'generated_post' not in st.session_state:
        return

    st.markdown("---")
    st.markdown("### 📱 Post Preview")
    
    # Initialize versioning for the editor if it doesn't exist
    if 'editor_version' not in st.session_state:
        st.session_state['editor_version'] = 0
    
    # Create a container that looks like LinkedIn
    with st.container():
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("👤 **You**")
        with col2:
            st.caption("Just now · 🌐")
        
        # Show image if exists
        if image_bytes is not None:
            st.image(image_bytes, use_container_width=True)
        elif image is not None:
            st.image(image, use_container_width=True)
        
        # Show post text - Capture manual edits
        st.markdown(f"**📝 Edit your post text:**")
        # Use a versioned key to force a widget reset when AI updates the text
        editor_key = f"post_editor_v{st.session_state['editor_version']}"
        edited_text = st.text_area(
            "Post Content", 
            value=st.session_state['generated_post'], 
            height=350, 
            key=editor_key,
            label_visibility="collapsed"
        )
        # Update main state with whatever is in the current editor
        st.session_state['generated_post'] = edited_text
        
        # Fake engagement bar
        st.markdown("👍 💬 🔄 📤")
    
    # AI Refinement Section
    st.markdown("### ✨ AI Refinement")
    with st.expander("🪄 Ask AI to rewrite or adjust this post", expanded=False):
        refine_col1, refine_col2 = st.columns([4, 1])
        with refine_col1:
            instructions = st.text_input(
                "Comment/Instruction for AI", 
                placeholder="e.g. 'Make it more professional', 'Add 3 more emojis', 'Translate to French'",
                key="ai_refine_input"
            )
        with refine_col2:
            st.write("") # Padding
            if st.button("Change", type="primary", use_container_width=True):
                if instructions:
                    with st.spinner("AI is rewriting your post..."):
                        current_text = st.session_state.get('generated_post', "")
                        refined_text = refine_post_with_ai(current_text, instructions)
                        
                        # Update the post content
                        st.session_state['generated_post'] = refined_text
                        # Bump the version to force the text_area widget to refresh
                        st.session_state['editor_version'] += 1
                        st.rerun()
                else:
                    st.warning("Please enter an instruction first.")

    st.markdown("---")

# --- MAIN APP ---

st.title("🤖 LinkedIn Genius")
st.markdown("### Your Autonomous AI Content Manager")

# Sidebar
option = st.sidebar.radio("Select Mode", (
    "🚀 Auto Trend Hunter", 
    "🔍 Manual Topic Scout",
    "👁️ Visual Storyteller", 
    "✨ Creative Remix",
    "🧠 Quiz Challenge"
))

if option == "🚀 Auto Trend Hunter":
    st.header("Mode 1: Trend Hunter")
    st.info("Finds a trending tech topic, reads news, and writes a text-only post.")
    
    if st.button("Find Trend & Generate"):
        with st.status("Hunting for trends..."):
            topic = get_trending_tech_topic()
            st.write(f"Topic: **{topic}**")
            
            article = fetch_article_content(topic)
            if not article:
                st.warning("No new/unprocessed articles found for this topic. Try another search or wait for news to update.")
            else:
                st.write(f"Article: {article['title']}")
                
                post = generate_post_text(article, type="article")
                st.session_state['generated_post'] = post
                st.session_state['post_type'] = 'text'
                st.session_state['article_url'] = article['url']
    
    if 'generated_post' in st.session_state and st.session_state.get('post_type') == 'text':
        # Ensure it's a string if we are using it as a key for text_area
        st.session_state['generated_post'] = str(st.session_state['generated_post'])
        show_post_preview()
        
        if st.button("🚀 Publish to LinkedIn"):
            if post_to_linkedin_api(st.session_state['generated_post']):
                # Save to history ONLY on successful publish
                if st.session_state.get('article_url'):
                    add_url_to_sheet(st.session_state['article_url'])
                
                st.success("Published Successfully!")
                del st.session_state['generated_post']
            else:
                st.error("Failed to publish.")

elif option == "🔍 Manual Topic Scout":
    st.header("Mode 5: Manual Topic Scout")
    st.info("Insert a subject to find related news and generate a post.")
    
    manual_topic = st.text_input("Enter Search Subject (e.g., 'Google DeepMind', 'Solar Energy'):")
    
    if st.button("Search & Generate"):
        if manual_topic:
            with st.status(f"Searching for '{manual_topic}'..."):
                article = fetch_article_content(manual_topic)
                if not article:
                    st.warning("No new/unprocessed articles found for this topic. Try another search or wait for news to update.")
                else:
                    st.write(f"Article: {article['title']}")
                    
                    post = generate_post_text(article, type="article")
                    st.session_state['generated_post'] = post
                    st.session_state['post_type'] = 'manual'
                    st.session_state['article_url'] = article['url']
        else:
            st.error("Please enter a subject first.")
    
    if 'generated_post' in st.session_state and st.session_state.get('post_type') == 'manual':
        st.session_state['generated_post'] = str(st.session_state['generated_post'])
        show_post_preview()
        
        if st.button("🚀 Publish to LinkedIn"):
            if post_to_linkedin_api(st.session_state['generated_post']):
                # Save to history ONLY on successful publish
                if st.session_state.get('article_url'):
                    add_url_to_sheet(st.session_state['article_url'])
                
                st.success("Published Successfully!")
                del st.session_state['generated_post']
            else:
                st.error("Failed to publish.")

elif option == "👁️ Visual Storyteller":
    st.header("Mode 2: Visual Storyteller")
    st.info("Upload an image. AI analyzes it and writes a post.")
    
    uploaded_file = st.file_uploader("Upload Image", type=['jpg', 'png', 'jpeg', 'JFIF', 'GIF'])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        
        if st.button("Analyze & Write"):
            with st.spinner("Analyzing image..."):
                model = genai.GenerativeModel("gemini-2.5-flash")
                response = model.generate_content(["Describe this image in detail for a professional audience.", image])
                description = response.text
                
                post = generate_post_text(description, type="image")
                
                st.session_state['generated_post'] = post
                st.session_state['post_type'] = 'image'
                # Use raw bytes for LinkedIn upload to preserve animations (GIFs)
                st.session_state['image_data'] = uploaded_file.getvalue()
                # Store for preview
                st.session_state['preview_image_bytes'] = uploaded_file.getvalue()

    if 'generated_post' in st.session_state and st.session_state.get('post_type') == 'image':
        st.session_state['generated_post'] = str(st.session_state['generated_post'])
        show_post_preview(image_bytes=st.session_state.get('preview_image_bytes'))
        
        if st.button("🚀 Publish (Image + Text)"):
            with st.spinner("Uploading..."):
                asset_urn = upload_image_to_linkedin(st.session_state['image_data'])
                if asset_urn:
                    if post_to_linkedin_api(st.session_state['generated_post'], asset_urn=asset_urn):
                        st.success("Published Successfully!")
                        del st.session_state['generated_post']
                    else:
                        st.error("Post creation failed.")

elif option == "✨ Creative Remix":
    st.header("Mode 3: Creative Remix")
    st.info("Upload an image. AI analyzes and writes a creative post about it.")
    
    uploaded_file = st.file_uploader("Upload Source Image", type=['jpg', 'png', 'jpeg', 'JFIF', 'GIF'])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Source Image', width=300)
        
        if st.button("Remix & Generate"):
            with st.spinner("Analyzing and creating post..."):
                vision_model = genai.GenerativeModel("gemini-2.5-flash")
                desc_response = vision_model.generate_content(["Describe the visual composition, subject, and mood of this image.", image])
                prompt_description = desc_response.text
                
                post = generate_post_text(prompt_description, type="image")
                st.session_state['generated_post'] = post
                st.session_state['post_type'] = 'remix'
                # Use raw bytes for LinkedIn upload
                st.session_state['image_data'] = uploaded_file.getvalue()
                # Store for preview
                st.session_state['preview_image_bytes'] = uploaded_file.getvalue()

    if 'generated_post' in st.session_state and st.session_state.get('post_type') == 'remix':
        st.session_state['generated_post'] = str(st.session_state['generated_post'])
        show_post_preview(image_bytes=st.session_state.get('preview_image_bytes'))
        
        if st.button("🚀 Publish Remix"):
            asset_urn = upload_image_to_linkedin(st.session_state['image_data'])
            if asset_urn:
                if post_to_linkedin_api(st.session_state['generated_post'], asset_urn=asset_urn):
                    st.success("Published Successfully!")
                    del st.session_state['generated_post']

elif option == "🧠 Quiz Challenge":
    st.header("Mode 4: Quiz Challenge")
    st.info("Generate engaging quiz images to challenge your followers!")
    
    # Category selection
    category = st.selectbox(
        "Choose Quiz Category:",
        ["Python", "Artificial Intelligence", "Machine Learning", "Data Science", "Data Engineering"]
    )
    
    if st.button("🎲 Generate Quiz"):
        with st.spinner(f"Creating {category} quiz..."):
            quiz_data = generate_quiz_question(category)
            
            if quiz_data:
                quiz_data['category'] = category
                st.session_state['quiz_data'] = quiz_data
                
                # Create quiz image
                image_bytes, pil_image = create_quiz_image(quiz_data, category)
                st.session_state['quiz_image'] = pil_image
                st.session_state['quiz_image_bytes'] = image_bytes
                
                # Generate post text
                post = generate_post_text(None, type="quiz", quiz_data=quiz_data)
                st.session_state['generated_post'] = post
                st.session_state['post_type'] = 'quiz'
    
    if 'generated_post' in st.session_state and st.session_state.get('post_type') == 'quiz':
        st.session_state['generated_post'] = str(st.session_state['generated_post'])
        show_post_preview(image=st.session_state.get('quiz_image'))
        
        if st.button("🚀 Publish Quiz"):
            with st.spinner("Publishing..."):
                asset_urn = upload_image_to_linkedin(st.session_state['quiz_image_bytes'])
                if asset_urn:
                    if post_to_linkedin_api(st.session_state['generated_post'], asset_urn=asset_urn):
                        st.success("Quiz Published Successfully!")
                        del st.session_state['generated_post']
                        del st.session_state['quiz_data']
                    else:
                        st.error("Post creation failed.")
