#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Push Slack Bot Assistant to GitHub
# ═══════════════════════════════════════════════════════════════════════════════
#
# BEFORE RUNNING THIS SCRIPT:
# 1. Create a new repository on GitHub: https://github.com/new
# 2. Repository name: slack-bot-assistant (or your choice)
# 3. DO NOT initialize with README, .gitignore, or license
# 4. Update REPO_NAME below if you chose a different name
# 5. Update YOUR_EMAIL below with your GitHub email
#
# THEN RUN: bash push_to_github.sh
# ═══════════════════════════════════════════════════════════════════════════════

# Configuration
GITHUB_USERNAME="pkamalprasath"
REPO_NAME="open_claw_slack_bot"  # Change this if needed
YOUR_EMAIL="pkamalprasath@gmail.com"  # IMPORTANT: Change this to your GitHub email

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "  Pushing Slack Bot Assistant to GitHub"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Check if repository name was changed
if [ "$REPO_NAME" = "slack-bot-assistant" ]; then
    echo -e "${YELLOW}⚠️  Using default repository name: $REPO_NAME${NC}"
    echo -e "${YELLOW}   Update REPO_NAME in this script if you chose a different name${NC}"
    echo ""
fi

# Check if email was changed
if [ "$YOUR_EMAIL" = "your-email@example.com" ]; then
    echo -e "${YELLOW}⚠️  WARNING: You need to update YOUR_EMAIL in this script!${NC}"
    echo -e "${YELLOW}   Open push_to_github.sh and change YOUR_EMAIL to your GitHub email${NC}"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to exit and update..."
fi

# Step 1: Initialize Git repository
echo -e "${BLUE}[1/7]${NC} Initializing Git repository..."
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "✓ Git repository already initialized"
else
    git init
    echo "✓ Git repository initialized"
fi

# Step 2: Configure Git user
echo ""
echo -e "${BLUE}[2/7]${NC} Configuring Git user..."
git config user.name "$GITHUB_USERNAME"
git config user.email "$YOUR_EMAIL"
echo "✓ Git user configured: $GITHUB_USERNAME <$YOUR_EMAIL>"

# Step 3: Add all files
echo ""
echo -e "${BLUE}[3/7]${NC} Adding all files to staging..."
git add .
echo "✓ All files added"

# Step 4: Verify what will be committed
echo ""
echo -e "${BLUE}[4/7]${NC} Files to be committed:"
git status --short | head -20
echo "..."
TOTAL_FILES=$(git status --short | wc -l)
echo "Total: $TOTAL_FILES files"

# Verify no secrets will be committed
echo ""
echo -e "${BLUE}Checking for secrets...${NC}"
if git diff --cached | grep -q "xoxb-\|xapp-\|sk-ant-\|sk-proj-"; then
    echo -e "${YELLOW}⚠️  WARNING: Potential secrets detected in staged files!${NC}"
    echo "Please review and ensure .env is not being committed"
    read -p "Press Enter to continue anyway, or Ctrl+C to abort..."
else
    echo "✓ No secrets detected in staged files"
fi

# Step 5: Create commit
echo ""
echo -e "${BLUE}[5/7]${NC} Creating initial commit..."
git commit -m "Initial commit: AI-powered Slack Bot Assistant

Features:
- Full agent system with 15+ tools
- RAG knowledge base with ChromaDB
- MCP integrations (Slack, GitHub, Notion)
- Comprehensive test suite (11/11 passing)
- Complete documentation and learning materials
- Production-ready error handling and logging

See QUICK_START.md to get started."

echo "✓ Commit created"

# Step 6: Rename branch to main
echo ""
echo -e "${BLUE}[6/7]${NC} Renaming branch to main..."
git branch -M main
echo "✓ Branch renamed to main"

# Step 7: Add remote and push
echo ""
echo -e "${BLUE}[7/7]${NC} Adding remote and pushing to GitHub..."
REMOTE_URL="https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

# Check if remote already exists
if git remote | grep -q "origin"; then
    echo "Remote 'origin' already exists. Updating URL..."
    git remote set-url origin "$REMOTE_URL"
else
    git remote add origin "$REMOTE_URL"
fi

echo "Remote URL: $REMOTE_URL"
echo ""
echo "Pushing to GitHub..."
git push -u origin main

# Check if push was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo -e "${GREEN}✓ SUCCESS! Your project is now on GitHub!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo -e "Repository URL: ${GREEN}https://github.com/$GITHUB_USERNAME/$REPO_NAME${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Visit your repository on GitHub"
    echo "2. Add topics: slack-bot, ai-agent, langraph, python, anthropic"
    echo "3. Edit the repository description"
    echo "4. Consider adding a LICENSE file"
    echo "5. Enable GitHub Discussions (optional)"
    echo ""
else
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo -e "${YELLOW}⚠️  Push failed!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "Common issues:"
    echo "1. Repository doesn't exist on GitHub yet"
    echo "   → Create it first at https://github.com/new"
    echo ""
    echo "2. Wrong repository name"
    echo "   → Update REPO_NAME in this script"
    echo ""
    echo "3. Authentication required"
    echo "   → GitHub may prompt for username/password or token"
    echo "   → Use a Personal Access Token instead of password"
    echo "   → Create token at: https://github.com/settings/tokens"
    echo ""
    echo "4. Repository already exists with content"
    echo "   → Pull first: git pull origin main --allow-unrelated-histories"
    echo "   → Then push again"
    echo ""
fi
