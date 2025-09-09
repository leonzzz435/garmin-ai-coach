# Manual Git History Squash Commands

**WARNING: This will permanently remove all git history! Make sure you have a backup.**

## Method 1: Using Orphan Branch (Recommended)

```bash
# 1. Create a new orphan branch (no commit history)
git checkout --orphan temp-branch

# 2. Add all files to staging
git add -A

# 3. Create the first and only commit
git commit -m "Initial commit - squashed history"

# 4. Delete the old main branch
git branch -D main

# 5. Rename the current branch to main
git branch -m main

# 6. Force push to remote (optional, but will overwrite remote history)
git push -f origin main
```

## Method 2: Using Reset (Alternative)

```bash
# 1. Create a backup branch first
git branch backup-branch

# 2. Find the first commit hash
git log --oneline | tail -1

# 3. Reset to the first commit
git reset --soft <first-commit-hash>

# 4. Create a single commit with all changes
git commit -m "Initial commit - squashed history"

# 5. Force push to remote
git push -f origin main
```

## Method 3: Fresh Repository (Nuclear Option)

```bash
# 1. Remove git directory
rm -rf .git

# 2. Initialize new git repository
git init

# 3. Add all files
git add -A

# 4. Create initial commit
git commit -m "Initial commit"

# 5. Add remote (if you have one)
git remote add origin <your-remote-url>

# 6. Push to remote
git push -u origin main
```

## Quick One-Liner Commands

If you want to run everything at once (be very careful!):

```bash
# Backup first
git branch backup-$(date +%Y%m%d)

# Squash everything
git checkout --orphan temp-branch && git add -A && git commit -m "Initial commit - squashed history" && git branch -D main && git branch -m main

# Force push to remote (optional)
git push -f origin main
```

## Important Notes

1. **Always create a backup** of your repository before running these commands
2. **Force pushing** will overwrite the remote repository history - make sure all collaborators are aware
3. **This is irreversible** - once you delete the git history, it cannot be recovered
4. If you have collaborators, coordinate with them before doing this operation
5. Consider using [`git rebase -i`](https://git-scm.com/docs/git-rebase) for less destructive history rewriting

## Verification

After running the commands, verify the result:

```bash
# Check that you only have one commit
git log --oneline

# Check current branch
git branch

# Check if everything is staged properly
git status