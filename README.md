# Swaylytics

An agentic data science assistant. Upload a dataset, ask a question, and watch the model write and run Python code iteratively until it reaches an answer.

## How it works

The backend runs a multi-round reasoning loop: the model generates analysis and Python code, executes it in a sandboxed workspace, feeds the results back, and iterates until it produces a conclusion — or stops after 30 rounds.

## Modes

**Swaylytics mode** — uses the DeepAnalyze-8B model hosted on GCP via vLLM and Gemini. Requires the SSH tunnel below.

**Gemini-only mode** — uses Gemini for planning and execution without a local model. Works without the GCP tunnel. Requires a `GEMINI_API_KEY` in `.env`.

## Prerequisites

- [Anaconda](https://www.anaconda.com/download) (for the Python environment)
- [Node.js](https://nodejs.org/) (for the frontend)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) — only if using DeepAnalyze mode

## Installation

```bash
# 1. Create and activate a conda environment
conda create -n swaylytics python=3.11
conda activate swaylytics

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install frontend dependencies
cd frontend && npm install && cd ..
```

## Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API key — enables Gemini-only mode and hybrid router | For Gemini mode |
| `GEMINI_MODEL` | Gemini model to use (default: `gemini-3-flash-preview`) | No |
| `ROUTER_ERROR_RECOVERY` | Auto-recover from execution errors via Gemini (default: `true`) | No |
| `ROUTER_CHECKPOINTS` | Gemini checks model reasoning at intervals (default: `true`) | No |
| `ROUTER_CHECKPOINT_INTERVAL` | Rounds between checkpoint checks (default: `3`) | No |

## Running

**DeepAnalyze mode** — connect to the GCP inference server first (skip if using Gemini-only mode):

```bash
gcloud compute ssh your-server-name --zone=your-zone \
  --ssh-flag="-N" --ssh-flag="-L" --ssh-flag="8000:localhost:8000"
```

Then start the app:

```bash
# Windows
.\start.bat

# macOS / Linux
./start.sh
```

This starts both services:
- **Backend** (FastAPI) — http://localhost:8200
- **Frontend** (Next.js) — http://localhost:3000

Logs are written to `logs/backend.log` and `logs/tiramisu.log`.

To stop:

```bash
# Windows
.\stop.bat

# macOS / Linux
./stop.sh
```

## Project structure

```
.
├── frontend/             # Next.js frontend
│   ├── app/              # Pages
│   ├── components/       # React components and UI library
│   └── lib/              # API client and utilities
├── backend.py            # FastAPI entry point
├── backend_app/
│   ├── routers/          # API routes (chat, workspace, export)
│   └── services/         # Business logic (agentic loop, execution, export)
├── requirements.txt      # Python dependencies
├── start.bat / start.sh  # Start both services
└── stop.bat / stop.sh    # Stop both services
```

## License

See [LICENSE](LICENSE).
