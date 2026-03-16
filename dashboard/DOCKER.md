# OpenCommish Dashboard - Docker

This directory contains the Streamlit analytics dashboard for OpenCommish.

## Building the Docker Image

```bash
cd dashboard
docker build -t opencommish-dashboard .
```

## Running the Container

```bash
# Run with data directory mounted
docker run -p 8501:8501 \
  -v $(pwd)/../data:/app/data \
  -e STREAMLIT_SERVER_PORT=8501 \
  opencommish-dashboard
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STREAMLIT_SERVER_PORT` | 8501 | Port for Streamlit server |
| `STREAMLIT_SERVER_ADDRESS` | 0.0.0.0 | Bind address |
| `STREAMLIT_SERVER_HEADLESS` | true | Run without browser auto-open |

## Accessing the Dashboard

Once running, access at: http://localhost:8501
