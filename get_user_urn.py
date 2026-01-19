import requests
import re

def get_token_from_file():
    try:
        with open('linkedin_bot.py', 'r') as f:
            content = f.read()
            match = re.search(r"LINKEDIN_ACCESS_TOKEN = '([^']+)'", content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error reading file: {e}")
    return None

def get_urn(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Try userinfo
    try:
        response = requests.get('https://api.linkedin.com/v2/userinfo', headers=headers)
        if response.status_code == 200:
            return response.json().get('sub')
    except: pass
    
    # Try me
    try:
        response = requests.get('https://api.linkedin.com/v2/me', headers=headers)
        if response.status_code == 200:
            return f"urn:li:person:{response.json().get('id')}"
    except: pass
    
    return None

if __name__ == "__main__":
    token = get_token_from_file()
    if token:
        print(f"Found token: {token[:10]}...")
        urn = get_urn(token)
        if urn:
            print(f"URN_FOUND: {urn}")
        else:
            print("FAILED_TO_FETCH_URN")
    else:
        print("TOKEN_NOT_FOUND_IN_FILE")
