#!/bin/bash

# Script to remove all branches except main
# Use this after you've already squashed your commits

echo "This will delete all local and remote branches except 'main'"
echo "Make sure you're on the main branch and have saved any important work!"
read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi

# Make sure we're on main branch
echo "Switching to main branch..."
git checkout main

# Step 1: Delete all local branches except main
echo "Deleting all local branches except main..."
branches_to_delete=$(git branch | grep -v "main" | grep -v "\*" | sed 's/^[ \t]*//')
if [ ! -z "$branches_to_delete" ]; then
    echo "Found local branches to delete:"
    echo "$branches_to_delete"
    for branch in $branches_to_delete; do
        echo "Deleting local branch: $branch"
        git branch -D "$branch"
    done
else
    echo "No additional local branches to delete."
fi

# Step 2: Clean up remote branches (optional)
echo "Do you want to delete all remote branches except main?"
read -p "Delete remote branches? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Fetching remote branches..."
    git fetch origin --prune
    
    # Get remote branches except main and HEAD
    remote_branches=$(git branch -r | grep -v "origin/main" | grep -v "origin/HEAD" | sed 's/origin\///' | sed 's/^[ \t]*//')
    
    if [ ! -z "$remote_branches" ]; then
        echo "Found remote branches to delete:"
        echo "$remote_branches"
        for branch in $remote_branches; do
            echo "Deleting remote branch: $branch"
            git push origin --delete "$branch"
        done
    else
        echo "No remote branches to delete."
    fi
    
    # Clean up remote tracking branches
    echo "Cleaning up remote tracking branches..."
    git remote prune origin
fi

echo ""
echo "Branch cleanup complete!"
echo "Remaining branches:"
git branch -a