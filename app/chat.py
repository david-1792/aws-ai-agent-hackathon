import uuid
import urllib
import time

from collections.abc import Generator

import requests
import streamlit as st

from utils.aws import get_region
from app.utils import create_safe_markdown

class SanaChat:
    def __init__(self) -> None:
        self.agent_name = 'sana'
        self._init_session_state()

    def process_user_message(self, message: str, claims: dict, tokens: dict) -> None:
        st.session_state['messages'].append({'role': 'user', 'content': message})

        with st.chat_message('user'):
            st.session_state['pending_assistant'] = True

        with st.chat_message('assistant'):
            placeholder = st.empty()

            create_safe_markdown('<span class="thinking-bubble">🧠 ...</span>', placeholder)

            chunk_count: int = 0
            response: str = ''

            payload: dict = {
                'prompt': message,
                'actor_id': claims.get('sub')
            }

            for chunk in self.invoke_endpoint(
                payload=payload,
                session_id=st.session_state['session_id'],
                bearer_token=tokens.get('access_token')
            ):
                chunk = str(chunk)
                if not chunk.strip():
                    continue

                chunk_count += 1
                response += chunk
                if chunk_count % 3 == 0:
                    response += ''

                create_safe_markdown(f'<div class="assistant-bubble streaming typing-cursor">🧠 {response}</div>', placeholder)
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
            emoji: str = '🧑' if message['role'] == 'user' else '🧠'

            with st.chat_message(message['role']):
                if message['role'] == 'assistant':
                    create_safe_markdown(f'<div class="{bubble_class}">{emoji} {message["content"]}</div>', st)
                else:
                    create_safe_markdown(f'<span class="{bubble_class}">{emoji} {message["content"]}</span>', st)

    def invoke_endpoint(
        self,
        payload: dict,
        session_id: str,
        bearer_token: str,
        endpoint_version: str = 'DEFAULT'
    ) -> Generator[str, None, None]:
        escaped_arn: str = urllib.parse.quote(st.session_state['agent_arn'], safe='')

        url: str = f'https://bedrock-agentcore.{st.session_state['region']}.amazonaws.com/runtimes/{escaped_arn}/invocations'

        params: dict = {'qualifier': endpoint_version}

        headers: dict = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id,
        }

        try:
            response = requests.post(
                url=url,
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
                elif line.startswith('tool: '):
                    line = line[len('tool: '):]
                    line = line.replace('"', '')
                    yield f"[TOOL] {line}"
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

        if 'agent_arn' not in st.session_state:
            st.session_state['agent_arn'] = None

        if 'region' not in st.session_state:
            st.session_state['region'] = get_region()

        if 'messages' not in st.session_state:
            st.session_state['messages'] = []

        if 'pending_assistant' not in st.session_state:
            st.session_state['pending_assistant'] = False
