
def create_safe_markdown(content: str, message_placeholder) -> None:
    safe_content: str = content.encode('utf-16', 'surrogatepass').decode('utf-16')
    message_placeholder.markdown(
        safe_content.replace('\\n', '<br>'),
        unsafe_allow_html=True
    )