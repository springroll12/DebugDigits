# GitHub CI Plugins

Python-based GitHub CI plugins that automatically run tests and enforce code style standards on every pull request.

## Features

- Automatically runs tests on new pull requests and when PRs are updated
- Enforces code style standards using flake8, black, isort, and ruff
- Posts test results and style violations as comments on the PR
- Creates GitHub check runs to show test and style check status
- Supports custom test commands
- Generates detailed HTML test reports
- Parses test output to provide structured results

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure the GitHub workflow file is in the `.github/workflows` directory.

3. Ensure your repository has the necessary GitHub secrets configured.

## Manual Usage

### Test Runner

You can run the test plugin manually:

```bash
python github_ci_plugin.py \
  --token "your_github_token" \
  --repo "owner/repo" \
  --pr 123 \
  --test-command "python -m unittest discover" \
  --report-dir "/path/to/save/reports"
```

Required parameters:
- `--pr NUMBER`: The pull request number to process

Optional parameters:
- `--report-dir PATH`: Directory to save the HTML test report (default: auto-generated temp directory)

### Code Style Checker

You can run the code style checker manually:

```bash
python code_style_checker.py \
  --token "your_github_token" \
  --repo "owner/repo" \
  --pr 123
```

Required parameters:
- `--pr NUMBER`: The pull request number to process

## Configuration

The default workflow runs the Python unittest discovery. To customize the tests that are run, modify the `--test-command` parameter in the `.github/workflows/run_tests.yml` file.

## License

MIT
