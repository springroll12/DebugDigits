# DebugDigits
2025 Hack-a-thon - Debug Digits

### Task
Using [Aider](https://github.com/Aider-AI/aider) and [Anthropic's Claude](https://docs.anthropic.com/en/home), build out a CLI tool integrated with GitHub PRs that can perform a variaty of review tasks (Code quality, Security, [OWASP Compliance](https://owasp-aasvs.readthedocs.io/en/latest/level3.html), etc...).

### Notes
- Should stick with Python3 to keep everyone's work compatible (Claude seemed to favor Python3 for CLI code generation)
- aider --model sonnet --api-key anthropic={API_KEY}
- You'll need to share your Github user account to be added as a contributor to this repository

### Credentials
I've setup an Anthropic account. I can share the credentials with the team so we don't all need to sign up for individual accounts.

### Folders
aider_sandboxes : Aider seems to only read from within the folder you execute it. To avoid stepping on toes during dev, you can create a folder here to run your tests while still using source control.
project : main project to integrate with github PR and execute review plugins
plugins : various review plugins
