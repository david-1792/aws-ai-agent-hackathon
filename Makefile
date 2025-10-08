web-app:
	uv run python -m streamlit run app.py

web-app-local:
	uv run python -m streamlit run app.py -- --local