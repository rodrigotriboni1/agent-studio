# Vault plan — agent-studio

## Loop instructions (ralph)

Each iteration executes **exactly one** subtask and stops. Do not chain.

1. Find the first unchecked `[ ]` subtask (recurse into `task/NN.md` links).
   If none remain anywhere → create `plan/stop.md` and stop.
2. Execute that single subtask, then mark it `[x]`.
   - Documentation subtask: follow the referenced prompt under
     `<skill>/assets/prompts/` against the named repo, write into the vault,
     then run `gv.py validate` before marking done.
   - Graph subtask (relations/components/dependencies): runs **after** all repo
     tasks; follow its prompt across the registered repos, write into the matching
     tier, then run `gv.py validate` before marking done.
3. Stop. Do not look for the next subtask.


## Tasks

- [ ] agent-studio (bootstrap) → task/01.md
- [ ] dependencies (graph) → task/02.md
