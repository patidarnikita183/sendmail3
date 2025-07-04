import urllib.parse
import requests
from flask import session, redirect, url_for
from .config import Config

def get_auth_url():
    """Generate the authorization URL for Microsoft Graph"""
    params = {
        'client_id': Config.CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': Config.REDIRECT_URI,
        'scope': ' '.join(Config.USER_SCOPES),
        'response_mode': 'query',
        'prompt': 'select_account'
    }
    return f"{Config.AUTHORITY}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)

def get_access_token(auth_code):
    """Exchange authorization code for access token"""
    token_url = f"{Config.AUTHORITY}/oauth2/v2.0/token"
    data = {
        'client_id': Config.CLIENT_ID,
        'client_secret': Config.CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': Config.REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    response = requests.post(token_url, data=data)
    return response.json() if response.status_code == 200 else None

def make_graph_request(endpoint, access_token, method='GET', data=None):
    """Make a request to Microsoft Graph API"""
    url = f"{Config.GRAPH_ENDPOINT}{endpoint}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'POST':
        response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 202]:
        if response.text.strip():
            try:
                return response.json()
            except ValueError:
                return response.text
        return {'success': True, 'status_code': response.status_code}
    return response.text