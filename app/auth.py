import base64
import hashlib
import logging
import json
import uuid
import jwt
import os

from time import sleep

from urllib.parse import urlencode

import requests
import streamlit as st
from streamlit_cookies_manager import CookieManager

from app.config import settings

logger = logging.getLogger(__name__)

COOKIE_SLEEP_TIME: float = 0.5

class SanaAuth:
    def __init__(self) -> None:
        self.scopes: list[str] = ['openid', 'email']
        self.cookies = CookieManager()
        if not self.cookies.ready():
            st.stop()

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
        state: str = str(uuid.uuid4())
        
        self.cookies['code_verifier'] = verifier
        self.cookies['code_challenge'] = challenge
        self.cookies['oauth_state'] = state
        self.cookies.save()
        sleep(COOKIE_SLEEP_TIME)

        params: dict = {
            'response_type': 'code',
            'client_id': settings.AWS_COGNITO_APP_CLIENT_ID,
            'redirect_uri': settings.AWS_COGNITO_REDIRECT_URI,
            'scope': ' '.join(self.scopes),
            'code_challenge_method': 'S256',
            'code_challenge': challenge,
            'state': state
        }

        return f'{settings.AWS_COGNITO_DOMAIN}/login?{urlencode(params)}'

    def handle_oauth_callback(self) -> None:
        if self.cookies.get('tokens'):
            st.query_params.clear()
            return

        query_params: dict = st.query_params.to_dict()
        sleep(2)

        if not (code := query_params.get('code')):
            return

        if not (received_state := query_params.get('state')):
            return
    
        if not (stored_state := self.cookies['oauth_state']):
            st.stop()

        if received_state != stored_state:
            st.stop()

        if not (code_verifier := self.cookies['code_verifier']):
            st.stop()

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

            self.cookies['tokens'] = json.dumps(tokens)
            del self.cookies['code_verifier']
            del self.cookies['code_challenge']
            del self.cookies['oauth_state']
            self.cookies.save()
            sleep(COOKIE_SLEEP_TIME)

            st.query_params.clear()
            st.rerun()
        except requests.exceptions.HTTPError as e:
            print('Error during OAuth callback handling:', e)
            st.stop()
        except Exception as e:
            raise e

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
        del self.cookies['tokens']
        self.cookies.save()
        sleep(COOKIE_SLEEP_TIME)

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