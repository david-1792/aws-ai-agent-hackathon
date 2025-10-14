
def create_safe_markdown(content: str, message_placeholder, unsafe_allow_html: bool = False) -> None:
    safe_content: str = content.encode('utf-16', 'surrogatepass').decode('utf-16')
    safe_content = safe_content.replace('<br>', '\n\n').replace('\\n', '\n')
    message_placeholder.markdown(safe_content, unsafe_allow_html=unsafe_allow_html)