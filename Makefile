deploy-app-local:
	uv run  --package sana-app streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true

deploy-agent-local:
	uv run --package sana-agent python -m sana.main