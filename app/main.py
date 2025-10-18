import streamlit as st
from streamlit_js_eval import get_geolocation

from geopy.geocoders import Nominatim
from tzfpy import get_tz

from app.auth import SanaAuth
from app.chat import SanaChat

geolocator = Nominatim(user_agent='sana-app')

def on_welcome_dialog_dismiss() -> None:
    st.session_state['welcome_shown'] = True

@st.dialog(
    title='Welcome to Sana! 👋',
    on_dismiss=on_welcome_dialog_dismiss
)
def welcome_dialog() -> None:
    st.markdown('''
        **Sana** is a mental health screening agent designed to provide access to mental health resources and professional help.
   
        It was built as a way to help people who may be struggling with mental health issues but are unsure of where to find help
        and need a safe space to start the conversation about their feelings.
        
        :rocket: **Getting started**
        
        To get started using **Sana**, give a description of who you are and how you're feeling. For example, you could say:
        > Hello. I am a 23 year old software engineer living in Los Angeles. I've been feeling very anxious when interacting with people lately.
        > I am a very introverted person and I get extremely nervous when I have to meet new people. This has been affecting my work and personal life to a great extent.
                
        The more context you provide, the better **Sana** can assist you in finding the right resources and help.

        Thanks for trying out **Sana**!

        [David Jiménez Rodríguez](https://github.com/david-1792), author of the project
    ''')

@st.dialog(
    title=':warning: Disclaimer'
)
def disclaimer_dialog() -> None:
    st.markdown('''
    This is an early prototype made as a submission to the [AWS AI Agent Global Hackathon 2025](https://aws-agent-hackathon.devpost.com/).
    This project is **NOT** tested or certified to be used in a production environment with users in need of urgent mental health care.
                
    Sana is **NOT** a replacement for professional mental health care.
    It can help you find resources and connect with professionals, but it can **NOT** provide therapy or medical advice.
    
    It will **NOT** diagnose or treat any mental health conditions, as those are not tasks that should be performed by an AI model.
    This is the core idea and principle behind Sana: to be a tool that helps you find the right resources and professional help, **NOT** to replace them.
    
    The information provided by Sana is based on a very limited dataset of **US-based** information and should **NOT** be the sole basis for making decisions about your mental health.
    Always seek the advice of a qualified mental health professional with any questions you may have regarding your mental health or a medical condition.

    If you are in crisis or need immediate help, please contact a mental health professional or [search for an adequate crisis helpline](https://findahelpline.com/).
    ''')

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
    if 'welcome_shown' not in st.session_state:
        welcome_dialog()
        st.session_state['welcome_shown'] = True

    with st.sidebar:
        st.image('app/static/logo.png', width='stretch')
        st.markdown(
            '<div style="text-align: center; font-size: 20px;"> Welcome to <b>Sana</b>! 👋</div>',
            unsafe_allow_html=True,
        )
        st.markdown('---')

        st.subheader('⚙️ **Settings**')

        allow_location = st.checkbox('📍 Allow location access')

        with st.empty():
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

        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown('---')
        if st.button('🚪 Logout', use_container_width=True, type='secondary'):
            auth.logout()

        if st.button(':warning: Disclaimer', use_container_width=True, type='secondary'):
            disclaimer_dialog()

        st.link_button(
            '💻 Source code', 
            'https://github.com/david-1792/sana',
            use_container_width=True,
            type='secondary'
        )

    tokens: dict = auth.get_tokens()
    claims: dict = auth.get_user_claims()

    chat.display_conversation()

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