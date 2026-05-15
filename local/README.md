# Recall - Local Development

Simple, cross-platform setup for running Recall locally on Windows, macOS, or Linux.

## Quick Start

### First Time Setup

```bash
# 1. Install dependencies
python local/recall.py setup

# 2. Start Recall
python local/recall.py run
```

That's it! Open http://localhost:8000/docs in your browser.

## Commands

| Command | Description |
|---------|-------------|
| `python local/recall.py setup` | Install Python dependencies and prepare environment |
| `python local/recall.py run` | Start both Qdrant (vector DB) and API server |
| `python local/recall.py api` | Start only the API (Qdrant must be running separately) |

## What Does Setup Do?

The setup command:
1. Creates a Python virtual environment (`venv/`)
2. Installs all required packages from `requirements.txt`
3. Downloads the spaCy language model (`en_core_web_sm`)
4. Creates data directories for storage

## What Does Run Do?

The run command:
1. Downloads Qdrant standalone binary (if not already present)
2. Starts Qdrant on port 6333
3. Starts the FastAPI server on port 8000

Both services run together, and you can stop everything with `Ctrl+C`.

## Requirements

- **Python 3.11+** (check with `python --version`)
- **4GB+ RAM** (for vector embeddings)
- **~2GB disk space** (for models and data)

## Using Docker Instead

If you prefer Docker over the standalone setup:

```bash
# Start everything with Docker Compose
docker-compose up --build

# Stop everything
docker-compose down
```

## URLs

Once running, you can access:

- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Qdrant Dashboard:** http://localhost:6333/dashboard

## Troubleshooting

### Qdrant Won't Start

If the automatic Qdrant download fails, you can use Docker instead:

```bash
# In one terminal
docker run -p 6333:6333 -v $(pwd)/data/qdrant_storage:/qdrant/storage qdrant/qdrant

# In another terminal
python local/recall.py api
```

### Python Version Too Old

Recall requires Python 3.11 or newer. Check your version:

```bash
python --version
```

If too old, install a newer version from [python.org](https://www.python.org/downloads/)

### Dependencies Failed to Install

Make sure you're inside the virtual environment and try again:

**Windows:**
```bash
venv\Scripts\activate
python -m pip install -r requirements.txt
```

**macOS/Linux:**
```bash
source venv/bin/activate
python -m pip install -r requirements.txt
```

## File Structure

```
recall/
├── local/
│   ├── recall.py          # Main launcher script (setup + run)
│   └── README.md          # This file
├── backend/               # FastAPI application
├── data/                  # Persistent storage (auto-created)
│   ├── qdrant_storage/   # Vector database
│   ├── kuzu/             # Graph database
│   └── recall.db         # SQLite metadata
├── venv/                  # Virtual environment (auto-created)
├── qdrant_standalone/     # Qdrant binary (auto-downloaded)
├── requirements.txt       # Python dependencies
└── docker-compose.yml     # Docker setup (alternative)
```

## What Gets Created?

Running setup and run will create:
- `venv/` - Python virtual environment
- `data/` - All your uploaded documents and embeddings
- `qdrant_standalone/` - Qdrant database binary

You can delete these folders to start fresh.

## Advanced Usage

### Run API Only (Qdrant Separate)

If you want to manage Qdrant yourself:

```bash
# Terminal 1: Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant

# Terminal 2: Start API only
python local/recall.py api
```

### Use Custom Python

If you have multiple Python versions:

```bash
python3.11 local/recall.py setup
python3.11 local/recall.py run
```

### Environment Variables

You can customize behavior with environment variables:

```bash
# Example: Change API port
export API_PORT=9000
python local/recall.py run
```

See `.env.example` in the project root for all available options.

## Getting Help

- Run `python local/recall.py --help` for command help
- Check API docs at http://localhost:8000/docs when running
- See main README.md for architecture details
