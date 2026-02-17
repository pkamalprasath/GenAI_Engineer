# GitHub Setup Guide

**GitHub Profile:** https://github.com/pkamalprasath/GenAI_Engineer

---

## 🚀 Quick Setup (3 Minutes)

### Option 1: Use the Script (Easiest)

```bash
# 1. Edit push_to_github.sh and update YOUR_EMAIL
# 2. Run the script
bash push_to_github.sh
```

### Option 2: Manual Commands

**Step 1: Create Repository on GitHub**
- Go to: https://github.com/new
- Name: `slack-bot-assistant`
- Description: "AI-powered Slack bot with agent system, RAG, and MCP integrations"
- **Important:** DO NOT check "Initialize with README"

**Step 2: Run These Commands**

```bash
# Navigate to project directory
cd "d:\AI\KrishNaik_Academy\Coding\Vizuara\open_claw_proj"

# Initialize Git
git init

# Configure user
git config user.name "pkamalprasath"
git config user.email "YOUR_EMAIL@example.com"  # Your GitHub email

# Add all files
git add .

# Create commit
git commit -m "Initial commit: AI-powered Slack Bot Assistant

Features:
- Full agent system with 15+ tools
- RAG knowledge base with ChromaDB
- MCP integrations (Slack, GitHub, Notion)
- Comprehensive test suite (11/11 passing)
- Complete documentation and learning materials
- Production-ready error handling and logging

See QUICK_START.md to get started."

# Rename branch to main
git branch -M main

# Add remote (replace 'slack-bot-assistant' with your repo name)
git remote add origin https://github.com/pkamalprasath/slack-bot-assistant.git

# Push to GitHub
git push -u origin main
```

---

## 🔑 Authentication

### If GitHub Asks for Password

GitHub no longer accepts passwords. Use a **Personal Access Token** instead:

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name: "Slack Bot Assistant"
4. Scopes: Check `repo` (full control of private repositories)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again!)

**When Git prompts for password:**
- Username: `pkamalprasath`
- Password: Paste your Personal Access Token

---

## ✅ Verification

After pushing, verify everything is on GitHub:

```bash
# Check remote URL
git remote -v

# Check what was pushed
git log --oneline -5

# View repository on GitHub
# Open: https://github.com/pkamalprasath/slack-bot-assistant
```

---

## 🎨 After Pushing: Repository Settings

### 1. Add Topics (Tags)

On your repository page, click "Add topics":
- `slack-bot`
- `ai-agent`
- `langraph`
- `python`
- `anthropic`
- `fastmcp`
- `rag`
- `educational`

### 2. Edit Description

Update repository description:
```
AI-powered Slack bot with agent system, RAG knowledge base, and MCP integrations. Production-ready with comprehensive documentation and learning materials.
```

### 3. Add Website (Optional)

If you deploy the documentation:
- Add your GitHub Pages URL or documentation site

### 4. Add LICENSE (Recommended)

```bash
# Create MIT License
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2026 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# Commit and push
git add LICENSE
git commit -m "Add MIT License"
git push
```

### 5. Enable GitHub Features

In repository Settings:
- **Discussions:** Enable (for Q&A)
- **Issues:** Enable (for bug reports)
- **Projects:** Enable (optional, for project management)
- **Branch Protection:** Add rule for `main` branch
  - Require pull request reviews
  - Require status checks to pass

---

## 📊 Repository Structure on GitHub

Your repository will look like this:

```
slack-bot-assistant/
├── 📄 README.md                    ← GitHub shows this on main page
├── 🚀 QUICK_START.md
├── 📚 docs/                        ← All documentation
├── 🎓 .claude/                     ← Learning materials
├── 💻 src/                         ← Source code
├── ⚙️ config/                      ← Configuration
├── 🧪 tests/                       ← Tests
├── .env.example                    ← Safe template
├── .gitignore                      ← Prevents secrets
└── pyproject.toml                  ← Dependencies
```

**What's NOT on GitHub (gitignored):**
- `.env` (your secrets)
- `logs/` (runtime logs)
- `memory_store/` (user data)
- `.venv/` (virtual environment)

---

## 🐛 Troubleshooting

### Error: "Repository not found"

**Cause:** Repository doesn't exist on GitHub yet

**Fix:**
1. Create repository at: https://github.com/new
2. Make sure name matches in `git remote add origin` command

---

### Error: "Permission denied (publickey)"

**Cause:** SSH key not configured

**Fix:** Use HTTPS instead (already in commands above), or:

```bash
# Switch to HTTPS
git remote set-url origin https://github.com/pkamalprasath/slack-bot-assistant.git
```

---

### Error: "Repository already exists"

**Cause:** Repository was initialized with README on GitHub

**Fix:**

```bash
# Pull and merge
git pull origin main --allow-unrelated-histories

# Then push
git push -u origin main
```

---

### Error: "Detected secrets in commit"

**Cause:** `.env` file might be staged

**Fix:**

```bash
# Unstage .env
git reset HEAD .env

# Verify .env is in .gitignore
grep "^.env$" .gitignore

# Commit without .env
git commit -m "Your message"
git push
```

---

### Want to Undo Last Commit?

```bash
# Undo commit but keep changes
git reset --soft HEAD~1

# Undo commit and changes (careful!)
git reset --hard HEAD~1
```

---

## 📝 Future Updates

After initial push, to update GitHub:

```bash
# Make changes to files

# Stage changes
git add .

# Commit
git commit -m "Description of changes"

# Push
git push
```

---

## 🎓 Learning Resources

### Git Basics
- **Git Handbook:** https://guides.github.com/introduction/git-handbook/
- **GitHub Docs:** https://docs.github.com/

### Best Practices
- **Commit Messages:** https://chris.beams.io/posts/git-commit/
- **Branch Strategy:** https://nvie.com/posts/a-successful-git-branching-model/

---

## ✨ Make Your Repository Stand Out

### Create a Great README

Your `README.md` already has:
- ✅ Clear project description
- ✅ Features list
- ✅ Setup instructions
- ✅ Documentation links
- ✅ Contributing guidelines

### Add Badges (Optional)

Add to top of README.md:

```markdown
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Tests](https://img.shields.io/badge/tests-11%2F11%20passing-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
```

### Create First Release

After your first push:

```bash
# Tag the release
git tag -a v1.0.0 -m "First stable release"
git push origin v1.0.0
```

Then on GitHub:
1. Go to Releases
2. Click "Draft a new release"
3. Choose tag `v1.0.0`
4. Title: "v1.0.0 - Initial Release"
5. Description: Copy from `docs/development/FIXES_SUMMARY.md`

---

## 🎯 Quick Checklist

Before pushing:
- [x] `.env` is empty (all secrets removed)
- [x] `.env.example` has template values
- [x] `.gitignore` prevents sensitive files
- [x] `logs/` directory is empty
- [x] `memory_store/` has no user data
- [x] All documentation updated
- [x] Tests passing (11/11)

After pushing:
- [ ] Repository visible on GitHub
- [ ] README displays correctly
- [ ] Topics/tags added
- [ ] LICENSE file added
- [ ] Repository description updated
- [ ] GitHub features enabled

---

**Ready to Push!** 🚀

Run `bash push_to_github.sh` or follow the manual commands above.

Your project will be live at:
**https://github.com/pkamalprasath/slack-bot-assistant**

---

**Last Updated:** 2026-02-18
**Status:** Ready for GitHub Release ✅
