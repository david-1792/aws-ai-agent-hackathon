import streamlit as st
from streamlit_js_eval import get_geolocation

from geopy.geocoders import Nominatim
from tzfpy import get_tz
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
    with st.sidebar:
        st.image('app/static/logo.png', width='stretch')
        st.markdown(
            '<h1 style="text-align: center; font-size: 1.5rem; margin-bottom: 0.5rem;">Welcome to Sana! 👋</h1>',
            unsafe_allow_html=True,
        )
        st.markdown('---')

        st.subheader('⚙️ **Settings**')

        allow_location = st.checkbox('📍 Allow location access')

        if allow_location:
            if (geolocation := get_geolocation()):
                lat: float = geolocation['coords']['latitude']
                lng: float = geolocation['coords']['longitude']

                if (timezone := get_tz(lat=lat, lng=lng)):
                    st.session_state['timezone'] = timezone

                if (location := geolocator.reverse(f'{lat}, {lng}')):
                    address: dict = location.raw.get('address', {})
                    if (country := address.get('country_code')) == 'us':
                        st.info(f'Using location of {address.get("city", "your city")}, {address.get("state", "")} for location-based services.')
                        st.session_state['country'] = country.upper()
                        st.session_state['zip_code'] = address.get('postcode', '90011')
                    else:
                        st.warning('Your location is outside the US. We will use a default location of Los Angeles for location-based services.')
                        st.session_state['country'] = 'US'
                        st.session_state['zip_code'] = '90011'
                        st.session_state['timezone'] = 'America/Los_Angeles'
        else:
            st.info('Location access is disabled. Using default location of Los Angeles for location-based services.')

        st.markdown('<br><br>', unsafe_allow_html=True)
        st.markdown('---')
        if st.button('🚪 Logout', use_container_width=True, type='secondary'):
            auth.logout()

    tokens: dict = auth.get_tokens()
    claims: dict = auth.get_user_claims()

    chat.display_conversation()

    disable_input: bool = st.session_state.get('pending_assistant', False)
    if prompt := st.chat_input('What are you feeling?', disabled=disable_input):
        chat.process_user_message(prompt, claims, tokens)

def render_login_interface(auth: SanaAuth) -> None:
    login_url: str = auth.get_login_url()
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={login_url}">',
        unsafe_allow_html=True,
    )

if __name__ == '__main__':
    main()