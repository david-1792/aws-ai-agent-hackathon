import sys

import streamlit as st
from streamlit_js_eval import get_geolocation

from geopy.geocoders import Nominatim

from app.auth import SanaAuth
from app.chat import SanaChat
from app.styles import apply_styles
from utils.aws import get_ssm_parameter

geolocator = Nominatim(user_agent='sana-app')

def main() -> None:
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == '--local':
                st.session_state['agent_url'] = 'http://localhost:8080/invocations'

    if 'agent_url' not in st.session_state:
        st.session_state['agent_url'] = get_ssm_parameter('/sana/agent/url')

    st.set_page_config(
        page_title='Sana',
        page_icon='🧠',
        layout='wide',
    )

    apply_styles()

    auth = SanaAuth()
    chat = SanaChat()

    auth.handle_oauth_callback()

    if auth.is_authenticated():
        render_main_interface(auth, chat)
    else:
        render_login_interface(auth)

def render_main_interface(auth: SanaAuth, chat: SanaChat) -> None:
    st.title('🧠🩺 Sana')

    if st.sidebar.button('Logout'):
        auth.logout()

    tokens: dict = auth.get_tokens()
    claims: dict = auth.get_user_claims()

    chat.display_conversation()

    if st.sidebar.checkbox('📍 Use my location'):
        if (geolocation := get_geolocation()):
            location = geolocator.reverse(f'{geolocation['coords']['latitude']}, {geolocation['coords']['longitude']}')
            address: dict = location.raw.get('address')

            if address.get('country_code') == 'mx':
                st.session_state['city'] = address.get('city')
    
    if prompt := st.chat_input('What are you feeling?'):
        chat.process_user_message(prompt, claims, tokens)

def render_login_interface(auth: SanaAuth) -> None:
    login_url: str = auth.get_login_url()
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={login_url}">',
        unsafe_allow_html=True,
    )

if __name__ == '__main__':
    main()