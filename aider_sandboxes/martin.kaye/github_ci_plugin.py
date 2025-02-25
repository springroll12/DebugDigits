#!/usr/bin/env python3
"""
GitHub CI Plugin for running tests on every pull request.
This script interacts with GitHub's API to manage test runs on PRs.
"""

import os
import sys
import argparse
import requests
import json
import logging
import datetime
import tempfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('github_ci_plugin')

class GitHubCIPlugin:
    """
    A plugin to run tests on GitHub pull requests and report results.
    """
    
    def __init__(self, token: str, repo: str, pr_number: Optional[int] = None):
        """
        Initialize the GitHub CI Plugin.
        
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
    
    def run_tests(self, test_command: str) -> Dict[str, Any]:
        """
        Run the specified test command and return results.
        
        Args:
            test_command: Command to run tests
            
        Returns:
            Dictionary with test results including success status and output
        """
        import subprocess
        import re
        
        logger.info(f"Running test command: {test_command}")
        start_time = datetime.datetime.now()
        
        try:
            result = subprocess.run(
                test_command,
                shell=True,
                capture_output=True,
                text=True
            )
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            success = result.returncode == 0
            
            # Parse test output to extract more detailed information
            test_details = self._parse_test_output(result.stdout, result.stderr)
            
            return {
                "success": success,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "test_details": test_details
            }
        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": duration,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "test_details": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 1,
                    "failures": []
                }
            }
    
    def _parse_test_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Parse test output to extract structured information.
        
        This method attempts to parse unittest, pytest, or other common test formats.
        It can be extended to support more test frameworks.
        
        Returns:
            Dictionary with test statistics and details
        """
        # Default values
        test_details = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "failures": []
        }
        
        combined_output = stdout + "\n" + stderr
        
        # Try to parse unittest output
        unittest_pattern = r"Ran (\d+) tests? in .*\n\n(OK|FAILED)"
        unittest_match = re.search(unittest_pattern, combined_output)
        if unittest_match:
            test_details["total"] = int(unittest_match.group(1))
            if unittest_match.group(2) == "OK":
                test_details["passed"] = test_details["total"]
            else:
                # Try to extract failures and errors
                failures_pattern = r"failures=(\d+)"
                errors_pattern = r"errors=(\d+)"
                
                failures_match = re.search(failures_pattern, combined_output)
                if failures_match:
                    test_details["failed"] = int(failures_match.group(1))
                
                errors_match = re.search(errors_pattern, combined_output)
                if errors_match:
                    test_details["errors"] = int(errors_match.group(1))
                
                test_details["passed"] = test_details["total"] - test_details["failed"] - test_details["errors"]
        
        # Try to parse pytest output
        pytest_pattern = r"=+ (\d+) passed, (\d+) skipped, (\d+) failed, (\d+) error"
        pytest_match = re.search(pytest_pattern, combined_output)
        if pytest_match:
            test_details["passed"] = int(pytest_match.group(1))
            test_details["skipped"] = int(pytest_match.group(2))
            test_details["failed"] = int(pytest_match.group(3))
            test_details["errors"] = int(pytest_match.group(4))
            test_details["total"] = test_details["passed"] + test_details["skipped"] + test_details["failed"] + test_details["errors"]
        
        # Extract failure details
        failure_blocks = re.finditer(r"(ERROR|FAIL): (test\w+).*?\n(.*?)(?=\n\n|$)", combined_output, re.DOTALL)
        for match in failure_blocks:
            test_details["failures"].append({
                "type": match.group(1),
                "test_name": match.group(2),
                "details": match.group(3).strip()
            })
        
        return test_details
    
    def generate_html_report(self, test_results: Dict[str, Any], pr_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Generate an HTML report from test results.
        
        Args:
            test_results: The test results dictionary
            pr_data: Pull request data
            
        Returns:
            Tuple of (file_path, html_content)
        """
        # Create a temporary directory for the report
        report_dir = Path(tempfile.mkdtemp(prefix="github_ci_report_"))
        report_file = report_dir / "test_report.html"
        
        # Format test details
        test_details = test_results.get("test_details", {})
        total = test_details.get("total", 0)
        passed = test_details.get("passed", 0)
        failed = test_details.get("failed", 0)
        skipped = test_details.get("skipped", 0)
        errors = test_details.get("errors", 0)
        
        # Calculate pass rate
        pass_rate = 0
        if total > 0:
            pass_rate = (passed / total) * 100
        
        # Generate HTML content
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report for PR #{pr_data["number"]}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .summary {{ display: flex; justify-content: space-between; margin-bottom: 20px; }}
        .summary-box {{ flex: 1; padding: 15px; margin: 0 10px; border-radius: 5px; text-align: center; }}
        .passed {{ background-color: #d4edda; color: #155724; }}
        .failed {{ background-color: #f8d7da; color: #721c24; }}
        .skipped {{ background-color: #fff3cd; color: #856404; }}
        .total {{ background-color: #e2e3e5; color: #383d41; }}
        .details {{ margin-top: 30px; }}
        .output {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        pre {{ margin: 0; white-space: pre-wrap; }}
        .progress-bar {{ height: 20px; background-color: #e9ecef; border-radius: 10px; margin-bottom: 20px; overflow: hidden; }}
        .progress {{ height: 100%; border-radius: 10px; }}
        .failures {{ margin-top: 20px; }}
        .failure-item {{ background-color: #f8d7da; padding: 10px; margin-bottom: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Test Report</h1>
            <p>Pull Request: <strong>#{pr_data["number"]}</strong> - {pr_data["title"]}</p>
            <p>Commit: <code>{pr_data["head"]["sha"]}</code></p>
            <p>Run at: {test_results.get("start_time", "Unknown")}</p>
            <p>Duration: {test_results.get("duration", 0):.2f} seconds</p>
        </div>
        
        <div class="progress-bar">
            <div class="progress" style="width: {pass_rate}%; background-color: {'#28a745' if test_results['success'] else '#dc3545'};"></div>
        </div>
        
        <div class="summary">
            <div class="summary-box total">
                <h2>Total</h2>
                <p>{total}</p>
            </div>
            <div class="summary-box passed">
                <h2>Passed</h2>
                <p>{passed}</p>
            </div>
            <div class="summary-box failed">
                <h2>Failed</h2>
                <p>{failed + errors}</p>
            </div>
            <div class="summary-box skipped">
                <h2>Skipped</h2>
                <p>{skipped}</p>
            </div>
        </div>
        
        <div class="failures">
            <h2>Failures and Errors</h2>
            """
        
        # Add failure details
        failures = test_details.get("failures", [])
        if failures:
            for failure in failures:
                html_content += f"""
            <div class="failure-item">
                <h3>{failure.get("type", "Error")}: {failure.get("test_name", "Unknown Test")}</h3>
                <pre>{failure.get("details", "No details available")}</pre>
            </div>
                """
        else:
            html_content += "<p>No failures or errors detected.</p>"
        
        html_content += """
        </div>
        
        <div class="details">
            <h2>Test Output</h2>
            <div class="output">
                <h3>Standard Output</h3>
                <pre>""" + test_results.get("stdout", "No output") + """</pre>
            </div>
            
            <div class="output">
                <h3>Standard Error</h3>
                <pre>""" + test_results.get("stderr", "No errors") + """</pre>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        # Write the HTML content to the file
        report_file.write_text(html_content)
        logger.info(f"Generated HTML report at {report_file}")
        
        return str(report_file), html_content
    
    def process_pull_request(self, pr_number: int, test_command: str) -> None:
        """Process a single pull request by running tests and reporting results."""
        pr_data = self.get_pull_request(pr_number)
        head_sha = pr_data["head"]["sha"]
        
        logger.info(f"Processing PR #{pr_number}, commit {head_sha}")
        
        # Create a check run
        check_run_id = self.create_check_run(head_sha, "Test Suite")
        
        # Run tests
        test_results = self.run_tests(test_command)
        
        # Generate HTML report
        report_path, html_content = self.generate_html_report(test_results, pr_data)
        
        # Prepare test summary
        test_details = test_results.get("test_details", {})
        total = test_details.get("total", 0)
        passed = test_details.get("passed", 0)
        failed = test_details.get("failed", 0)
        errors = test_details.get("errors", 0)
        skipped = test_details.get("skipped", 0)
        
        # Prepare output for GitHub
        conclusion = "success" if test_results["success"] else "failure"
        summary = f"Tests: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped"
        if total > 0:
            summary += f" (Pass rate: {(passed/total)*100:.1f}%)"
        
        summary += f"\nRun duration: {test_results.get('duration', 0):.2f} seconds"
        
        output = {
            "title": "Test Results",
            "summary": summary,
            "text": f"```\n{test_results['stdout']}\n{test_results['stderr']}\n```"
        }
        
        # Update check run with results
        self.update_check_run(check_run_id, conclusion, output)
        
        # Add a comment to the PR with more detailed information
        comment = f"## Test Results\n\n"
        comment += f"**Status**: {'✅ Passed' if test_results['success'] else '❌ Failed'}\n\n"
        comment += f"**Summary**:\n"
        comment += f"- Total: {total}\n"
        comment += f"- Passed: {passed}\n"
        comment += f"- Failed: {failed}\n"
        comment += f"- Errors: {errors}\n"
        comment += f"- Skipped: {skipped}\n"
        comment += f"- Duration: {test_results.get('duration', 0):.2f} seconds\n\n"
        
        # Add failure details if any
        failures = test_details.get("failures", [])
        if failures:
            comment += "**Failures**:\n\n"
            for failure in failures:
                comment += f"- **{failure.get('type', 'Error')}**: {failure.get('test_name', 'Unknown Test')}\n"
                comment += f"  ```\n  {failure.get('details', 'No details available')}\n  ```\n\n"
        
        # Add link to the report if we were to upload it somewhere
        comment += f"**Detailed report**: A full HTML report has been generated.\n\n"
        
        # Add a collapsible section with the full output
        comment += "<details>\n"
        comment += "<summary>Click to see full test output</summary>\n\n"
        comment += f"```\n{test_results['stdout']}\n{test_results['stderr']}\n```\n"
        comment += "</details>\n"
        
        self.add_comment(pr_number, comment)
        
        # Log the report location
        logger.info(f"Test report generated at: {report_path}")
    
    # Method removed as we'll only process specific PRs
    
    def _get_current_time(self) -> str:
        """Get current time in ISO 8601 format."""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    """Main entry point for the GitHub CI Plugin."""
    parser = argparse.ArgumentParser(description='GitHub CI Plugin for running tests on PRs')
    parser.add_argument('--token', required=True, help='GitHub API token')
    parser.add_argument('--repo', required=True, help='Repository in format owner/repo')
    parser.add_argument('--pr', required=True, type=int, help='Pull request number to process')
    parser.add_argument('--test-command', required=True, help='Command to run tests')
    parser.add_argument('--report-dir', help='Directory to save the HTML report (default: auto-generated temp dir)')
    
    args = parser.parse_args()
    
    plugin = GitHubCIPlugin(args.token, args.repo, args.pr)
    logger.info(f"Processing pull request #{args.pr}")
    plugin.process_pull_request(args.pr, args.test_command)


if __name__ == "__main__":
    main()
