from requests_oauthlib import OAuth2Session
import webbrowser
import os

# Disable scope change errors
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Client keys
CLIENT_ID = '78pz3yi7wreoza'
CLIENT_SECRET = 'WPL_AP1.TNKBz3giqsCwTbT6.TXgD+w=='
REDIRECT_URI = 'https://www.linkedin.com/in/ibrahim-lakhzine-9739a112b/'

# Authorization URL
AUTHORIZATION_BASE_URL = 'https://www.linkedin.com/oauth/v2/authorization'
TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'

def main():
    # Define scopes including the new ones
    scope = ['openid', 'profile', 'w_member_social', 'email']
    
    linkedin = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=scope)
    
    # 1. User authorization
    authorization_url, state = linkedin.authorization_url(AUTHORIZATION_BASE_URL)
    
    print("Please go here and authorize:", authorization_url)
    
    # Open the browser for the user
    webbrowser.open(authorization_url)
    
    # 2. Get the authorization verifier code from the callback url
    print(f"\nYou will be redirected to {REDIRECT_URI}")
    print("Copy the 'code' parameter from the URL bar after redirection.")
    print("It will look like: ...?code=AQX...&state=...")
    redirect_response = input('Paste the full redirect URL or just the code here: ')
    
    # Extract code if full URL is pasted
    if 'code=' in redirect_response:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(redirect_response)
        code = parse_qs(parsed.query).get('code', [''])[0] or redirect_response.split('code=')[-1].split('&')[0]
    else:
        code = redirect_response

    # 3. Fetch the access token
    try:
        token = linkedin.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code, include_client_id=True)
        print("\nSUCCESS! Here is your new Access Token:")
        print("-" * 60)
        print(token['access_token'])
        print("-" * 60)
        print("\nUpdate your linkedin_bot.py with this new token.")
    except Exception as e:
        print(f"\nError fetching token: {e}")

if __name__ == '__main__':
    main()
