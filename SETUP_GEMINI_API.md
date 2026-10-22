# Gemini (Google AI Studio) — free API key

The second VLM coder. The free tier is enough for the pilot and much of the full
study (Gemini 2.0 Flash free tier: ~15 requests/min, ~1,500/day). No billing/card
required.

## Steps
1. Go to **Google AI Studio**: https://aistudio.google.com/apikey
   (sign in with any Google account).
2. Click **Create API key** → *Create API key in new project* (or pick a project).
3. Copy the key (starts with `AIza...`).

## Give it to the pipeline (do NOT paste into chat)
Terminal one-liner — the key is typed into your terminal, not the chat, and saved
to the git-ignored `config/config.yaml`:

```bash
cd "/Users/saipe/claude code/youtube VLM"
python3 - <<'EOF'
import re, pathlib, getpass
p = pathlib.Path("config/config.yaml"); t = p.read_text()
g = getpass.getpass("Gemini API 키 붙여넣고 Enter: ").strip()
t = re.sub(r'(google_api_key:\s*).*', f'\\1"{g}"', t, count=1)
p.write_text(t); print("저장 완료 →", p)
EOF
```

(Or edit `config/config.yaml` → `secrets.google_api_key: "your-key"` and save.)

## Notes
- The Gemini API key is different from the YouTube Data API key, even though both
  start with `AIza`. Keep both.
- Free-tier rate limits are fine for the ~30-video pilot; the automated coding
  stage retries with backoff if it hits a limit.
