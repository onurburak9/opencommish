#!/bin/bash
# Safe Git Wrapper for AI-Assisted Development
# Prevents accidental PR merges by AI agents
# 
# Installation:
#   Add to your ~/.bashrc or ~/.zshrc:
#   source /path/to/opencommish/scripts/safe-git.sh
#
# Or copy the gh() function directly into your shell config

# Wrapper for 'gh pr merge' that requires human confirmation
gh() {
    # Check if this is a PR merge command
    if [[ "$1" == "pr" && "$2" == "merge" ]]; then
        echo "⛔ Blocked: PR merging requires human approval"
        echo "   Run 'command gh pr merge' directly if you really want to merge"
        return 1
    fi
    
    # Pass through all other gh commands
    command gh "$@"
}

# Optional: Also block git push to main branch directly
# Uncomment if you want to enforce PR-based workflow
git() {
    # Check if trying to push to main/master directly
    if [[ "$1" == "push" && ( "$2" == "origin main" || "$2" == "origin master" ) ]]; then
        echo "⚠️  Warning: Pushing directly to $2"
        echo "   Consider using a PR workflow instead"
        read -p "   Continue anyway? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            echo "   Push cancelled"
            return 1
        fi
    fi
    
    # Pass through all other git commands
    command git "$@"
}

echo "🔒 Safe git wrappers loaded. PR merges are protected."
