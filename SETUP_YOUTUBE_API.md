# YouTube Data API v3 — key setup

You need one free API key from Google Cloud. ~5 minutes. No billing required for
the default quota (10,000 units/day; our retrieval logs its usage).

## Steps

1. **Sign in** to Google Cloud Console: https://console.cloud.google.com/

2. **Create a project**
   - Top bar → project dropdown → *New Project*.
   - Name it e.g. `meditation-vlm-study` → *Create* → select it.

3. **Enable the API**
   - Go to: https://console.cloud.google.com/apis/library/youtube.googleapis.com
   - Make sure your project is selected → click **Enable**.

4. **Create the key**
   - Go to: *APIs & Services → Credentials*
     (https://console.cloud.google.com/apis/credentials)
   - **+ Create Credentials → API key**.
   - Copy the key string.

5. **(Recommended) Restrict the key**
   - On the key → *Edit*:
     - *API restrictions* → **Restrict key** → check **YouTube Data API v3**.
     - (Optional) *Application restrictions* → leave **None** for local scripts.
   - Save.

## Give the key to the pipeline (do NOT paste it into chat)

Two options — pick one:

**A. Environment variable (preferred)**
```bash
export YOUTUBE_API_KEY="paste-your-key-here"
```
Add it to your `~/.zshrc` to persist. The config file already reads
`${YOUTUBE_API_KEY}`.

**B. In the config file**
```bash
cp config/config.pilot.yaml config/config.yaml
# then edit config/config.yaml -> retrieval.youtube_api_key: "your-key"
```
`config/config.yaml` is git-ignored, so the key won't be committed.

## Quota notes
- A `search.list` call costs **100 units**; `videos`/`channels` cost ~1 each.
- The pilot (`max_results_per_query: 8`, English only) uses only a few hundred
  units — well within the daily 10,000.
- The full ~2000-video run across all techniques will use more; the retrieval
  manifest (`data/01_raw/retrieval_manifest.json`) records exact usage. If you
  hit the daily cap, the run resumes the next day or you can request a quota
  increase in the Cloud Console.

## Verify
Once the key is set:
```bash
source .venv/bin/activate
pip install -r requirements.txt      # installs the live-run deps
python scripts/01_retrieve.py        # should print "N unique videos -> ..."
```
