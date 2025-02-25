#!/usr/bin/env python3
"""
GitHub CI Plugin for enforcing code style standards.
This script checks Python code against style guidelines using tools like flake8, black, and isort.
"""

import os
import sys
import argparse
import requests
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('code_style_checker')

class CodeStyleChecker:
    """
    A plugin to check code style on GitHub pull requests and report results.
    """
    
    def __init__(self, token: str, repo: str, pr_number: Optional[int] = None):
        """
        Initialize the Code Style Checker.
        
        Args:
            token: GitHub API token with appropriate permissions
            repo: Repository in format 'owner/repo'
            pr_number: Pull request number (optional)
        """
        self.token = token
        self.repo = repo
        self.pr_number = pr_number
        self.api_url = f"https://api.github.com/repos/{repo}"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def get_pull_request(self, pr_number: int) -> Dict[str, Any]:
        """Get details for a specific pull request."""
        url = f"{self.api_url}/pulls/{pr_number}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_changed_files(self, pr_number: int) -> List[str]:
        """Get list of files changed in the pull request."""
        url = f"{self.api_url}/pulls/{pr_number}/files"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        files = []
        for file_data in response.json():
            filename = file_data["filename"]
            if filename.endswith(".py"):  # Only check Python files
                files.append(filename)
        
        return files
    
    def create_check_run(self, head_sha: str, name: str) -> int:
        """Create a new check run for the given commit."""
        url = f"{self.api_url}/check-runs"
        data = {
            "name": name,
            "head_sha": head_sha,
            "status": "in_progress",
            "started_at": self._get_current_time()
        }
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()["id"]
    
    def update_check_run(self, check_run_id: int, conclusion: str, output: Dict[str, Any]) -> None:
        """Update an existing check run with results."""
        url = f"{self.api_url}/check-runs/{check_run_id}"
        data = {
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": self._get_current_time(),
            "output": output
        }
        response = requests.patch(url, headers=self.headers, json=data)
        response.raise_for_status()
    
    def add_comment(self, pr_number: int, body: str) -> None:
        """Add a comment to a pull request."""
        url = f"{self.api_url}/issues/{pr_number}/comments"
        data = {"body": body}
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
    
    def run_flake8(self, files: List[str]) -> Dict[str, Any]:
        """Run flake8 on the specified files."""
        if not files:
            return {"success": True, "output": "No Python files to check", "violations": []}
        
        try:
            cmd = ["flake8"] + files
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            violations = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(":", 3)
                        if len(parts) >= 4:
                            violations.append({
                                "file": parts[0],
                                "line": int(parts[1]),
                                "column": int(parts[2]),
                                "message": parts[3].strip()
                            })
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "violations": violations
            }
        except Exception as e:
            logger.error(f"Error running flake8: {str(e)}")
            return {
                "success": False,
                "output": str(e),
                "violations": []
            }
    
    def run_ruff(self, files: List[str]) -> Dict[str, Any]:
        """Run ruff on the specified files."""
        if not files:
            return {"success": True, "output": "No Python files to check", "violations": []}
        
        try:
            cmd = ["ruff", "check"] + files
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            violations = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and ":" in line:
                        # Ruff output format: file.py:line:column: error code message
                        parts = line.split(":", 3)
                        if len(parts) >= 4:
                            file_path = parts[0]
                            line_num = int(parts[1])
                            col_num = int(parts[2])
                            message = parts[3].strip()
                            violations.append({
                                "file": file_path,
                                "line": line_num,
                                "column": col_num,
                                "message": message
                            })
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "violations": violations
            }
        except Exception as e:
            logger.error(f"Error running ruff: {str(e)}")
            return {
                "success": False,
                "output": str(e),
                "violations": []
            }
    
    def run_black(self, files: List[str]) -> Dict[str, Any]:
        """Run black in check mode on the specified files."""
        if not files:
            return {"success": True, "output": "No Python files to check", "violations": []}
        
        try:
            cmd = ["black", "--check"] + files
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            violations = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if "would reformat" in line:
                        file_path = line.split("would reformat ", 1)[1].strip()
                        violations.append({
                            "file": file_path,
                            "message": "File needs reformatting with black"
                        })
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + "\n" + result.stderr,
                "violations": violations
            }
        except Exception as e:
            logger.error(f"Error running black: {str(e)}")
            return {
                "success": False,
                "output": str(e),
                "violations": []
            }
    
    def run_isort(self, files: List[str]) -> Dict[str, Any]:
        """Run isort in check mode on the specified files."""
        if not files:
            return {"success": True, "output": "No Python files to check", "violations": []}
        
        try:
            cmd = ["isort", "--check-only"] + files
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            violations = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if "ERROR" in line and "would be" in line:
                        parts = line.split("ERROR", 1)[1].strip()
                        file_path = parts.split(" ", 1)[0].strip()
                        violations.append({
                            "file": file_path,
                            "message": "Imports need sorting with isort"
                        })
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + "\n" + result.stderr,
                "violations": violations
            }
        except Exception as e:
            logger.error(f"Error running isort: {str(e)}")
            return {
                "success": False,
                "output": str(e),
                "violations": []
            }
    
    def check_code_style(self, pr_number: int) -> Dict[str, Any]:
        """
        Check code style for files in a pull request.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Dictionary with check results
        """
        pr_data = self.get_pull_request(pr_number)
        head_sha = pr_data["head"]["sha"]
        
        logger.info(f"Checking code style for PR #{pr_number}, commit {head_sha}")
        
        # Create a check run
        check_run_id = self.create_check_run(head_sha, "Code Style Check")
        
        # Get changed files
        files = self.get_changed_files(pr_number)
        logger.info(f"Found {len(files)} Python files to check")
        
        # Run style checks
        flake8_results = self.run_flake8(files)
        black_results = self.run_black(files)
        isort_results = self.run_isort(files)
        ruff_results = self.run_ruff(files)
        
        # Combine results
        all_violations = (
            flake8_results["violations"] + 
            black_results["violations"] + 
            isort_results["violations"] +
            ruff_results["violations"]
        )
        
        success = (
            flake8_results["success"] and 
            black_results["success"] and 
            isort_results["success"] and
            ruff_results["success"]
        )
        
        # Prepare output for GitHub
        conclusion = "success" if success else "failure"
        
        summary = f"Code Style Check: {'Passed' if success else 'Failed'}\n\n"
        summary += f"- Flake8: {'Passed' if flake8_results['success'] else 'Failed'}\n"
        summary += f"- Black: {'Passed' if black_results['success'] else 'Failed'}\n"
        summary += f"- isort: {'Passed' if isort_results['success'] else 'Failed'}\n"
        summary += f"- Ruff: {'Passed' if ruff_results['success'] else 'Failed'}\n\n"
        summary += f"Total violations: {len(all_violations)}"
        
        # Prepare detailed output
        details = "## Code Style Violations\n\n"
        
        if all_violations:
            for violation in all_violations:
                if "line" in violation and "column" in violation:
                    details += f"- **{violation['file']}:{violation['line']}:{violation['column']}**: {violation['message']}\n"
                else:
                    details += f"- **{violation['file']}**: {violation['message']}\n"
        else:
            details += "No violations found! 🎉\n"
        
        # Add tool outputs
        details += "\n<details>\n<summary>Flake8 Output</summary>\n\n```\n"
        details += flake8_results["output"] or "No output"
        details += "\n```\n</details>\n\n"
        
        details += "<details>\n<summary>Black Output</summary>\n\n```\n"
        details += black_results["output"] or "No output"
        details += "\n```\n</details>\n\n"
        
        details += "<details>\n<summary>isort Output</summary>\n\n```\n"
        details += isort_results["output"] or "No output"
        details += "\n```\n</details>\n\n"
        
        details += "<details>\n<summary>Ruff Output</summary>\n\n```\n"
        details += ruff_results["output"] or "No output"
        details += "\n```\n</details>\n"
        
        output = {
            "title": "Code Style Check Results",
            "summary": summary,
            "text": details
        }
        
        # Update check run with results
        self.update_check_run(check_run_id, conclusion, output)
        
        # Add a comment to the PR
        self.add_comment(pr_number, details)
        
        return {
            "success": success,
            "violations": all_violations,
            "flake8": flake8_results,
            "black": black_results,
            "isort": isort_results,
            "ruff": ruff_results
        }
    
    def _get_current_time(self) -> str:
        """Get current time in ISO 8601 format."""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    """Main entry point for the Code Style Checker."""
    parser = argparse.ArgumentParser(description='GitHub CI Plugin for checking code style')
    parser.add_argument('--token', required=True, help='GitHub API token')
    parser.add_argument('--repo', required=True, help='Repository in format owner/repo')
    parser.add_argument('--pr', required=True, type=int, help='Pull request number to process')
    
    args = parser.parse_args()
    
    checker = CodeStyleChecker(args.token, args.repo, args.pr)
    results = checker.check_code_style(args.pr)
    
    # Exit with appropriate status code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
