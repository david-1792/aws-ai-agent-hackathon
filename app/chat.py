import uuid
import time

from collections.abc import Generator

import requests
import streamlit as st

from app.config import settings
from app.utils import create_safe_markdown

class SanaChat:
    def __init__(self) -> None:
        self._init_session_state()

    def process_user_message(self, message: str, claims: dict, tokens: dict) -> None:
        st.session_state['messages'].append({'role': 'user', 'content': message})

        with st.chat_message('user'):
            create_safe_markdown(f'<span class="user-bubble">{message}</span>', st)
            st.session_state['pending_assistant'] = True

        with st.chat_message('assistant'):
            placeholder = st.empty()

            create_safe_markdown('<span class="thinking-bubble">...</span>', placeholder)

            chunk_count: int = 0
            response: str = ''

            payload: dict = {
                'prompt': message,
                'actor': {
                    'city': st.session_state.get('city', 'Ciudad de México')
                }
            }

            for chunk in self.invoke_endpoint(
                payload=payload,
                session_id=st.session_state['session_id'],
                bearer_token=tokens.get('access_token')
            ):
                chunk = str(chunk)
                if not chunk:
                    continue

                chunk_count += 1
                response += chunk
                if chunk_count % 3 == 0:
                    response += ''

                create_safe_markdown(f'<div class="assistant-bubble streaming typing-cursor">{response}</div>', placeholder)
                time.sleep(0.02)

            st.session_state['pending_assistant'] = False
            st.session_state['messages'].append({'role': 'assistant', 'content': response})

    def display_conversation(self) -> None:
        messages = st.session_state.messages[:]

        if (
            messages
            and messages[-1]['role'] == 'user'
            and st.session_state.get('pending_assistant', False)
        ):
            messages = messages[:-1]

        for message in messages:
            bubble_class: str = 'user-bubble' if message['role'] == 'user' else 'assistant-bubble'

            with st.chat_message(message['role']):
                if message['role'] == 'assistant':
                    create_safe_markdown(f'<div class="{bubble_class}">{message["content"]}</div>', st)
                else:
                    create_safe_markdown(f'<span class="{bubble_class}">{message["content"]}</span>', st)

    def invoke_endpoint(
        self,
        payload: dict,
        session_id: str,
        bearer_token: str,
        endpoint_version: str = 'DEFAULT'
    ) -> Generator[str, None, None]:
        params: dict = {'qualifier': endpoint_version}

        headers: dict = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id,
        }

        try:
            response = requests.post(
                url=settings.AWS_AGENTCORE_RUNTIME_URL,
                params=params,
                headers=headers,
                json=payload,
                timeout=100,
                stream=True
            )

            finished: bool = False
            for line in response.iter_lines(chunk_size=1):
                if not line:
                    continue

                line = line.decode('utf-8')
                if line.startswith('data: '):
                    line = line[len('data: '):]
                    line = line.replace('"', '')
                    yield line
                elif line:
                    line = line.replace('"', '')
                    if finished:
                        yield '\n' + line
                    finished = True

        except requests.exceptions.RequestException as e:
            raise e

    def _init_session_state(self) -> None:
        if 'session_id' not in st.session_state:
            st.session_state['session_id'] = str(uuid.uuid4())

        if 'messages' not in st.session_state:
            st.session_state['messages'] = []

        if 'pending_assistant' not in st.session_state:
            st.session_state['pending_assistant'] = False
