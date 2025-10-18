import base64
import hashlib
import logging
import json
import uuid
import jwt
import os

from urllib.parse import urlencode

import requests
import streamlit as st
from streamlit_cookies_controller import CookieController

from app.config import settings

logger = logging.getLogger(__name__)

class SanaAuth:
    def __init__(self) -> None:
        self.scopes: list[str] = ['openid', 'email']
        self.cookies = CookieController('cookies')

        # Common cookie settings
        is_production = settings.ENVIRONMENT == 'prod'
        self.oauth_cookie_settings = {
            'same_site': 'lax',  # Allow cross-site requests for OAuth
            'path': '/',
            'secure': is_production  # True in production with HTTPS
        }

        self.token_cookie_settings = {
            'same_site': 'strict',  # More secure for tokens
            'path': '/',
            'secure': is_production  # True in production with HTTPS
        }

    def generate_pkce_pair(self) -> tuple[str, str]:
        verifier: str = base64.urlsafe_b64encode(
            os.urandom(40)
        ).decode('utf-8').rstrip('=')

        challenge: str = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        return verifier, challenge

    def get_login_url(self) -> str:
        verifier, challenge = self.generate_pkce_pair()

        # Set cookies for OAuth flow
        oauth_max_age = 600  # 10 minutes for OAuth flow
        self.cookies.set('code_verifier', verifier, max_age=oauth_max_age, **self.oauth_cookie_settings)
        self.cookies.set('code_challenge', challenge, max_age=oauth_max_age, **self.oauth_cookie_settings)

        state: str = str(uuid.uuid4())
        self.cookies.set('oauth_state', state, max_age=oauth_max_age, **self.oauth_cookie_settings)

        params: dict = {
            'response_type': 'code',
            'client_id': settings.AWS_COGNITO_APP_CLIENT_ID,
            'redirect_uri': settings.AWS_COGNITO_REDIRECT_URI,
            'scope': ' '.join(self.scopes),
            'code_challenge_method': 'S256',
            'code_challenge': challenge,
            'state': state
        }

        return f'{settings.AWS_COGNITO_DOMAIN}/oauth2/authorize?{urlencode(params)}'

    def handle_oauth_callback(self) -> None:
        query_params: dict = st.query_params

        # Check if we have OAuth callback parameters
        if not (received_state := query_params.get('state')):
            logger.debug('No state parameter in query params - not an OAuth callback')
            return

        if not (code := query_params.get('code')):
            logger.warning('OAuth callback missing authorization code')
            st.error('Authorization failed: Missing authorization code')
            st.stop()

        # Check if user is already authenticated
        if self.cookies.get('tokens'):
            logger.info('User is already authenticated, clearing query params')
            st.query_params.clear()
            st.rerun()
            return

        # Get stored OAuth state and PKCE verifier from cookies
        code_verifier: str = self.cookies.get('code_verifier')
        stored_state: str = self.cookies.get('oauth_state')

        # Validate state parameter
        if not stored_state:
            logger.error('No state stored in cookies - possible CSRF attack or cookie issues')
            st.error('Authentication failed: No state stored in cookies. Please try logging in again.')
            # Clear potentially invalid cookies
            self.cookies.remove('code_verifier')
            self.cookies.remove('code_challenge')
            self.cookies.remove('oauth_state')
            st.query_params.clear()
            st.stop()

        if received_state != stored_state:
            logger.error(f'State parameter mismatch - stored: {stored_state}, received: {received_state}')
            st.error('Authentication failed: State parameter does not match. Please try logging in again.')
            # Clear potentially invalid cookies
            self.cookies.remove('code_verifier')
            self.cookies.remove('code_challenge')
            self.cookies.remove('oauth_state')
            st.query_params.clear()
            st.stop()

        # Validate PKCE verifier
        if not code_verifier:
            logger.error('No code verifier stored in cookies')
            st.error('Authentication failed: Missing code verifier. Please try logging in again.')
            self.cookies.remove('oauth_state')
            st.query_params.clear()
            st.stop()

        # Exchange authorization code for tokens
        token_url: str = f'{settings.AWS_COGNITO_DOMAIN}/oauth2/token'
        data: dict = {
            'grant_type': 'authorization_code',
            'client_id': settings.AWS_COGNITO_APP_CLIENT_ID,
            'code': code,
            'redirect_uri': settings.AWS_COGNITO_REDIRECT_URI,
            'code_verifier': code_verifier,
        }

        headers: dict = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(token_url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            tokens = response.json()

            # Store tokens with proper expiration
            self.cookies.set('tokens', tokens, max_age=3600, **self.token_cookie_settings)

            # Clean up OAuth flow cookies
            self.cookies.remove('code_verifier')
            self.cookies.remove('code_challenge')
            self.cookies.remove('oauth_state')

            # Clear query parameters and trigger rerun
            st.query_params.clear()
            logger.info('OAuth authentication successful')
            st.rerun()

        except requests.exceptions.RequestException as e:
            logger.error(f'Token exchange request failed: {e}')
            st.error('Authentication failed: Unable to connect to authentication server. Please try again.')
            st.stop()
        except requests.exceptions.HTTPError:
            logger.error(f'Token exchange HTTP error: {response.status_code} - {response.text}')
            st.error(f'Authentication failed: {response.status_code} error from authentication server.')
            st.stop()
        except Exception as e:
            logger.error(f'Unexpected error during token exchange: {e}')
            st.error('Authentication failed: An unexpected error occurred. Please try again.')
            st.stop()

    def is_authenticated(self) -> bool:
        return bool(self.get_tokens())
    
    def get_tokens(self) -> dict | None:
        if not (token_data := self.cookies.get('tokens')):
            return None
        
        if isinstance(token_data, str):
            return json.loads(token_data)
        
        if isinstance(token_data, dict):
            return token_data
        
        return None
    
    def get_user_claims(self) -> dict | None:
        if not (tokens := self.get_tokens()):
            return None
        
        return jwt.decode(
            tokens['id_token'],
            options={'verify_signature': False}
        )
    
    def logout(self) -> None:
        self.cookies.remove('tokens')

        if 'session_id' in st.session_state:
            del st.session_state['session_id']

        if 'messages' in st.session_state:
            del st.session_state['messages']
    
        params: dict = {
            'client_id': settings.AWS_COGNITO_APP_CLIENT_ID,
            'logout_uri': settings.AWS_COGNITO_REDIRECT_URI,
        }

        logout_url: str = f'{settings.AWS_COGNITO_DOMAIN}/logout?{urlencode(params)}'

        st.markdown(
            f'<meta http-equiv="refresh" content="0;url={logout_url}">',
            unsafe_allow_html=True,
        )

        st.rerun()