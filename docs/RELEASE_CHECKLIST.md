# Release checklist

Status is recorded against `main` at commit `82723c9`. A gate is marked done only when a command was run and its result recorded here.

## Gates

| # | Gate | Command | Status at 82723c9 |
| --- | --- | --- | --- |
| 1 | Python suite | `env -u MODEL_API_KEY -u OPENAI_API_KEY -u UPSTASH_REDIS_REST_URL -u UPSTASH_REDIS_REST_TOKEN .venv/bin/python -m pytest -q -p no:cacheprovider` | Passed: 676 tests, 4 subtests, exit 0 |
| 2 | Frontend tests | `cd frontend && npm test` | Passed: 146 tests, 0 failures |
| 3 | Type check and build | `cd frontend && npm run build` | Passed: exit 0 (chunk-size warning only) |
| 4 | Secret scan of the bundle | search `frontend/dist` for server secret values | Passed in the earlier release; re-run before each release |
| 5 | Kill switch | `scripts/run_muse_studio_live.py source` with no flags | Exits 2 (paid path closed) |
| 6 | Git hygiene | `git status`; no `.env` or `.vercel/` tracked | Clean for tracked files; untracked local directories are not committed |
| 7 | Production deploy | prebuilt deploy under the team owner's token | Deployed `854RRwAdx5tka5HLwCUBHknzxrbv`, READY |
| 8 | Production smoke | `/` 200, recorded trace JSON 200, API routes 501 on GET | Passed |
| 9 | Browser acceptance | manual check on the deployed origin | Not performed; no browser automation here |

## Deployment notes

- Git-triggered deployments of commits authored by `noreply@codebuff.com` are blocked by Vercel's commit-author check (the team is on Pro, the owner is `ratulc-7916`).
- The release was made as a prebuilt upload from the local tree at `82723c9`. It is not linked to a Git commit in Vercel. Rollback reference: `dpl_F1An4wLdwavjZko1eZimhd3AySzM`.
- Do not change the commit author, repository visibility or plan without the owner's approval.

## Before each release

1. Run gates 1 to 5.
2. Confirm the commit to deploy is pushed to `main` through `cloud_git`.
3. Deploy with the owner's token; never redeploy duplicates.
4. Run gate 8 on the deployed alias.
5. Record the deployment id and commit in `docs/FINAL_ACCEPTANCE_LEDGER.md`.
