import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import shutil
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import time
from urllib.parse import quote
import json
import re
from google.api_core import exceptions
import random
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=GEMINI_API_KEY)

def create_search_query(profession):
    email_domains = ['@gmail.com', '@yahoo.com', '@outlook.com', '@hotmail.com', '@aol.com', '@icloud.com']
    email_query = ' OR '.join([f'"{domain}"' for domain in email_domains])
    query = f'site:linkedin.com "{profession}" ({email_query})'
    print(query)
    return query

def search_linkedin_profiles(query, num_pages=1):
    profiles = []
    print(f"\nSearching for profiles with query: {query}")

    # Setup Selenium Chrome in headless mode (minimal options)
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(options=options)

    for page in range(num_pages):
        first = page + 1  # Bing uses multiples of 10 for pagination
        search_url = f'https://www.bing.com/search?q={quote(query)}&first={first}'
        print(search_url)
        print(f"\nProcessing page {page + 1}/{num_pages}")

        try:
            driver.get(search_url)
            time.sleep(random.uniform(3, 6))  # Let page load
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # Collect all div texts
            all_divs = soup.find_all('div')
            print(f"Found {len(all_divs)} divs on page {page + 1}")
            combined_text = "\n".join(div.get_text(separator=" ", strip=True) for div in all_divs)
            print(combined_text)
            # Feed combined_text to Gemini for extraction
            prompt = f"""
            Extract LinkedIn profile information from the following text. For each profile, provide:
            - Full Name
            - Company Name
            - Website URL
            - Email
            - Phone Number

            Text:
            {combined_text}
            """

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            print("LLM response:")
            print(response.text)
            # Optionally, you can parse response.text and append to profiles if needed

            delay = random.uniform(10, 30)
            print(f"Waiting {delay:.1f} seconds before next request...")
            time.sleep(delay)
        except Exception as e:
            print(f"Error searching page {page + 1}: {str(e)}")

    driver.quit()
    print(f"\nTotal profiles found: {len(profiles)}")
    return profiles

def parse_gemini_response(response_text, profession):
    """Parse the Gemini response into a structured dictionary"""
    info = {
        'Full Name': '',
        'Company Name': '',
        'Website URL': '',
        'Email': '',
        'Phone Number': '',
        'Profession': profession  # Add profession to each record
    }
    
    try:
        # Try to find structured data patterns
        name_match = re.search(r'Full[Nn]ame:?\s*([^\n]+)', response_text)
        company_match = re.search(r'Company[Nn]ame:?\s*([^\n]+)', response_text)
        website_match = re.search(r'Website URL:?\s*(https?://[^\s\n]+)', response_text)
        email_match = re.search(r'Email:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', response_text)
        phone_match = re.search(r'Phone:?\s*([\+\d\-\(\)\s]+)', response_text)
        
        if name_match: info['Full Name'] = name_match.group(1).strip()
        if company_match: info['Company Name'] = company_match.group(1).strip()
        if website_match: info['Website URL'] = website_match.group(1).strip()
        if email_match: info['Email'] = email_match.group(1).strip()
        if phone_match: info['Phone Number'] = phone_match.group(1).strip()
        
        print("Extracted information:")
        for key, value in info.items():
            print(f"{key}: {value}")
            
    except Exception as e:
        print(f"Error parsing Gemini response: {str(e)}")
    
    return info

def is_valid_profile(info):
    """Check if the profile has enough valid information to be worth saving"""
    # Check if at least one of these important fields has data
    important_fields = ['Full Name', 'Email', 'Website URL']
    return any(info.get(field, '').strip() for field in important_fields)

def is_duplicate(profile, existing_df):
    """Check if a profile is a duplicate based on multiple criteria"""
    if existing_df.empty:
        return False
        
    for _, row in existing_df.iterrows():
        # Check Website URL match (if both have URLs)
        if profile['Website URL'] and row['Website URL'] and profile['Website URL'] == row['Website URL']:
            return True
            
        # Check Email match (if both have emails)
        if profile['Email'] and row['Email'] and profile['Email'].lower() == row['Email'].lower():
            return True
            
        # Check Full Name match (if both have names)
        if profile['Full Name'] and row['Full Name'] and profile['Full Name'].lower() == row['Full Name'].lower():
            return True
            
        # Check URL in Website URL field (to catch LinkedIn profile URLs)
        if profile.get('LinkedIn URL') and row['Website URL'] and profile['LinkedIn URL'] in row['Website URL']:
            return True
            
    return False

def save_to_csv(profiles_info, profession):
    try:
        if not profiles_info:
            print("No data to save!")
            return
            
        # Create filename from profession
        output_file = f"{profession.lower().replace(' ', '_')}_leads.csv"
        print(f"\nProcessing {len(profiles_info)} profiles for {profession}")
        
        # Filter out invalid profiles
        valid_profiles = [p for p in profiles_info if is_valid_profile(p)]
        if not valid_profiles:
            print("No valid profiles to save after filtering!")
            return
            
        print(f"Found {len(valid_profiles)} valid profiles")
        
        # Create DataFrame from new data
        new_df = pd.DataFrame(valid_profiles)
        
        # Reorder columns to match desired format
        columns = ['Full Name', 'Company Name', 'Website URL', 'Email', 'Phone Number', 'Profession']
        for col in columns:
            if col not in new_df.columns:
                new_df[col] = ''
        new_df = new_df[columns]
        
        # Try to load existing data if file exists
        if os.path.exists(output_file):
            print(f"Found existing file for {profession}, checking for duplicates...")
            try:
                existing_df = pd.read_csv(output_file)
                
                # Add missing columns to existing data if any
                for col in columns:
                    if col not in existing_df.columns:
                        existing_df[col] = ''
                
                # Filter out duplicates
                unique_profiles = []
                for _, profile in new_df.iterrows():
                    if not is_duplicate(profile, existing_df):
                        unique_profiles.append(profile)
                
                if not unique_profiles:
                    print("All new profiles are duplicates, no new data to add.")
                    return
                    
                print(f"Found {len(unique_profiles)} unique new profiles")
                
                # Combine with existing data
                unique_df = pd.DataFrame(unique_profiles)
                combined_df = pd.concat([existing_df, unique_df], ignore_index=True)
                
                # Clean the data
                for col in combined_df.columns:
                    combined_df[col] = combined_df[col].fillna('').astype(str).apply(lambda x: x.strip())
                
                # Remove any rows that are completely empty
                combined_df = combined_df.loc[combined_df.apply(lambda x: x.str.strip().str.len() > 0).any(axis=1)]
                
            except Exception as e:
                print(f"Error reading existing file: {str(e)}")
                combined_df = new_df
        else:
            print(f"Creating new file for {profession}...")
            combined_df = new_df
        
        # Save to CSV
        combined_df.to_csv(output_file, index=False, encoding='utf-8')
        
        # Verify the file was created and has data
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"File saved successfully! Size: {file_size} bytes")
            
            # Read back and display first few rows
            saved_df = pd.read_csv(output_file)
            print("\nFirst few rows of saved data:")
            print(saved_df.head())
            print(f"\nTotal records in file: {len(saved_df)}")
        else:
            print("Warning: File was not created!")
            
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        backup_file = f"backup_{int(time.time())}_{profession.lower().replace(' ', '_')}_leads.csv"
        try:
            pd.DataFrame(profiles_info).to_csv(backup_file, index=False, encoding='utf-8')
            print(f"Backup saved to {backup_file}")
        except Exception as e:
            print(f"Error saving backup: {str(e)}")
            with open(f"emergency_backup_{int(time.time())}_{profession.lower().replace(' ', '_')}.json", 'w', encoding='utf-8') as f:
                json.dump(profiles_info, f, ensure_ascii=False, indent=2)

def extract_profile_info(profile_data, profession, retries=3, initial_delay=5):
    """Extract information from profile with retry logic"""
    prompt = f"""
    Extract the following information from this LinkedIn profile text and format it precisely:
    Full Name: [Extract full name]
    Company Name: [Extract company name]
    Website URL: [Extract website if present]
    Email: [Extract email if present]
    Phone: [Extract phone if present]

    Text:
    Title: {profile_data['title']}
    Description: {profile_data['snippet']}
    URL: {profile_data['url']}
    """
    
    delay = initial_delay
    for attempt in range(retries):
        try:
            print(f"\nAttempt {attempt + 1}/{retries} to process profile")
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            print("Got response from Gemini")
            info = parse_gemini_response(response.text, profession)
            # Add LinkedIn URL to help with duplicate detection
            info['LinkedIn URL'] = profile_data['url']
            return info
        except exceptions.ResourceExhausted:
            if attempt < retries - 1:
                print(f"Rate limit hit, waiting {delay} seconds before retry...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print("Max retries reached, skipping this profile")
                return {
                    'Full Name': '',
                    'Company Name': '',
                    'Website URL': '',
                    'Email': '',
                    'Phone Number': '',
                    'Profession': profession,
                    'LinkedIn URL': profile_data['url']
                }
        except Exception as e:
            print(f"Error processing profile: {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                return {
                    'Full Name': '',
                    'Company Name': '',
                    'Website URL': '',
                    'Email': '',
                    'Phone Number': '',
                    'Profession': profession,
                    'LinkedIn URL': profile_data['url']
                }

def is_valid_email(email):
    """Check if email is valid using regex pattern"""
    if not email or pd.isna(email):
        return False
    
    # Regular expression for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Additional checks
    if not re.match(pattern, email):
        return False
    
    # Check for common disposable email domains
    disposable_domains = [
        'tempmail', 'throwaway', 'fake', 'temp-mail', 
        'tempmail', '10minutemail', 'mailinator', 'yopmail'
    ]
    
    domain = email.lower().split('@')[1]
    if any(d in domain for d in disposable_domains):
        return False
        
    return True

def craft_email_content(profession, recipient_name, company_name):
    """Use Gemini to craft a personalized email based on profession"""
    prompt = f"""
    Craft a professional, personalized email for this subject {profession}.

 

    Requirements:

    1. Keep it brief (3-4 short paragraphs)

    2. Be professional but friendly

    3. Focus on value proposition about the services we are offering (Enterprise Content Management

Business Analytics

Information Management and also in DEAR name don't include any name make it generic

SaaS Development

Email Marketing)

    4. Include a clear call to action

    5. Don't be pushy or salesy

    6. Make it specific to their profession

    7. Don't mention AI or automated emails - Professional signature LAKHZINE IBRAHIM for my title AI & ML Engineer | Data Scientist | Software Engineer | AI Optimization Expert | Freelancer don't include Company Name and Contact Information the subject should no contain username or any names It should be precise strat the mail always with Hi There,
    
    Format the email with:
    - Subject line
    - Body
    - Professional signature
    """
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        email_content = response.text.strip()
        
        # Extract subject line and body
        parts = email_content.split('\n', 1)
        if len(parts) >= 2:
            subject = parts[0].replace('Subject:', '').strip()
            body = parts[1].strip()
            return subject, body
        return "Professional Connection", email_content
    except Exception as e:
        print(f"Error crafting email: {str(e)}")
        return None, None

def send_email(to_email, subject, body):
    """Send email using SMTP"""
    try:
        # Get email credentials from environment variables
        sender_email = os.getenv('EMAIL_ADDRESS')
        sender_password = os.getenv('EMAIL_PASSWORD')
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        
        if not all([sender_email, sender_password]):
            print("Email credentials not found in environment variables!")
            return False
            
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to SMTP server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def process_and_send_emails(csv_file):
    """Process CSV file and send personalized emails to each contact"""
    try:
        df = pd.read_csv(csv_file)
        profession = df['Profession'].iloc[0] if not df.empty else None
        
        if not profession:
            print("No profession found in CSV!")
            return
            
        print(f"\nProcessing emails for {profession}...")
        
        # Track statistics
        total = 0
        sent = 0
        failed = 0
        skipped = 0
        invalid_emails = []
        
        for _, row in df.iterrows():
            email = row['Email']
            if not pd.isna(email) and email.strip():
                total += 1
                
                # Validate email
                if not is_valid_email(email):
                    print(f"\nSkipping invalid email: {email}")
                    skipped += 1
                    invalid_emails.append({
                        'email': email,
                        'reason': 'Invalid email format or disposable domain'
                    })
                    continue
                
                print(f"\nProcessing email for: {email}")
                
                # Craft personalized email
                subject, body = craft_email_content(
                    profession=profession,
                    recipient_name=row['Full Name'] if not pd.isna(row['Full Name']) else None,
                    company_name=row['Company Name'] if not pd.isna(row['Company Name']) else None
                )
                
                if subject and body:
                    # Add random delay between emails (1-3 seconds)
                    time.sleep(random.uniform(1, 3))
                    
                    if send_email(email, subject, body):
                        sent += 1
                    else:
                        failed += 1
                else:
                    print(f"Could not craft email for {email}")
                    failed += 1
        
        print(f"\nEmail Campaign Summary for {profession}:")
        print(f"Total Contacts: {total}")
        print(f"Emails Sent: {sent}")
        print(f"Failed: {failed}")
        print(f"Skipped (Invalid): {skipped}")
        
        if invalid_emails:
            print("\nInvalid Emails Skipped:")
            for item in invalid_emails:
                print(f"- {item['email']}: {item['reason']}")
        
        # Save invalid emails to a log file
        if invalid_emails:
            log_file = f"invalid_emails_{profession.lower().replace(' ', '_')}.txt"
            with open(log_file, 'w') as f:
                f.write(f"Invalid Emails Report for {profession}\n")
                f.write("=" * 50 + "\n\n")
                for item in invalid_emails:
                    f.write(f"Email: {item['email']}\n")
                    f.write(f"Reason: {item['reason']}\n")
                    f.write("-" * 30 + "\n")
            print(f"\nDetailed invalid email report saved to: {log_file}")
        
    except Exception as e:
        print(f"Error processing emails: {str(e)}")

def main():
    try:
        profession = input("Enter the profession to search for (e.g., 'life coach'): ")
        num_pages = int(input("Enter number of search pages to process (1-20): "))
        
        if not profession or num_pages < 1:
            print("Invalid input!")
            return
        
        profession=create_search_query(profession)

        print(f"\nSearching for {profession} profiles...")
        profiles = search_linkedin_profiles(profession, num_pages)
        
        if not profiles:
            print("No profiles found!")
            return
            
        total_profiles = len(profiles)
        print(f"\nFound {total_profiles} profiles to process")
        
        profiles_info = []
        
        for i, profile in enumerate(profiles, 1):
            print(f"\nProcessing profile {i}/{total_profiles}: {profile['url']}")
            info = extract_profile_info(profile, profession)
            
            # Validate email if present
            if info.get('Email'):
                if not is_valid_email(info['Email']):
                    print(f"Skipping profile with invalid email: {info['Email']}")
                    continue
            
            if any(value.strip() for value in info.values()):  # Only add if we got some non-empty information
                profiles_info.append(info)
                print(f"Added profile {i} to results")
                
        if profiles_info:
            save_to_csv(profiles_info, profession)
            
            # Ask if user wants to send emails
            send_emails = input("\nWould you like to send personalized emails to the collected contacts? (y/n): ").lower()
            if send_emails == 'y':
                csv_file = f"{profession.lower().replace(' ', '_')}_leads.csv"
                if os.path.exists(csv_file):
                    process_and_send_emails(csv_file)
                else:
                    print(f"CSV file not found: {csv_file}")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()