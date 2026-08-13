# Public repository checklist

Before pushing a public release branch:

- Run `python scripts/check_public_repo.py`.
- Run the Python and frontend syntax checks documented in `README.md`.
- Confirm `.env`, logs, virtual environments, models and generated audio are untracked.
- Review `git diff --check` and `git status --short`.
- Choose and add a project `LICENSE` before describing the repository as open source.
- Include the ACE-Step, Gemma and all other third-party license notices in release artifacts.
- Keep model weights outside Git. Download them from their authorized upstream sources.
- Review Git history before publishing. Rewriting history changes commit IDs and must be done deliberately.
- Do not publish a release package until it has been tested from a clean Windows or Linux account.

The repository defaults to loopback addresses. Remote services must be configured explicitly with
environment variables described in `.env.example`.
