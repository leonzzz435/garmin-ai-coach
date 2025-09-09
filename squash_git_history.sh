#!/bin/bash

# Script to squash all commits into one and remove git history
# WARNING: This will permanently remove all git history!

echo "WARNING: This will permanently remove all git history!"
echo "Make sure you have a backup of your repository before proceeding."
read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi

# Step 1: Create a new orphan branch (no commit history)
echo "Creating orphan branch..."
git checkout --orphan temp-branch

# Step 2: Add all files to staging
echo "Adding all files..."
git add -A

# Step 3: Create the first and only commit
echo "Creating single commit..."
git commit -m "Initial commit - squashed history"

# Step 4: Delete the old main branch
echo "Deleting old main branch..."
git branch -D main

# Step 5: Rename the current branch to main
echo "Renaming branch to main..."
git branch -m main

# Step 6: Force push to remote (if you have a remote)
echo "Do you want to force push to remote origin? This will overwrite the remote repository!"
read -p "Force push to remote? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Force pushing to remote..."
    git push -f origin main
    echo "Done! All git history has been squashed into one commit."
else
    echo "Local git history has been squashed. Remote repository unchanged."
    echo "To update remote later, run: git push -f origin main"
fi

echo "Git history cleanup complete!"