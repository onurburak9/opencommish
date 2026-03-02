.PHONY: dashboard install fetch-stats help

help:
	@echo "Available commands:"
	@echo "  make dashboard     - Start the Streamlit dashboard"
	@echo "  make install       - Install dashboard dependencies"
	@echo "  make fetch-stats   - Run the daily stats collection manually"

install:
	uv pip install -r dashboard/requirements.txt

dashboard:
	streamlit run dashboard/app.py

fetch-stats:
	python3 cron/fetch_daily_stats.py
