# ExplainMyScreen AI

ExplainMyScreen AI helps people understand complex website interfaces, mobile
application screens, online forms, and technical error messages. Upload a
screenshot to get a clear explanation of the visible content, important
controls, possible solutions, and suggested next steps.

## Problem statement

Beginners and non-technical users can struggle to understand buttons, form
fields, and error messages on digital screens. Finding reliable help online
can be time-consuming and confusing, making it harder for people to use
digital services independently.

## Proposed solution

The application analyzes uploaded screenshots and explains what is visible in
beginner-friendly language. It can identify relevant interface elements,
explain visible errors, and suggest safe, step-by-step actions. Screenshot
analysis uses a locally running vision model through Ollama.

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running
- The `gemma3:4b` model (or another Ollama vision model selected with
  `OLLAMA_MODEL`)

## Run locally

1. Create and activate a virtual environment.
2. Install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Download the default model:

   ```powershell
   ollama pull gemma3:4b
   ```

4. Start the API:

   ```powershell
   python -m uvicorn main:app --host 127.0.0.1 --port 5000
   ```

5. Open [http://localhost:5000](http://localhost:5000) or visit
   [http://localhost:5000/docs](http://localhost:5000/docs) to try the API.

Set `OLLAMA_MODEL` to use another compatible Ollama vision model. Set
`FRONTEND_ORIGINS` to a comma-separated list of frontend origins if a separate
frontend needs to call the API.

## API endpoints

- `GET /` — service information
- `GET /health` — API health check
- `POST /analyze` — analyze an uploaded PNG, JPEG, or WEBP screenshot

The screenshot upload limit is 8 MB. Analysis depends on Ollama being available
locally.
