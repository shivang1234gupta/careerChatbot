# Deploying the Chatbot

This app is a **Gradio** chatbot (Python). Below are practical ways to deploy it.

---

## 1. Hugging Face Spaces (easiest, free tier)

Good for: quick public demos, no credit card.

1. **Push your code to GitHub** (ensure `me/` with PDFs and `summary.txt` is in the repo, or use Git LFS for large PDFs).

2. **Create a Space** at [huggingface.co/spaces](https://huggingface.co/spaces):
   - Choose **Gradio** as SDK.
   - Link your GitHub repo or upload the project.

3. **Set secrets** in the Space: **Settings → Repository secrets** (or Variables):
   - `GEMINI_API_KEY` – your Gemini API key
   - `PUSHOVER_TOKEN` – optional, for notifications
   - `PUSHOVER_USER` – optional

4. Your `README.md` already has the Spaces YAML; the Space will run `chatbot.py` with Gradio.

5. **Hardware**: Free CPU is enough. If it’s slow, use a Space with more CPU or a small GPU (paid).

---

## 2. Railway

Good for: always-on app, custom domain, simple config.

1. Install [Railway CLI](https://docs.railway.app/develop/cli) and log in.

2. In your project directory:
   ```bash
   railway init
   railway up
   ```

3. In **Railway dashboard**:
   - Add **Environment variables**: `GEMINI_API_KEY`, `PUSHOVER_TOKEN`, `PUSHOVER_USER`.
   - Under **Settings**, set **Start Command** to:
     ```bash
     python chatbot.py
     ```
   - Or add a **Procfile** in the repo:
     ```
     web: python chatbot.py
     ```

4. Railway will expose the app via a public URL. Gradio runs on port 7860 by default; Railway usually detects it. If not, set **PORT** and in code use something like:
   ```python
   gr.ChatInterface(me.chat).launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
   ```

---

## 3. Render

1. Create a **Web Service** at [render.com](https://render.com), connected to your GitHub repo.

2. **Build**:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python chatbot.py`

3. **Environment**: Add `GEMINI_API_KEY`, `PUSHOVER_TOKEN`, `PUSHOVER_USER`.

4. Render expects the app to listen on `PORT`. Add to `chatbot.py` before `launch()`:
   ```python
   port = int(os.environ.get("PORT", 7860))
   gr.ChatInterface(me.chat).launch(server_name="0.0.0.0", server_port=port)
   ```

---

## 4. Docker (any cloud or VPS)

Use this to run the same image on your own server, Fly.io, AWS, etc.

**Dockerfile** (create in project root):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Gradio default port; override with PORT env if needed
ENV PORT=7860
EXPOSE 7860

CMD ["python", "chatbot.py"]
```

**Run locally:**
```bash
docker build -t chatbot .
docker run -p 7860:7860 --env-file .env chatbot
```

For production, pass env vars via your platform (e.g. `-e GEMINI_API_KEY=...`) or a secret manager; don’t bake `.env` into the image.

---

## Checklist before deploy

- [x] **Paths**: Code uses `PROJECT_ROOT` and `ME_DIR` so PDFs and `summary.txt` are loaded from the repo (no absolute paths).
- [x] **Binding**: `server_name="0.0.0.0"` is set so the server is reachable in containers/cloud.
- [ ] **Secrets**: Set `GEMINI_API_KEY` (required) and optional Pushover vars on the platform; do not commit `.env`.
- [ ] **Port**: On Render/Railway/Fly, use `PORT` from the environment if they require it (see sections above).

---

## Optional: use `PORT` everywhere

If you want one codebase that works on both local and Render/Railway, you can change the last lines of `chatbot.py` to:

```python
if __name__ == "__main__":
    me = Me(use_rag=True)
    port = int(os.environ.get("PORT", 7860))
    gr.ChatInterface(me.chat).launch(server_name="0.0.0.0", server_port=port)
```

Then local runs stay on 7860, and in the cloud the platform’s `PORT` will be used.
