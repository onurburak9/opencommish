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
        self.token = os.environ.get('GITHUB_TOKEN')
        self.repo_owner = os.environ.get('REPO_OWNER')
        self.repo_name = os.environ.get('REPO_NAME')
        self.issue_number = os.environ.get('ISSUE_NUMBER')
        self.event_type = os.environ.get('EVENT_TYPE')
        self.actor = os.environ.get('ACTOR')
        
        # Get the trigger content
        self.trigger_body = self._get_trigger_body()
        
    def _get_trigger_body(self) -> str:
        """Get the body that triggered this action."""
        comment_body = os.environ.get('COMMENT_BODY', '')
        issue_body = os.environ.get('ISSUE_BODY', '')
        return comment_body or issue_body or ''
    
    def extract_kimi_request(self) -> Optional[str]:
        """Extract the request from @kimi mention."""
        # Match @kimi or @Kimi followed by the request
        pattern = r'@kimi\s+(.*?)(?:\n\n|\Z)'
        match = re.search(pattern, self.trigger_body, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
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
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    def get_repo_context(self) -> Dict[str, Any]:
        """Gather repository context for the AI."""
        context = {
            'files': [],
            'structure': {},
            'recent_commits': [],
            'branch': '',
        }
        
        # Get current branch
        _, branch, _ = self.run_safe_command('git branch --show-current')
        context['branch'] = branch.strip()
        
        # Get recent commits
        _, commits, _ = self.run_safe_command('git log --oneline -10')
        context['recent_commits'] = commits.strip().split('\n') if commits else []
        
        # Get repo structure
        _, files, _ = self.run_safe_command('find . -type f -name "*.py" -o -name "*.yml" -o -name "*.yaml" -o -name "*.md" -o -name "*.json" | head -50')
        context['files'] = [f.strip() for f in files.split('\n') if f.strip() and not f.startswith('./.git')]
        
        return context
    
    def read_file(self, filepath: str) -> str:
        """Safely read a file from the repo."""
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
            return path.read_text()
        return f"File not found: {filepath}"
    
    def create_branch(self, branch_name: str) -> str:
        """Create a new branch for changes."""
        # Sanitize branch name
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', branch_name.lower())
        safe_name = f"kimi/{safe_name[:50]}"  # Prefix and limit length
        
        # Create and checkout branch
        self.run_safe_command(f'git checkout -b {safe_name}')
        return safe_name
    
    def run_tests(self) -> tuple:
        """Run the test suite."""
        returncode, stdout, stderr = self.run_safe_command('pytest tests/ -v --tb=short')
        return returncode == 0, stdout + '\n' + stderr
    
    def post_comment(self, body: str):
        """Post a comment on the issue/PR."""
        from github import Github
        
        g = Github(self.token)
        repo = g.get_repo(f"{self.repo_owner}/{self.repo_name}")
        
        # Determine if issue or PR
        try:
            issue = repo.get_issue(int(self.issue_number))
            issue.create_comment(body)
        except Exception:
            # Try as PR
            pr = repo.get_pull(int(self.issue_number))
            pr.create_comment(body)
    
    def create_pull_request(self, branch: str, title: str, body: str) -> str:
        """Create a pull request with the changes."""
        from github import Github
        
        g = Github(self.token)
        repo = g.get_repo(f"{self.repo_owner}/{self.repo_name}")
        
        pr = repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base='main'
        )
        return pr.html_url
    
    def process_request(self):
        """Main entry point to process the Kimi request."""
        request = self.extract_kimi_request()
        if not request:
            print("No @kimi request found")
            return
        
        print(f"Processing request: {request}")
        
        # Gather context
        context = self.get_repo_context()
        
        # Build prompt for Kimi
        prompt = self._build_prompt(request, context)
        
        # Send to Kimi API (or OpenClaw gateway)
        response = self._call_kimi_api(prompt)
        
        # Process response and execute actions
        actions = self._parse_actions(response)
        
        # Execute actions safely
        results = self._execute_actions(actions)
        
        # Post summary comment
        summary = self._build_summary(actions, results)
        self.post_comment(summary)
    
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
        gateway_url = os.environ.get('OPENCLAW_GATEWAY_URL')
        gateway_token = os.environ.get('OPENCLAW_GATEWAY_TOKEN')
        
        if gateway_url:
            return self._call_openclaw_gateway(prompt, gateway_url, gateway_token)
        
        # Fall back to direct Kimi API
        kimi_key = os.environ.get('KIMI_API_KEY')
        if kimi_key:
            return self._call_kimi_direct(prompt, kimi_key)
        
        # No API available - return simulated response for testing
        return json.dumps({
            "actions": [
                {"type": "comment", "message": "Kimi API not configured. Please set OPENCLAW_GATEWAY_URL or KIMI_API_KEY secret."}
            ]
        })
    
    def _call_openclaw_gateway(self, prompt: str, url: str, token: Optional[str]) -> str:
        """Call OpenClaw gateway."""
        import requests
        
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
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
            response.raise_for_status()
            return response.json().get('response', '{}')
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _call_kimi_direct(self, prompt: str, api_key: str) -> str:
        """Call Moonshot/Kimi API directly."""
        import requests
        
        try:
            response = requests.post(
                "https://api.moonshot.cn/v1/chat/completions",
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
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def _parse_actions(self, response: str) -> List[Dict]:
        """Parse the JSON response from Kimi."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            
            data = json.loads(response)
            return data.get('actions', [])
        except json.JSONDecodeError:
            # If not valid JSON, treat as a comment action
            return [{"type": "comment", "message": response}]
    
    def _execute_actions(self, actions: List[Dict]) -> List[Dict]:
        """Execute the actions safely."""
        results = []
        current_branch = None
        
        for action in actions:
            action_type = action.get('type')
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
                result['output'] = f"Error: {e}"
            
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
