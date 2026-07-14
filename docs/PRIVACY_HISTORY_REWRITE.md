# Privacy history rewrite runbook

This is a coordinated repository-administration operation, not a normal code
change. Run it only after the privacy-containment pull request has been reviewed
and merged. It rewrites commit IDs on every branch and tag.

## Preconditions

1. Freeze merges and ask every collaborator to stop pushing.
2. Confirm the default branch contains the synthetic resume fixtures and no
   tracked E2E screenshots, test traces, videos, reports, or databases.
3. Record the affected paths without copying their contents into tickets, chat,
   logs, or screenshots.
4. Ensure an owner can temporarily update branch protection and force-push all
   branches and tags.
5. Save the synthetic versions of these two files outside the mirror clone so
   they can be restored after their historical paths are removed:
   - `agentception/evals/golden/resume_text.txt`
   - `agentception/evals/golden/resume_parses.json`

Do not create a broadly shared backup of the pre-rewrite repository. If incident
response policy requires a backup, keep it encrypted, access-restricted, and
assign a deletion date.

## Rewrite in a fresh mirror clone

Verify the installed command before using it:

```powershell
git filter-repo --version
```

Create a fresh mirror clone in a dedicated maintenance directory, then remove
the private artifacts from every ref:

```powershell
git clone --mirror https://github.com/arun3676/agentception.git agentception-history-rewrite.git
Set-Location agentception-history-rewrite.git

git filter-repo --force --invert-paths `
  --path agentception/e2e/screenshots `
  --path data/agentception.db `
  --path agentception/evals/golden/resume_text.txt `
  --path agentception/evals/golden/resume_parses.json
```

`git filter-repo` removes the `origin` remote as a safety measure. Before
publishing, use a normal working clone of the rewritten bare repository to
restore the two synthetic golden files saved during preflight:

```powershell
Set-Location ..
git clone .\agentception-history-rewrite.git restore-worktree
Set-Location restore-worktree
# Copy only the two preflight synthetic files back to their original paths.
git add agentception/evals/golden/resume_text.txt `
        agentception/evals/golden/resume_parses.json
git commit -m "Restore synthetic resume fixtures after privacy rewrite"
git push origin master
Set-Location ..\agentception-history-rewrite.git
```

## Verify before pushing

Run all of the following against the rewritten repository:

```powershell
python agentception/scripts/check_repository_privacy.py --history
git fsck --full --no-reflogs --unreachable
git log --all -- agentception/e2e/screenshots data/agentception.db
```

The privacy checker must pass. The final `git log` command must print no commits.
Also run the normal backend, frontend, and evaluation checks before publishing
the rewritten refs.

## Publish during the maintenance window

After a second owner reviews the verification output:

```powershell
git remote add origin https://github.com/arun3676/agentception.git
git push --force --all origin
git push --force --tags origin
```

Do not use `git push --mirror`: it can attempt to overwrite provider-managed
refs. Restore branch protection immediately after the push.

## Aftercare

- Close or recreate pull requests whose commits still point to old history.
- Ask every collaborator to delete the old clone and clone again; rebasing an
  old branch can reintroduce the removed objects.
- Inspect GitHub Actions artifacts, releases, PR attachments, forks, deployment
  artifacts, and external caches for copies.
- Contact GitHub support if cached pull-request objects remain publicly
  reachable after all repository refs are clean.
- Review Railway, Vercel, and provider logs. Rotate a credential only when logs
  show that a complete value was exposed or used unexpectedly.
- Record the affected person's contact-data notification/monitoring decision in
  a private incident record, not in this repository.
