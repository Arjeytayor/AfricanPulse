# AfricanPulse → GitHub Guide

Complete step-by-step guide to push this project to GitHub from the terminal.

---

## Prerequisites

1. **Git installed** on your Windows machine
   - Check: `git --version`
   - If not installed: `winget install Git.Git`

2. **GitHub account** — Sign up at https://github.com (free)

3. **GitHub CLI** (optional but recommended) — `winget install GitHub.cli`

---

## Part 1: Verify Your .gitignore is Working

Before pushing anything, make sure your secrets don't leak.

Open your terminal in the AfricanPulse folder and run the 
**`AfricanPulse/.gitignore`** file **already blocks** `.env`, `*.env`, `secrets.json`, and the `archive/` directory.  
**However**, always double-check with the dry-run below.

Open a terminal inside the `AfricanPulse/` folder and run:

```bash
git init
git add .
git status --dry-run --short -- .env
```

**If the above shows `.env` as a new file**, STOP.  Something is wrong with `.gitignore`, and your API keys will be pushed to GitHub.

If it shows nothing (good), continue.

---

## Part 2: Create the GitHub Repository

### Option A: Using GitHub CLI (gh)

1. **Log in** (one-time setup):
   ```bash
   gh auth login
   ```
   Follow the prompts (press `Enter` for web login, then `y` to authenticate with GitHub). A browser tab will open. Authorize `gh` and copy the code back into your terminal.

2. **Create the repository**:
   ```bash
   cd C:\Users\DELL\Documents\AfricanPulse
   gh repo create AfricanPulse --public --description "Global macro & crypto news intelligence pipeline" --source=. --push
   ```

   This single command:
   - Creates a **public** repo called `AfricanPulse` on your GitHub account
   - Links the local folder to it
   - Pushes every committed file

### Option B: Using the Website + Terminal

1. Go to **https://github.com/new**
2. Fill in:
   - **Repository name**: `AfricanPulse`
   - **Description**: `Global macro & crypto news intelligence pipeline`
   - **Visibility**: ◉ Public (or ◉ Private)
   - **Do NOT** check "Add a README" or ".gitignore" — you already have those
3. Click **Create repository**
4. Copy the URL (e.g., `https://github.com/YOUR_USERNAME/AfricanPulse.git`)

---

## Part 3: Push from Terminal (manual steps)

Run these commands in order inside the `AfricanPulse` folder:

```bash
# 1. Navigate to the project folder
cd C:\Users\DELL\Documents\AfricanPulse

# 2. Initialize git (only if not already done)
git init

# 3. Add all files that .gitignore allows
git add .

# 4. Verify what will be committed (your .env and secrets must NOT appear here)
git status

# 5. If .env or secrets show up, STOP and fix .gitignore first.
#    If not, commit everything:
git commit -m "Initial commit: WorldPulse pipeline v2.0 - dynamic topics, NIM LLM, Telegram delivery"

# 6. Connect to your GitHub repo (replace YOUR_USERNAME with your actual GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/AfricanPulse.git

# 7. Push the code
git push -u origin main
```

If your default branch is `master` instead of `main`, use:
```bash
git push -u origin master
```

---

## Part 4: Verify on GitHub

1. Go to `https://github.com/YOUR_USERNAME/AfricanPulse`
2. You should see all your files **except**:
   - `.env` (should be hidden by .gitignore)
   - `cache/` (should be hidden)
   - `logs/` (should be hidden)
   - `outputs/` (should be hidden)
   - `vector_index/` (should be hidden)
   - `archive/` (should be hidden)
   - `__pycache__/` (should be hidden)

3. Check by opening the `cache/` or `outputs/` folder on GitHub — they should **not** exist.

---

## Part 5: (Optional) Commit Only What Changed

After your initial push, you'll make changes. Here's the full workflow for future commits:

```bash
# Navigate to the project
cd C:\Users\DELL\Documents\AfricanPulse

# Check what changed
git status

# Stage specific files (recommended)
git add README.md

# ... or stage everything that changed
git add .

# Commit with a message
git commit -m "Updated README with installation steps"

# Push to GitHub
git push
```

---

## Part 6: What Files Will / Won't be on GitHub

| File/Folder | On GitHub? | Why |
|-------------|-----------|-----|
| `main.py`, `scheduler.py`, etc. | ✅ Yes | Core code — tracked |
| `README.md` | ✅ Yes | Documentation — tracked |
| `requirements.txt` | ✅ Yes | Dependencies — tracked |
| `.env` | ❌ No | Secrets — ignored by `.gitignore` |
| `archive/` | ❌ No | Old test files — ignored by `.gitignore` |
| `cache/` | ❌ No | Generated data — ignored by `.gitignore` |
| `outputs/` | ❌ No | Generated content — ignored by `.gitignore` |
| `logs/` | ❌ No | Generated logs — ignored by `.gitignore` |
| `__pycache__/` | ❌ No | Python bytecode — ignored by `.gitignore` |
| `vector_index/` | ❌ No | Vector index data — ignored by `.gitignore` |

---

## Part 7: Quick Reference Commands

| Command | What it does |
|---------|-------------|
| `git status` | Shows which files changed vs what's on GitHub |
| `git add .` | Stages all changes for commit |
| `git commit -m "message"` | Saves your changes locally |
| `git push` | Uploads your local commits to GitHub |
| `git pull` | Downloads latest changes from GitHub to your machine |
| `git log --oneline` | Shows your commit history |
| `git diff` | Shows what changed before you commit |

---

## Part 8: If You Ever Need to Update Secrets

If you accidentally pushed your `.env` with secrets, or rotate your API keys later:

1. **Update the `.env` file locally** (it's ignored now)
2. **Rotate the leaked key** on the provider's website (NIM, Telegram, Perplexity, etc.)
3. **Force-delete the file from Git history** (if exposed):
   ```bash
   git rm --cached .env
   git commit -m "Remove .env from tracking"
   git push
   ```

---

## Part 9: Clone on Another Machine

If you ever clone this repo on another computer, you need to recreate your `.env`:

```bash
git clone https://github.com/YOUR_USERNAME/AfricanPulse.git
cd AfricanPulse
cp .env.example .env
# Edit .env and fill in your keys
```

---

## Done

Congratulations. Your code is now backed up, shareable, and version-controlled on GitHub.
