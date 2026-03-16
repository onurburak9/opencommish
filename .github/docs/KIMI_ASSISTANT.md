# Kimi K2.5 GitHub Actions Assistant

This GitHub Actions workflow allows you to interact with Kimi K2.5 AI directly from GitHub issues and pull requests.

## Usage

Simply mention `@kimi` in any issue, PR, or comment followed by your request:

```
@kimi Please analyze the test failures in this PR and suggest fixes.
```

```
@kimi Create a new feature to add player trade suggestions based on stats.
```

```
@kimi Run the tests and report back the results.
```

## What Kimi Can Do

### 1. Read and Analyze Code
```
@kimi Read the dashboard/app.py file and explain how the fantasy points calculation works.
```

### 2. Run Tests
```
@kimi Run the unit tests and tell me if they pass.
```

### 3. Create PRs with Changes
```
@kimi Fix the bug in the daily stats collection and create a PR.
```

### 4. Answer Questions
```
@kimi How does the projected stats scraping work?
```

## Configuration

### Required Secrets

Add these secrets to your repository (Settings → Secrets and variables → Actions):

| Secret | Description | Required |
|--------|-------------|----------|
| `GITHUB_TOKEN` | Auto-provided by GitHub | ✅ Yes |
| `KIMI_API_KEY` | Moonshot API key for direct API access | ⚠️ Optional |
| `OPENCLAW_GATEWAY_URL` | Your OpenClaw gateway URL | ⚠️ Optional |
| `OPENCLAW_GATEWAY_TOKEN` | Token for OpenClaw gateway auth | ⚠️ Optional |

### Setup Options

#### Option A: Moonshot API (Direct)
1. Get an API key from [Moonshot AI](https://platform.moonshot.cn/)
2. Add `KIMI_API_KEY` to repository secrets

#### Option B: OpenClaw Gateway (Self-hosted)
1. Set up your own OpenClaw gateway
2. Add `OPENCLAW_GATEWAY_URL` and `OPENCLAW_GATEWAY_TOKEN` secrets

#### Option C: Local Mode (No AI)
If no API is configured, the action will respond with instructions on how to set it up.

## Safety Features

The Kimi assistant has built-in safety restrictions:

### ✅ Allowed Operations
- Read files from the repository
- Run tests (`pytest`)
- Create new branches (`kimi/*`)
- Create pull requests
- Run safe git commands
- Comment on issues/PRs

### ❌ Blocked Operations
- Force push (`git push -f`)
- Reset hard (`git reset --hard`)
- Delete protected branches (`main`, `master`)
- Modify `.github/workflows/` files directly
- Delete the `.git` directory
- Any command with output redirection (`>`, `>>`)

### 🔒 Protected Paths
These paths cannot be modified directly:
- `.github/workflows/*`
- `.github/scripts/*`
- `SECURITY.md`
- `LICENSE`

All changes to protected files must go through a pull request review.

## Examples

### Debugging Test Failures
```
@kimi The tests are failing in this PR. Can you investigate and fix them?
```

Kimi will:
1. Read the test files
2. Run the tests
3. Analyze the failures
4. Create a fix branch
5. Open a PR with the fixes

### Adding New Features
```
@kimi Add a new endpoint to fetch weekly matchup predictions.
```

Kimi will:
1. Analyze the existing code structure
2. Create a new branch
3. Implement the feature
4. Run tests to verify
5. Create a PR with documentation

### Code Review
```
@kimi Review this PR and suggest improvements.
```

Kimi will:
1. Analyze the changed files
2. Check for common issues
3. Suggest improvements
4. Comment on the PR

## Troubleshooting

### Action Doesn't Trigger
- Make sure you mention `@kimi` (case insensitive)
- Check that the workflow file is in `.github/workflows/`
- Verify the issue/PR has the correct permissions

### API Errors
- Check that your API key is valid
- Verify the `OPENCLAW_GATEWAY_URL` is accessible
- Check the action logs for detailed error messages

### Safety Errors
- Kimi will report which command was blocked and why
- All changes to protected paths must go through PRs
- Create an issue if you need to modify protected files

## Architecture

```
GitHub Issue/PR
       │
       ▼
GitHub Actions Trigger (on: issues/issue_comment)
       │
       ▼
kimi-assistant.yml
       │
       ▼
kimi_handler.py
   ┌───┴───┐
   │       │
   ▼       ▼
Safety   Context
Checks   Gathering
   │       │
   └───┬───┘
       ▼
  Kimi API / OpenClaw
       │
       ▼
  Action Execution
       │
       ▼
  PR / Comment
```

## Security Considerations

1. **Token Permissions**: The action uses minimal permissions:
   - `contents: read` - Read codebase
   - `issues: write` - Comment on issues
   - `pull-requests: write` - Create PRs and comments

2. **Command Sandboxing**: All commands are checked against an allowlist

3. **No Direct Main Push**: All changes go through PRs

4. **Audit Trail**: All Kimi actions are logged in GitHub Actions

## Customization

You can modify the behavior by editing `.github/scripts/kimi_handler.py`:

- Add new action types in `_execute_actions()`
- Modify safety rules in `is_safe_command()`
- Add new protected paths in `PROTECTED_PATHS`
- Customize the prompt template in `_build_prompt()`

## Contributing

To improve the Kimi assistant:

1. Test your changes in a fork
2. Create a PR with your improvements
3. Tag `@kimi` to test the new functionality!
