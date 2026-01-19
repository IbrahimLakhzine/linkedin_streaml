import requests

def get_linkedin_person_id(access_token):
    url = "https://api.linkedin.com/v2/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        'Content-Type': 'application/json',
        "X-Restli-Protocol-Version": "2.0.0"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        person_id = data.get("id")
        print(f"LinkedIn Person ID: {person_id}")
        return person_id
    else:
        print(f"Failed to retrieve person ID: {response.status_code}", response.json())
        return None
# Replace <your_access_token> with your actual LinkedIn access token
access_token = 'AQVfPMrLMJBh6imyIfmqjmCIElKpqG1SR95bEVV1GXf2lTrDZW7k1Z5KFvj-KAkAWnutTazBW6G4yBCpn7XEQWwIYWPEpzR0g0Q2vDLltVrqwZLXiNzkriQMU4g7wKIEjQI9eJmV4Y8521zyw311EX49YK7t8oEn_xPop7s80i4eJ4Hoy6IP5DpFKbLc9DUF51cvBf-VhiIQ7ZmlhwakbcqQw0ZD5KRO67DdN3a56a0sLwhLiThR-tuplgC100B-Y4j_kJvFcVpOVf70MrhTrm8fiHzwtKL7tTjlyzh9vlLNutqLOe8NIWEsCTyfbwoiBMs0I3fsI1kYPJSSFIdeqW4W4STg9A'  # Obtain this through the OAuth flow

get_linkedin_person_id(access_token)