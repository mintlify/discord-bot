#!/bin/bash
set -e

local_branch=$(git rev-parse --symbolic-full-name --abbrev-ref HEAD)
remote_branch=$(git rev-parse --abbrev-ref --symbolic-full-name @{u})
remote=$(git config branch.$local_branch.remote)

echo "Fetching from $remote..."
git fetch $remote

if git merge-base --is-ancestor $remote_branch HEAD; then
    echo 'Already up-to-date'
    exit 0
fi

if git merge-base --is-ancestor HEAD $remote_branch; then
    echo 'Fast-forward possible. Merging...'
    git merge --ff-only --stat $remote_branch
else
    echo 'Fast-forward not possible. Rebasing...'
    git rebase --preserve-merges --stat $remote_branch
fi
echo $remote_branch