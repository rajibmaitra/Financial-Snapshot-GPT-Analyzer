## Financial Snapshot + GPT Analyzer

Web app built with Flask that lets someone enter a personal finance snapshot, fetches a lightweight 90-day market view via `yfinance`, and sends both to OpenAI for an educational write-up. This follows the same logic as the original CLI script, just with a browser-friendly UI.

### Prerequisites

- Python 3.9+
- An OpenAI API key with access to the Responses API (`gpt-4.1-mini` in this example)
- Node is **not** required

### Setup

1. **Clone / copy the project**
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>
   ```
   (If you start locally first, run `git init` and follow the publishing steps below later.)

2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate     # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `.env.example` to `.env`.
   - Fill in your real `OPENAI_API_KEY`.
   - Optionally change `FLASK_SECRET_KEY` and `OPENAI_MODEL`.
   - Keep `.env` out of git (`.gitignore` already covers it if you create one).

### Run locally

```bash
flask --app app run
# or python app.py for the built-in dev server
```

Open http://127.0.0.1:5000 and fill out the form. The OpenAI response shows under “GPT Educational Scenarios”. Quota or auth issues from OpenAI will appear as a flash message and in your terminal logs.

### Deploy / host on GitHub

GitHub Pages cannot run Python backends, so you host the **code** on GitHub and deploy the live app to a Python-friendly host (Render, Railway, Fly.io, etc.). A simple flow:

1. **Create a new GitHub repo**
   - Go to https://github.com/new, name it (e.g., `financial-snapshot-app`), keep it Private or Public.

2. **Push the local project**
   ```bash
   git init
   git add .
   git commit -m "Add Flask GPT financial snapshot app"
   git remote add origin git@github.com:<your-username>/<repo>.git
   git push -u origin main
   ```

3. **Deploy to a host**
   - Render example: create a new “Web Service”, connect to your repo, pick Build Command `pip install -r requirements.txt`, Start Command `gunicorn app:app` (Render adds `gunicorn` automatically, or add it to `requirements.txt`). Add environment variables from your `.env`.
   - Railway/Fly/Heroku follow a similar pattern—point to the repo, configure environment, set start command.

4. **(Optional) GitHub Pages front door**
   - If you want a marketing page on GitHub Pages, keep `docs/` with static content that links to the deployed backend URL. The actual Flask app still runs on the dynamic host from step 3.

### Useful commands

- `pip freeze > requirements.txt` – refresh dependencies list after upgrades.
- `flask --app app run --reload --port 8000` – run on a specific port with auto reload.
- `pytest` – once you add tests.

### Security reminders

- Never commit your real `.env` or API keys.
- Monitor OpenAI usage and handle `429` errors (quota) gracefully.
- This tool is for education; it must not be sold as financial advice.
