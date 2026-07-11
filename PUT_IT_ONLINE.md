# Put your app on the internet (free, no coding)

You'll use two free websites. Total time: about 15 minutes. At the end you get a
public link like `https://your-app-name.streamlit.app` that anyone can open.

---

## Part 1 — Put the code on GitHub (5 min)

GitHub is where the code lives. Streamlit (Part 2) reads it from there.

1. Go to **github.com** and click **Sign up** (skip if you already have an account).
2. Once logged in, click the **+** button (top-right) → **New repository**.
3. Fill in:
   - Repository name: `rent-agreement-analyzer`
   - Keep it on **Public** (required for free hosting)
   - Don't tick any checkboxes
4. Click **Create repository**.
5. On the next page, click the small link that says **"uploading an existing file"**.
6. Open your **Application Rent Agreement** folder in Finder, select these items and
   **drag them into the browser window**:
   - `app.py`
   - `requirements.txt`
   - the whole `rent_analyzer` folder  ← most important
   - (optional: `README.md`)

   ⚠️ Do NOT upload `Start App.command` — GitHub is fine without it.
7. Wait for the upload bars to finish, then click the green **Commit changes** button.

## Part 2 — Turn it into a live website (5 min)

1. Go to **share.streamlit.io**
2. Click **Continue to sign-in** → **Continue with GitHub** → **Authorize**.
3. Click **Create app** (top-right) → choose **"Deploy a public app from GitHub"**.
4. Fill in:
   - Repository: `your-username/rent-agreement-analyzer`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: pick any name you like (this becomes your link)
5. Click **Deploy**. You'll see it "baking" for 2–3 minutes.
6. Done — your app is live. Copy the link from the address bar and share it with anyone.

---

## Updating the app later

If the code in your folder changes, just repeat Part 1 step 5–7 (upload the changed
files again and Commit). The live website updates itself automatically in ~1 minute.

## If something goes wrong

- **App shows an error page**: on share.streamlit.io, click your app → "Manage app" →
  read the log at the bottom; it usually says what's missing.
- **"This file already exists"** during upload: that's fine — committing replaces it.
- Stuck? Just describe what you see on screen to Claude.
