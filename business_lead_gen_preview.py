import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import google.generativeai as genai
from google.api_core import exceptions
import random
import os

# Configure Gemini
GEMINI_API_KEY = 'AIzaSyDQ24d5VEcRcX1sFWF3rBzJECAQ_cl5m1E'
genai.configure(api_key=GEMINI_API_KEY)

def create_search_query(profession):
    """Create a search query for LinkedIn profiles"""
    email_domains = ['@gmail.com', '@yahoo.com', '@outlook.com', '@hotmail.com', '@aol.com', '@icloud.com']
    domain = random.choice(email_domains)
    return f'site:linkedin.com {profession} email{domain}'

def search_linkedin_profiles(profession, num_pages=1):
    """Search for LinkedIn profiles using Google"""
    profiles = []
    base_url = 'https://www.google.com/search'
    
    for page in range(num_pages):
        try:
            # Add random delay between requests
            time.sleep(random.uniform(2, 5))
            
            params = {
                'q': create_search_query(profession),
                'start': page * 10
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            search_results = soup.find_all('div', class_='g')
            
            for result in search_results:
                title_element = result.find('h3')
                link_element = result.find('a')
                snippet_element = result.find('div', class_='VwiC3b')
                
                if title_element and link_element and 'linkedin.com/in/' in link_element['href']:
                    profile_info = {
                        'title': title_element.text,
                        'url': link_element['href'],
                        'snippet': snippet_element.text if snippet_element else ''
                    }
                    profiles.append(profile_info)
                    
            print(f"Processed page {page + 1}, found {len(profiles)} profiles so far")
            
        except Exception as e:
            print(f"Error on page {page + 1}: {str(e)}")
            time.sleep(random.uniform(5, 10))  # Longer delay on error
            continue
    
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
        'Profession': profession
    }
    
    try:
        lines = response_text.strip().split('\n')
        current_key = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for known fields
            for key in info.keys():
                if line.startswith(f"{key}:"):
                    current_key = key
                    value = line.split(':', 1)[1].strip()
                    value = value.strip('[]')  # Remove instruction brackets if present
                    info[key] = value
                    break
                    
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
        
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

def save_to_csv(profiles_info, profession):
    """Save profile information to CSV file"""
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

def craft_email_content(profession, recipient_name, company_name):
    """Use Gemini to craft a personalized email based on profession"""
    prompt = f"""
    Craft a professional, personalized email for a {profession}. 
    Context:
    - Recipient Name: {recipient_name if recipient_name else '[Name]'}
    - Company: {company_name if company_name else 'your company'}
    - Profession: {profession}
    
    Requirements:
    1. Keep it brief (3-4 short paragraphs)
    2. Be professional but friendly
    3. Focus on value proposition
    4. Include a clear call to action
    5. Don't be pushy or salesy
    6. Make it specific to their profession
    7. Don't mention AI or automated emails
    
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

def preview_emails(csv_file):
    """Preview all emails that would be sent"""
    try:
        df = pd.read_csv(csv_file)
        profession = df['Profession'].iloc[0] if not df.empty else None
        
        if not profession:
            print("No profession found in CSV!")
            return
            
        print(f"\nPreviewing emails for {profession}...")
        
        # Create a directory for email previews
        preview_dir = 'email_previews'
        os.makedirs(preview_dir, exist_ok=True)
        
        # Create a preview file
        preview_file = os.path.join(preview_dir, f'{profession.lower().replace(" ", "_")}_email_previews.txt')
        total = 0
        
        with open(preview_file, 'w', encoding='utf-8') as f:
            f.write(f"Email Previews for {profession}\n")
            f.write("=" * 50 + "\n\n")
            
            for _, row in df.iterrows():
                email = row['Email']
                if not pd.isna(email) and email.strip():
                    total += 1
                    print(f"\nCrafting preview for: {email}")
                    
                    # Craft personalized email
                    subject, body = craft_email_content(
                        profession=profession,
                        recipient_name=row['Full Name'] if not pd.isna(row['Full Name']) else None,
                        company_name=row['Company Name'] if not pd.isna(row['Company Name']) else None
                    )
                    
                    if subject and body:
                        f.write(f"Email {total}:\n")
                        f.write(f"To: {email}\n")
                        f.write(f"Subject: {subject}\n")
                        f.write("-" * 30 + "\n")
                        f.write(body)
                        f.write("\n" + "=" * 50 + "\n\n")
                    else:
                        print(f"Could not craft email for {email}")
        
        print(f"\nEmail Preview Summary for {profession}:")
        print(f"Total Previews Generated: {total}")
        print(f"Preview file saved to: {preview_file}")
        
        # Open the preview file
        os.startfile(preview_file)
        
    except Exception as e:
        print(f"Error generating previews: {str(e)}")

def main():
    try:
        profession = input("Enter the profession to search for (e.g., 'life coach'): ")
        num_pages = int(input("Enter number of search pages to process (1-20): "))
        
        if not profession or num_pages < 1:
            print("Invalid input!")
            return
            
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
            if any(value.strip() for value in info.values()):  # Only add if we got some non-empty information
                profiles_info.append(info)
                print(f"Added profile {i} to results")
                
        if profiles_info:
            save_to_csv(profiles_info, profession)
            
            # Ask if user wants to preview emails
            preview_emails_choice = input("\nWould you like to preview the emails that would be sent? (y/n): ").lower()
            if preview_emails_choice == 'y':
                csv_file = f"{profession.lower().replace(' ', '_')}_leads.csv"
                if os.path.exists(csv_file):
                    preview_emails(csv_file)
                else:
                    print(f"CSV file not found: {csv_file}")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
