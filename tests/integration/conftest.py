import pytest
from playwright.sync_api import Page, expect
import subprocess
import time
import socket


def wait_for_port(host: str, port: int, timeout: float = 60.0) -> bool:
    """Wait for a port to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    return False


@pytest.fixture(scope="session")
def streamlit_server():
    """Start Streamlit server for testing."""
    # Start Streamlit in background
    process = subprocess.Popen(
        ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.headless=true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to be ready
    if not wait_for_port("localhost", 8501, timeout=60):
        process.terminate()
        raise RuntimeError("Streamlit server failed to start")
    
    yield "http://localhost:8501"
    
    # Cleanup
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture
def dashboard_page(page: Page, streamlit_server: str):
    """Navigate to the dashboard."""
    page.goto(streamlit_server)
    # Wait for Streamlit to load
    page.wait_for_selector("[data-testid='stApp']", timeout=30000)
    return page
