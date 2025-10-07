import streamlit as st

css: str = """

"""
def apply_styles() -> None:
    st.markdown(
        f'<style>{css}</style>', 
        unsafe_allow_html=True
    )