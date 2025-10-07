import streamlit as st

from app.auth import SanaAuth
from app.chat import SanaChat
from app.styles import apply_styles

def main() -> None:
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