import streamlit as st
from streamlit_js_eval import get_geolocation

from geopy.geocoders import Nominatim
from timezonefinder import timezone_at
from app.auth import SanaAuth
from app.chat import SanaChat

geolocator = Nominatim(user_agent='sana-app')

def main() -> None:
    st.set_page_config(
        page_title='Sana',
        page_icon='🧠',
        layout='wide',
    )

    auth = SanaAuth()
    chat = SanaChat()

    auth.handle_oauth_callback()

    if auth.is_authenticated():
        render_main_interface(auth, chat)
    else:
        render_login_interface(auth)

def render_main_interface(auth: SanaAuth, chat: SanaChat) -> None:
    st.sidebar.title('🧠🩺 Sana')

    if st.sidebar.button('Logout'):
        auth.logout()

    tokens: dict = auth.get_tokens()
    claims: dict = auth.get_user_claims()

    chat.display_conversation()

    if st.sidebar.checkbox('📍 Use my location'):
        if (geolocation := get_geolocation()):
            lat: float = geolocation['coords']['latitude']
            lng: float = geolocation['coords']['longitude']

            if (timezone := timezone_at(lat=lat, lng=lng)):
                st.session_state['timezone'] = timezone

            if (location := geolocator.reverse(f'{lat}, {lng}')):
                address: dict = location.raw.get('address', {})
                if (country := address.get('country_code')) == 'us':
                    st.session_state['country'] = country.upper()
                    st.session_state['zip_code'] = address.get('postcode', '10001')
                else:
                    st.sidebar.warning('Your location is outside the US. We will use a default location of New York for location-based services.')
                    st.session_state['country'] = 'US'
                    st.session_state['zip_code'] = '10001'
    
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