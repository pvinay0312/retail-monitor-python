#!/bin/bash
# One-command deploy to Railway + push to GitHub
# Run: bash deploy.sh

set -e

RAILWAY="$HOME/.local/bin/railway"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===================================="
echo "  Retail Monitor — Deploy Script"
echo "===================================="
echo ""

# ── Step 1: GitHub ────────────────────────────────────────────────────────────
echo "📦 Step 1: Push to GitHub"
echo "   Enter your GitHub username (or press Enter to skip):"
read -r GH_USER

if [ -n "$GH_USER" ]; then
    REPO_NAME="retail-monitor-python"
    echo "   Creating GitHub repo: $GH_USER/$REPO_NAME"
    echo "   (You'll need a Personal Access Token with 'repo' scope)"
    echo "   Get one at: https://github.com/settings/tokens/new"
    echo ""
    read -rsp "   GitHub PAT (hidden): " GH_TOKEN
    echo ""

    cd "$PROJECT_DIR"
    # Create repo via API
    curl -s -X POST "https://api.github.com/user/repos" \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -d "{\"name\":\"$REPO_NAME\",\"private\":false,\"description\":\"24/7 Discord retail monitor — Amazon, Best Buy, Walmart, Target, Nike SNKRS, Footsites\"}" \
        | python3 -c "import sys,json; r=json.load(sys.stdin); print('  Repo URL:', r.get('html_url', r.get('message','')))"

    git remote add origin "https://$GH_TOKEN@github.com/$GH_USER/$REPO_NAME.git" 2>/dev/null || \
        git remote set-url origin "https://$GH_TOKEN@github.com/$GH_USER/$REPO_NAME.git"
    git push -u origin main
    echo "  ✅ Pushed to GitHub!"
fi

echo ""

# ── Step 2: Railway ───────────────────────────────────────────────────────────
echo "🚂 Step 2: Deploy to Railway"
echo "   You'll be prompted to open a browser to log in."
echo ""

cd "$PROJECT_DIR"

# Login
$RAILWAY login

# Create new project and deploy
$RAILWAY init --name "retail-monitor-python"
$RAILWAY up --detach

echo ""
echo "✅ Deployed to Railway!"
echo ""
echo "===================================="
echo "  Next: Set environment variables"
echo "===================================="
echo ""
echo "Run these commands (replace ... with your actual webhook URLs):"
echo ""
echo "  $RAILWAY vars set AMAZON_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set BESTBUY_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set WALMART_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set TARGET_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set FOOTSITES_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set NIKE_SNKRS_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set UPCOMING_DROPS_WEBHOOK_URL=https://discord.com/api/webhooks/..."
echo "  $RAILWAY vars set COOK_GROUP_NAME=\"Your Group Name\""
echo "  $RAILWAY vars set COOK_GROUP_ICON_URL=\"https://...\""
echo ""
echo "Then Railway will auto-redeploy with the new vars."
echo ""
echo "  View logs:    $RAILWAY logs"
echo "  Open dashboard: $RAILWAY open"
