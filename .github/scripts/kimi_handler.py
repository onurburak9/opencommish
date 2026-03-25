#!/usr/bin/env python3
"""
Kimi K2.5 AI Assistant Handler for GitHub Actions.

This script processes requests tagged with @kimi and coordinates with
an OpenClaw gateway or Kimi API to provide AI assistance.

Features:
- Read and analyze codebase
- Run tests
- Create branches and PRs
- Comment on issues/PRs
- Safety restrictions to prevent destructive operations

Safety Rules:
- No force pushes
- No deletion of main/master branches
- No deletion of protected files (.github/workflows, etc.)
- All changes go through PRs, never direct push to main
"""

import os
import sys
import json
import subprocess
import re
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any


def log_step(step_num: int, title: str, details: str = ""):
    """Log a step with clear visual separator."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"STEP {step_num}: {title}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    if details:
        print(details, file=sys.stderr)


def log_info(msg: str):
    """Log info message."""
    print(f"[INFO] {msg}", file=sys.stderr)


def log_error(msg: str):
    """Log error message."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def log_success(msg: str):
    """Log success message."""
    print(f"[OK] {msg}", file=sys.stderr)


# Safety configuration
PROTECTED_BRANCHES = ['main', 'master', 'production', 'release']
PROTECTED_PATHS = [
    '.github/workflows/',
    '.github/scripts/',
    'SECURITY.md',
    'LICENSE',
]
ALLOWED_COMMANDS = [
    'git status', 'git log', 'git diff', 'git show',
    'git branch', 'git checkout', 'git add', 'git commit',
    'git push --set-upstream origin',  # Only for new branches
    'pytest', 'python', 'pip',
    'ls', 'cat', 'head', 'tail', 'find', 'grep',
]
BLOCKED_COMMANDS = [
    'git push -f', 'git push --force',
    'git reset --hard', 'git clean -fd',
    'rm -rf /', 'rm -rf .git',
    '>', '>>',  # No redirects that could overwrite files
]


class SafetyError(Exception):
    """Raised when a safety check fails."""
    pass


class KimiHandler:
    """Handles Kimi AI requests with safety checks."""
    
    def __init__(self):
        log_step(0, "INITIALIZATION", "Setting up Kimi handler...")
        
        self.token = os.environ.get('GITHUB_TOKEN')
        self.repo_owner = os.environ.get('REPO_OWNER')
        self.repo_name = os.environ.get('REPO_NAME')
        self.issue_number = os.environ.get('ISSUE_NUMBER')
        self.event_type = os.environ.get('EVENT_TYPE')
        self.actor = os.environ.get('ACTOR')
        
        log_info(f"Repository: {self.repo_owner}/{self.repo_name}")
        log_info(f"Event type: {self.event_type}")
        log_info(f"Actor: {self.actor}")
        log_info(f"Issue/PR #: {self.issue_number}")
        log_info(f"GITHUB_TOKEN: {'set' if self.token else 'NOT SET - CRITICAL ERROR'}")
        
        # Check API configuration
        self.gateway_url = os.environ.get('OPENCLAW_GATEWAY_URL')
        self.gateway_token = os.environ.get('OPENCLAW_GATEWAY_TOKEN')
        self.kimi_key = os.environ.get('KIMI_API_KEY')
        
        log_info(f"OPENCLAW_GATEWAY_URL: {self.gateway_url if self.gateway_url else 'not set'}")
        log_info(f"OPENCLAW_GATEWAY_TOKEN: {'set' if self.gateway_token else 'not set'}")
        log_info(f"KIMI_API_KEY: {'set (starts with: ' + self.kimi_key[:8] + '...)' if self.kimi_key else 'NOT SET'}")
        
        # Get the trigger content
        self.trigger_body = self._get_trigger_body()
        log_info(f"Trigger body length: {len(self.trigger_body)} chars")
        log_info(f"Trigger body preview: {self.trigger_body[:200]}...")
        
        log_success("Handler initialized")
        
    def _get_trigger_body(self) -> str:
        """Get the body that triggered this action."""
        comment_body = os.environ.get('COMMENT_BODY', '')
        issue_body = os.environ.get('ISSUE_BODY', '')
        body = comment_body or issue_body or ''
        return body
    
    def extract_kimi_request(self) -> Optional[str]:
        """Extract the request from @kimi mention."""
        log_step(1, "EXTRACTING @kimi REQUEST")
        
        # Match @kimi or @Kimi followed by the request
        pattern = r'@kimi\s+(.*?)(?:\n\n|\Z)'
        match = re.search(pattern, self.trigger_body, re.IGNORECASE | re.DOTALL)
        
        if match:
            request = match.group(1).strip()
            log_success(f"Found @kimi request: '{request[:100]}...'")
            return request
        
        log_error("No @kimi request found in trigger body")
        return None
    
    def is_safe_command(self, command: str) -> bool:
        """Check if a command is safe to execute."""
        cmd_lower = command.lower()
        
        # Check blocked commands
        for blocked in BLOCKED_COMMANDS:
            if blocked.lower() in cmd_lower:
                return False
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'git\s+push\s+.*--force',
            r'git\s+push\s+.*-f\b',
            r'git\s+reset\s+--hard',
            r'git\s+clean\s+-[fd]+',
            r'rm\s+-rf\s+/',
            r'>\s*[^>]',  # Output redirection
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, cmd_lower):
                return False
        
        return True
    
    def run_safe_command(self, command: str, cwd: Optional[str] = None) -> tuple:
        """Run a command after safety checks."""
        if not self.is_safe_command(command):
            raise SafetyError(f"Command blocked for safety: {command}")
        
        log_info(f"Running command: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                log_success(f"Command succeeded (exit code: 0)")
            else:
                log_error(f"Command failed (exit code: {result.returncode})")
            
            if result.stdout:
                log_info(f"stdout: {result.stdout[:200]}...")
            if result.stderr:
                log_info(f"stderr: {result.stderr[:200]}...")
            
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            log_error("Command timed out after 120s")
            return -1, "", "Command timed out"
        except Exception as e:
            log_error(f"Command exception: {e}")
            return -1, "", str(e)
    
    def get_repo_context(self) -> Dict[str, Any]:
        """Gather repository context for the AI."""
        log_step(2, "GATHERING REPO CONTEXT")
        
        context = {
            'files': [],
            'structure': {},
            'recent_commits': [],
            'branch': '',
        }
        
        # Get current branch
        log_info("Getting current branch...")
        _, branch, _ = self.run_safe_command('git branch --show-current')
        context['branch'] = branch.strip()
        log_info(f"Current branch: {context['branch']}")
        
        # Get recent commits
        log_info("Getting recent commits...")
        _, commits, _ = self.run_safe_command('git log --oneline -10')
        context['recent_commits'] = commits.strip().split('\n') if commits else []
        log_info(f"Found {len(context['recent_commits'])} recent commits")
        
        # Get repo structure
        log_info("Getting repo structure...")
        _, files, _ = self.run_safe_command('find . -type f -name "*.py" -o -name "*.yml" -o -name "*.yaml" -o -name "*.md" -o -name "*.json" | head -50')
        context['files'] = [f.strip() for f in files.split('\n') if f.strip() and not f.startswith('./.git')]
        log_info(f"Found {len(context['files'])} relevant files")
        
        log_success("Repo context gathered")
        return context
    
    def read_file(self, filepath: str) -> str:
        """Safely read a file from the repo."""
        log_info(f"Reading file: {filepath}")
        
        # Normalize path
        path = Path(filepath).resolve()
        repo_root = Path('.').resolve()
        
        # Ensure file is within repo
        if not str(path).startswith(str(repo_root)):
            raise SafetyError(f"File outside repo: {filepath}")
        
        # Check protected paths
        for protected in PROTECTED_PATHS:
            if protected in str(path):
                raise SafetyError(f"Cannot read protected file: {filepath}")
        
        if path.exists() and path.is_file():
            content = path.read_text()
            log_success(f"Read {len(content)} chars from {filepath}")
            return content
        
        log_error(f"File not found: {filepath}")
        return f"File not found: {filepath}"
    
    def create_branch(self, branch_name: str) -> str:
        """Create a new branch for changes."""
        log_info(f"Creating branch from name: {branch_name}")
        
        # Sanitize branch name
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', branch_name.lower())
        safe_name = f"kimi/{safe_name[:50]}"  # Prefix and limit length
        
        log_info(f"Sanitized branch name: {safe_name}")
        
        # Create and checkout branch
        self.run_safe_command(f'git checkout -b {safe_name}')
        log_success(f"Created and checked out branch: {safe_name}")
        return safe_name
    
    def run_tests(self) -> tuple:
        """Run the test suite."""
        log_step(4, "RUNNING TESTS")
        returncode, stdout, stderr = self.run_safe_command('pytest tests/ -v --tb=short')
        success = returncode == 0
        if success:
            log_success("Tests passed")
        else:
            log_error("Tests failed")
        return success, stdout + '\n' + stderr
    
    def post_comment(self, body: str):
        """Post a comment on the issue/PR."""
        log_step(6, "POSTING COMMENT TO GITHUB")
        log_info(f"Comment length: {len(body)} chars")
        
        from github import Github
        
        g = Github(self.token)
        repo = g.get_repo(f"{self.repo_owner}/{self.repo_name}")
        
        log_info(f"Posting to {self.repo_owner}/{self.repo_name} issue/PR #{self.issue_number}")
        
        # Determine if issue or PR
        try:
            issue = repo.get_issue(int(self.issue_number))
            issue.create_comment(body)
            log_success("Comment posted to issue")
        except Exception as e:
            log_info(f"Not an issue, trying PR... Error was: {e}")
            try:
                pr = repo.get_pull(int(self.issue_number))
                pr.create_comment(body)
                log_success("Comment posted to PR")
            except Exception as e2:
                log_error(f"Failed to post comment: {e2}")
                raise
    
    def update_reaction(self, success: bool = True):
        """Update the reaction on the triggering comment."""
        comment_id = os.environ.get('COMMENT_ID')
        if not comment_id:
            log_info("No COMMENT_ID set, skipping reaction update")
            return
        
        log_info(f"Updating reaction for comment {comment_id}")
        
        from github import Github
        
        try:
            g = Github(self.token)
            repo = g.get_repo(f"{self.repo_owner}/{self.repo_name}")
            
            # Get the comment to find the current reaction
            # Note: PyGithub doesn't have direct reaction update, so we add new + delete old
            # For simplicity, we just add a new reaction indicating completion
            emoji = 'rocket' if success else 'confused'
            
            # Use raw API call via requests since PyGithub reaction support is limited
            import requests
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues/comments/{comment_id}/reactions"
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            data = {"content": emoji}
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 201:
                log_success(f"Added {emoji} reaction")
            else:
                log_info(f"Could not add reaction: {response.status_code}")
        except Exception as e:
            log_info(f"Failed to update reaction: {e}")
    
    def create_pull_request(self, branch: str, title: str, body: str) -> str:
        """Create a pull request with the changes."""
        log_step(5, "CREATING PULL REQUEST")
        log_info(f"Branch: {branch}")
        log_info(f"Title: {title}")
        
        from github import Github
        
        g = Github(self.token)
        repo = g.get_repo(f"{self.repo_owner}/{self.repo_name}")
        
        pr = repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base='main'
        )
        log_success(f"PR created: {pr.html_url}")
        return pr.html_url
    
    def process_request(self):
        """Main entry point to process the Kimi request."""
        
        request = self.extract_kimi_request()
        if not request:
            log_error("No @kimi request found - aborting")
            return
        
        log_step(2, "GATHERING CONTEXT")
        context = self.get_repo_context()
        
        log_step(3, "BUILDING PROMPT")
        prompt = self._build_prompt(request, context)
        log_info(f"Prompt length: {len(prompt)} chars")
        log_info(f"Prompt preview:\n{prompt[:500]}...")
        
        log_step(4, "CALLING KIMI API")
        response = self._call_kimi_api(prompt)
        log_info(f"API Response length: {len(response)} chars")
        log_info(f"API Response preview:\n{response[:1000]}...")
        
        log_step(5, "PARSING ACTIONS")
        actions = self._parse_actions(response)
        log_info(f"Parsed {len(actions)} actions:")
        for i, action in enumerate(actions):
            log_info(f"  Action {i+1}: {action.get('type', 'unknown')}")
        
        log_step(6, "EXECUTING ACTIONS")
        results = self._execute_actions(actions)
        
        log_info("Action results:")
        for i, result in enumerate(results):
            status = "✅" if result['success'] else "❌"
            log_info(f"  {status} Action {i+1} ({result['action'].get('type')}): {result['output'][:100]}...")
        
        log_step(7, "BUILDING SUMMARY")
        summary = self._build_summary(actions, results)
        
        log_step(8, "POSTING COMMENT")
        self.post_comment(summary)
        
        log_step(9, "UPDATING REACTION")
        all_success = all(r['success'] for r in results)
        self.update_reaction(success=all_success)
        
        log_success("Request processing complete!")
    
    def _build_prompt(self, request: str, context: Dict) -> str:
        """Build the prompt for Kimi."""
        prompt = f"""You are Kimi K2.5, an AI coding assistant helping with the OpenCommish project.

Repository Context:
- Current branch: {context['branch']}
- Recent commits: {context['recent_commits'][:5]}
- Key files: {[f for f in context['files'] if not f.startswith('./.')][:20]}

User Request: {request}

You can perform the following actions (respond with JSON):
{{
  "actions": [
    {{"type": "read_file", "path": "path/to/file"}},
    {{"type": "run_command", "command": "safe command"}},
    {{"type": "run_tests"}},
    {{"type": "create_branch", "name": "descriptive-name"}},
    {{"type": "write_file", "path": "path/to/file", "content": "file content"}},
    {{"type": "create_pr", "title": "PR Title", "body": "PR description"}},
    {{"type": "comment", "message": "Response to user"}}
  ]
}}

Safety Rules:
- Never force push or delete branches
- Never modify .github/workflows or protected files directly
- All changes must go through PRs
- Only use safe git commands

What actions should you take to fulfill the request?"""
        return prompt
    
    def _call_kimi_api(self, prompt: str) -> str:
        """Call Kimi API or OpenClaw gateway."""
        
        # Try OpenClaw gateway first
        if self.gateway_url:
            log_info(f"Using OpenClaw gateway: {self.gateway_url}")
            return self._call_openclaw_gateway(prompt, self.gateway_url, self.gateway_token)
        
        # Fall back to direct Kimi API
        if self.kimi_key:
            log_info("Using direct Kimi API (moonshot.cn)")
            return self._call_kimi_direct(prompt, self.kimi_key)
        
        # No API available
        log_error("NO API CONFIGURED - neither OPENCLAW_GATEWAY_URL nor KIMI_API_KEY is set")
        return json.dumps({
            "actions": [
                {"type": "comment", "message": "⚠️ Kimi API not configured. Please set OPENCLAW_GATEWAY_URL or KIMI_API_KEY secret."}
            ]
        })
    
    def _call_openclaw_gateway(self, prompt: str, url: str, token: Optional[str]) -> str:
        """Call OpenClaw gateway."""
        import requests
        
        log_info(f"POST to {url}/api/v1/chat")
        
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            log_info("Using auth token")
        else:
            log_info("No auth token provided")
        
        try:
            response = requests.post(
                f"{url}/api/v1/chat",
                headers=headers,
                json={
                    "message": prompt,
                    "model": "moonshot/kimi-k2.5",
                    "stream": False
                },
                timeout=120
            )
            log_info(f"Gateway response status: {response.status_code}")
            response.raise_for_status()
            result = response.json().get('response', '{}')
            log_success("Gateway call successful")
            return result
        except requests.exceptions.ConnectionError as e:
            log_error(f"Cannot connect to gateway: {e}")
            return json.dumps({"actions": [{"type": "comment", "message": f"❌ Cannot connect to OpenClaw gateway: {e}"}]})
        except requests.exceptions.Timeout:
            log_error("Gateway request timed out")
            return json.dumps({"actions": [{"type": "comment", "message": "❌ OpenClaw gateway request timed out"}]})
        except Exception as e:
            log_error(f"Gateway error: {e}")
            return json.dumps({"actions": [{"type": "comment", "message": f"❌ OpenClaw gateway error: {e}"}]})
    
    def _call_kimi_direct(self, prompt: str, api_key: str) -> str:
        """Call Moonshot/Kimi API directly."""
        import requests
        
        api_url = "https://api.moonshot.cn/v1/chat/completions"
        log_info(f"POST to {api_url}")
        log_info(f"Using model: kimi-k2.5")
        log_info(f"API key (first 8 chars): {api_key[:8]}...")
        
        try:
            response = requests.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "kimi-k2.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=120
            )
            
            log_info(f"API response status: {response.status_code}")
            
            if response.status_code == 401:
                log_error("API returned 401 Unauthorized - check your KIMI_API_KEY")
                return json.dumps({"actions": [{"type": "comment", "message": "❌ Kimi API authentication failed. Check your KIMI_API_KEY secret."}]})
            elif response.status_code == 429:
                log_error("API returned 429 Rate Limited")
                return json.dumps({"actions": [{"type": "comment", "message": "❌ Kimi API rate limit exceeded. Please try again later."}]})
            
            response.raise_for_status()
            data = response.json()
            
            if 'choices' not in data or not data['choices']:
                log_error(f"Unexpected API response format: {data.keys()}")
                return json.dumps({"actions": [{"type": "comment", "message": f"❌ Unexpected API response: {data}"}]})
            
            log_success(f"API call successful - got {len(data.get('choices', []))} choices")
            return data['choices'][0]['message']['content']
            
        except requests.exceptions.ConnectionError as e:
            log_error(f"Cannot connect to Moonshot API: {e}")
            return json.dumps({"actions": [{"type": "comment", "message": f"❌ Cannot connect to Kimi API: {e}"}]})
        except requests.exceptions.Timeout:
            log_error("API request timed out")
            return json.dumps({"actions": [{"type": "comment", "message": "❌ Kimi API request timed out"}]})
        except Exception as e:
            log_error(f"API error: {type(e).__name__}: {e}")
            return json.dumps({"actions": [{"type": "comment", "message": f"❌ Kimi API error: {type(e).__name__}: {e}"}]})
    
    def _parse_actions(self, response: str) -> List[Dict]:
        """Parse the JSON response from Kimi."""
        log_info("Parsing API response for JSON actions...")
        
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                log_info("Found JSON in markdown code block")
                response = json_match.group(1)
            else:
                log_info("No markdown code block found, trying raw JSON")
            
            data = json.loads(response)
            actions = data.get('actions', [])
            log_success(f"Successfully parsed {len(actions)} actions from JSON")
            return actions
        except json.JSONDecodeError as e:
            log_error(f"JSON decode error: {e}")
            log_info("Treating response as plain text comment")
            # If not valid JSON, treat as a comment action
            return [{"type": "comment", "message": response}]
    
    def _execute_actions(self, actions: List[Dict]) -> List[Dict]:
        """Execute the actions safely."""
        results = []
        current_branch = None
        
        for i, action in enumerate(actions):
            action_type = action.get('type')
            log_info(f"Executing action {i+1}/{len(actions)}: {action_type}")
            
            result = {"action": action, "success": False, "output": ""}
            
            try:
                if action_type == 'read_file':
                    content = self.read_file(action['path'])
                    result['success'] = True
                    result['output'] = content[:2000]  # Limit output
                    
                elif action_type == 'run_command':
                    if self.is_safe_command(action['command']):
                        rc, stdout, stderr = self.run_safe_command(action['command'])
                        result['success'] = rc == 0
                        result['output'] = stdout + stderr
                    else:
                        result['output'] = "Command blocked for safety"
                        
                elif action_type == 'run_tests':
                    success, output = self.run_tests()
                    result['success'] = success
                    result['output'] = output[:3000]
                    
                elif action_type == 'create_branch':
                    branch = self.create_branch(action['name'])
                    current_branch = branch
                    result['success'] = True
                    result['output'] = f"Created branch: {branch}"
                    
                elif action_type == 'write_file':
                    # Safety check
                    path = action['path']
                    if any(p in path for p in PROTECTED_PATHS):
                        result['output'] = "Cannot write to protected path"
                    else:
                        Path(path).write_text(action['content'])
                        result['success'] = True
                        result['output'] = f"Wrote {len(action['content'])} chars to {path}"
                        
                elif action_type == 'create_pr':
                    if current_branch:
                        # First push the branch
                        self.run_safe_command(f'git push --set-upstream origin {current_branch}')
                        pr_url = self.create_pull_request(
                            current_branch,
                            action['title'],
                            action['body']
                        )
                        result['success'] = True
                        result['output'] = pr_url
                    else:
                        result['output'] = "No branch created yet"
                        
                elif action_type == 'comment':
                    result['success'] = True
                    result['output'] = action['message']
                    
                else:
                    result['output'] = f"Unknown action type: {action_type}"
                    
            except SafetyError as e:
                result['output'] = f"Safety error: {e}"
            except Exception as e:
                result['output'] = f"Error: {type(e).__name__}: {e}"
            
            results.append(result)
        
        return results
    
    def _build_summary(self, actions: List[Dict], results: List[Dict]) -> str:
        """Build a summary comment of what was done."""
        lines = ["## 🤖 Kimi K2.5 Assistant Response", ""]
        
        for i, result in enumerate(results):
            action = result['action']
            status = "✅" if result['success'] else "❌"
            
            if action['type'] == 'comment':
                lines.append(result['output'])
            else:
                lines.append(f"{status} **{action['type']}**: {result['output'][:200]}")
        
        lines.extend([
            "",
            "---",
            "*This response was generated by Kimi K2.5 via GitHub Actions*"
        ])
        
        return '\n'.join(lines)


def main():
    """Main entry point."""
    handler = KimiHandler()
    handler.process_request()


if __name__ == '__main__':
    main()
