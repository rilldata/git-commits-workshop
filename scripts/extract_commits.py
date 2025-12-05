#!/usr/bin/env python
"""
Extract commit information from local Git repositories and generate commits.json.

This script processes one or more Git repositories and extracts detailed commit
information including file changes, line statistics, and diff hunks.

Usage:
    python extract_commits.py --repos /path/to/repo1 /path/to/repo2
    python extract_commits.py --parent-dir /path/to/repos_dir
    python extract_commits.py --repos /path/to/repo1 --output custom_commits.json
"""

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from multiprocessing import Pool, cpu_count, Process, Queue
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Sentinel value to signal end of commits
DONE = None


def run_git_command(repo_path: str, command: List[str]) -> Tuple[str, int]:
    """Run a git command in the specified repository."""
    try:
        result = subprocess.run(
            ["git"] + command,
            cwd=repo_path,
            capture_output=True,
            text=False,  # Get bytes first
            check=False
        )
        # Decode with error handling for binary/non-UTF8 content
        try:
            stdout = result.stdout.decode('utf-8', errors='replace')
        except (UnicodeDecodeError, AttributeError):
            # Fallback: try with surrogateescape for better binary handling
            stdout = result.stdout.decode('utf-8', errors='surrogateescape')
        return stdout, result.returncode
    except Exception as e:
        print(f"Error running git command: {e}", file=sys.stderr)
        return "", 1


def is_git_repo(repo_path: str) -> bool:
    """Check if the given path is a Git repository."""
    stdout, returncode = run_git_command(repo_path, ["rev-parse", "--is-inside-work-tree"])
    return returncode == 0 and stdout.strip() == "true"


def get_repo_info(repo_path: str) -> Tuple[str, str]:
    """
    Extract organization and repository name from git remote URL.
    Returns (org, repo) tuple. Falls back to parsing path if remote not available.
    """
    # Try to get remote URL
    stdout, returncode = run_git_command(repo_path, ["remote", "get-url", "origin"])
    
    if returncode == 0 and stdout.strip():
        remote_url = stdout.strip()
        # Parse various remote URL formats:
        # https://github.com/org/repo.git
        # https://github.com/org/repo
        # git@github.com:org/repo.git
        # git@github.com:org/repo
        
        # Remove .git suffix
        remote_url = remote_url.rstrip('.git')
        
        # Match patterns
        patterns = [
            r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'gitlab\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'bitbucket\.org[:/]([^/]+)/([^/]+?)(?:\.git)?/?$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, remote_url)
            if match:
                return (match.group(1), match.group(2))
    
    # Fallback: use directory name as repo, try to infer org from path
    repo_name = os.path.basename(os.path.abspath(repo_path))
    # Try to get org from parent directory structure (common patterns)
    abs_path = os.path.abspath(repo_path)
    parts = Path(abs_path).parts
    # Look for common patterns like /Users/username/dev/org/repo
    if len(parts) >= 2:
        # Use second-to-last part as potential org
        org = parts[-2] if len(parts) > 1 else "unknown"
    else:
        org = "unknown"
    
    return (org, repo_name)


def get_commit_hashes(repo_path: str) -> List[str]:
    """Get all commit hashes in reverse chronological order (including merge commits)."""
    stdout, returncode = run_git_command(
        repo_path,
        ["log", "--reverse", "--pretty=%H"]
    )
    if returncode != 0:
        return []
    return [h.strip() for h in stdout.strip().split("\n") if h.strip()]


def parse_file_change(line: str) -> Optional[Dict]:
    """
    Parse a file change line from git show --raw output.
    
    Format: :old_mode new_mode old_sha new_sha status[ score] path [old_path]
    Example: :100644 100644 abc123 def456 M 100 file.txt
    Example: :100644 100644 abc123 def456 R100 80 old.txt new.txt
    """
    # Pattern matches: :mode mode sha sha status[ score] path [old_path]
    pattern = r'^:(\d+)\s+(\d+)\s+([a-f0-9]+)\s+([a-f0-9]+)\s+([ADMRCT])(\d+)?\s+(.+)$'
    match = re.match(pattern, line)
    if not match:
        return None
    
    old_mode, new_mode, old_sha, new_sha, status, score, paths = match.groups()
    
    # Parse paths (may be one or two paths for rename/copy)
    path_parts = paths.split("\t")
    if len(path_parts) == 2:
        old_path, new_path = path_parts
    else:
        old_path = None
        new_path = path_parts[0]
    
    # Determine change type
    change_type_map = {
        'A': 'Add',
        'D': 'Delete',
        'M': 'Modify',
        'R': 'Rename',
        'C': 'Copy',
        'T': 'Type'
    }
    change_type = change_type_map.get(status, 'Modify')
    
    # Get file extension
    file_extension = Path(new_path).suffix if new_path else Path(old_path).suffix if old_path else ""
    
    return {
        "change_type": change_type,
        "path": new_path or old_path,
        "old_path": old_path if old_path != new_path else None,
        "file_extension": file_extension,
        "lines_added": 0,  # Will be filled from diff
        "lines_deleted": 0,  # Will be filled from diff
        "hunks_added": 0,  # Will be filled from diff
        "hunks_removed": 0,  # Will be filled from diff
        "hunks_changed": 0  # Will be filled from diff
    }


def parse_diff_hunk(hunk_header: str) -> Tuple[int, int, int, int]:
    """
    Parse a diff hunk header to extract line information.
    
    Format: @@ -old_start,old_count +new_start,new_count @@
    Returns: (old_start, old_count, new_start, new_count)
    """
    pattern = r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@'
    match = re.match(pattern, hunk_header)
    if not match:
        return (0, 0, 0, 0)
    
    old_start = int(match.group(1))
    old_count = int(match.group(2) or 0)
    new_start = int(match.group(3))
    new_count = int(match.group(4) or 0)
    
    return (old_start, old_count, new_start, new_count)


def analyze_diff(diff_lines: List[str], file_change: Dict) -> Dict:
    """Analyze diff lines to count additions, deletions, and hunks."""
    lines_added = 0
    lines_deleted = 0
    hunks_added = 0
    hunks_removed = 0
    hunks_changed = 0
    
    in_hunk = False
    current_hunk_has_additions = False
    current_hunk_has_deletions = False
    
    for line in diff_lines:
        if line.startswith("@@"):
            # New hunk
            if in_hunk:
                # Process previous hunk
                if current_hunk_has_additions and current_hunk_has_deletions:
                    hunks_changed += 1
                elif current_hunk_has_additions:
                    hunks_added += 1
                elif current_hunk_has_deletions:
                    hunks_removed += 1
            
            in_hunk = True
            current_hunk_has_additions = False
            current_hunk_has_deletions = False
        elif line.startswith("+") and not line.startswith("+++"):
            lines_added += 1
            current_hunk_has_additions = True
        elif line.startswith("-") and not line.startswith("---"):
            lines_deleted += 1
            current_hunk_has_deletions = True
    
    # Process last hunk
    if in_hunk:
        if current_hunk_has_additions and current_hunk_has_deletions:
            hunks_changed += 1
        elif current_hunk_has_additions:
            hunks_added += 1
        elif current_hunk_has_deletions:
            hunks_removed += 1
    
    file_change["lines_added"] = lines_added
    file_change["lines_deleted"] = lines_deleted
    file_change["hunks_added"] = hunks_added
    file_change["hunks_removed"] = hunks_removed
    file_change["hunks_changed"] = hunks_changed
    
    return file_change


def find_file_change_by_path(file_changes_dict: Dict, path: str) -> Optional[Dict]:
    """Find a file_change in the dict by matching path or old_path."""
    for fc in file_changes_dict.values():
        if fc["path"] == path or (fc.get("old_path") and fc["old_path"] == path):
            return fc
    return None


def get_commit_details(repo_path: str, commit_hash: str, org: str, repo: str) -> Optional[Dict]:
    """Extract detailed information about a specific commit."""
    stdout, returncode = run_git_command(
        repo_path,
        [
            "show",
            "--raw",
            "--pretty=format:%ct%x00%aN%x00%P%x00%s%x00",
            "--patch",
            "--unified=0",
            commit_hash
        ]
    )
    
    if returncode != 0 or not stdout:
        return None
    
    lines = stdout.split("\n")
    if not lines:
        return None
    
    # Parse header (first line with null-separated values)
    header_parts = lines[0].split("\x00")
    if len(header_parts) < 4:
        return None
    
    timestamp = int(header_parts[0])
    author = header_parts[1]
    parents = header_parts[2].split() if header_parts[2] else []
    message = header_parts[3] if len(header_parts) > 3 else ""
    
    # Convert timestamp to readable format
    dt = datetime.fromtimestamp(timestamp)
    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Parse file changes and diff
    # Git shows all : lines first, then all diff sections
    # So we need to collect : lines first, then match diffs to files
    
    file_changes_dict = {}  # path -> file_change dict
    file_changes_list = []  # preserve order
    
    # First pass: collect all file changes from : lines
    for line in lines[1:]:
        if line.startswith(":"):
            file_change = parse_file_change(line)
            if file_change:
                path = file_change["path"]
                # For renames, also index by old_path for matching
                file_changes_dict[path] = file_change
                file_changes_list.append(path)
                if file_change.get("old_path") and file_change["old_path"] != path:
                    file_changes_dict[file_change["old_path"]] = file_change
    
    # Second pass: collect and match diff sections to files
    current_file_path = None
    current_diff_lines = []
    
    for line in lines[1:]:
        if line.startswith(":"):
            # We've already processed these, skip
            continue
        elif line.startswith("diff --git"):
            # Save previous file's diff if exists
            if current_file_path and current_diff_lines:
                file_change_to_update = find_file_change_by_path(file_changes_dict, current_file_path)
                if file_change_to_update:
                    # Update the file_change in place (since it's a reference)
                    updated_fc = analyze_diff(current_diff_lines, file_change_to_update)
                    # Update both path entries if it's a rename
                    file_changes_dict[file_change_to_update["path"]] = updated_fc
                    if file_change_to_update.get("old_path") and file_change_to_update["old_path"] != file_change_to_update["path"]:
                        file_changes_dict[file_change_to_update["old_path"]] = updated_fc
            
            # Extract file path from "diff --git a/path b/path" or "diff --git a/path b/newpath"
            # Format: diff --git a/oldpath b/newpath
            # For deletes: diff --git a/path /dev/null
            # For adds: diff --git /dev/null b/path
            parts = line.split()
            if len(parts) >= 4:
                a_path = parts[2].replace("a/", "", 1) if parts[2].startswith("a/") else None
                b_path = parts[3].replace("b/", "", 1) if parts[3].startswith("b/") else None
                
                # Determine which path to use - prefer b_path (new path), fallback to a_path
                if b_path and b_path != "/dev/null":
                    current_file_path = b_path
                elif a_path and a_path != "/dev/null":
                    current_file_path = a_path
                else:
                    current_file_path = None
                
                current_diff_lines = [line] if current_file_path else []
            else:
                current_file_path = None
                current_diff_lines = []
        elif current_file_path:
            # Check if this path matches any file_change
            matching_fc = find_file_change_by_path(file_changes_dict, current_file_path)
            if matching_fc:
                # Capture all diff-related lines
                if (line.startswith("index ") or
                    line.startswith("---") or 
                    line.startswith("+++") or
                    line.startswith("@@") or
                    line.startswith("+") or 
                    line.startswith("-") or 
                    line.startswith(" ") or
                    line.startswith("\\") or
                    line == ""):
                    current_diff_lines.append(line)
    
    # Save last file's diff
    if current_file_path and current_diff_lines:
        file_change_to_update = find_file_change_by_path(file_changes_dict, current_file_path)
        if file_change_to_update:
            updated_fc = analyze_diff(current_diff_lines, file_change_to_update)
            file_changes_dict[file_change_to_update["path"]] = updated_fc
            if file_change_to_update.get("old_path") and file_change_to_update["old_path"] != file_change_to_update["path"]:
                file_changes_dict[file_change_to_update["old_path"]] = updated_fc
    
    # Convert back to list in original order
    file_changes = [file_changes_dict[path] for path in file_changes_list if path in file_changes_dict]
    
    # Calculate totals
    files_added = sum(1 for fc in file_changes if fc["change_type"] == "Add")
    files_deleted = sum(1 for fc in file_changes if fc["change_type"] == "Delete")
    files_renamed = sum(1 for fc in file_changes if fc["change_type"] == "Rename")
    files_modified = sum(1 for fc in file_changes if fc["change_type"] == "Modify")
    lines_added = sum(fc["lines_added"] for fc in file_changes)
    lines_deleted = sum(fc["lines_deleted"] for fc in file_changes)
    hunks_added = sum(fc["hunks_added"] for fc in file_changes)
    hunks_removed = sum(fc["hunks_removed"] for fc in file_changes)
    hunks_changed = sum(fc["hunks_changed"] for fc in file_changes)
    
    # Determine if this is a merge commit (has more than one parent)
    is_merge = len(parents) > 1
    
    return {
        "hash": commit_hash,
        "org": org,
        "repo": repo,
        "author": author,
        "time": time_str,
        "message": message,
        "merge": is_merge,
        "files_added": files_added,
        "files_deleted": files_deleted,
        "files_renamed": files_renamed,
        "files_modified": files_modified,
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "hunks_added": hunks_added,
        "hunks_removed": hunks_removed,
        "hunks_changed": hunks_changed,
        "file_changes": file_changes
    }


def process_single_commit(args: Tuple[str, str, str, str]) -> Optional[Dict]:
    """Worker function to process a single commit. Returns commit data or None."""
    repo_path, commit_hash, org, repo = args
    return get_commit_details(repo_path, commit_hash, org, repo)


def writer_process(queue: Queue, output_path: str, batch_size: int):
    """Writer process that consumes commits from queue and writes to file in batches."""
    batch_buffer = []
    total_commits = 0
    
    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        while True:
            commit = queue.get()
            if commit is DONE:
                # Flush remaining buffer
                if batch_buffer:
                    for c in batch_buffer:
                        f.write(json.dumps(c) + "\n")
                    total_commits += len(batch_buffer)
                break
            
            batch_buffer.append(commit)
            if len(batch_buffer) >= batch_size:
                for c in batch_buffer:
                    f.write(json.dumps(c) + "\n")
                total_commits += len(batch_buffer)
                batch_buffer = []
                print(f"  Written {total_commits} commits...", file=sys.stderr, end="\r")
    
    print(f"\nDone! Wrote {total_commits} commits to {output_path}", file=sys.stderr)


def process_repository(repo_path: str, queue: Queue):
    """Reader: Process a single repository and put commits into queue."""
    print(f"Processing repository: {repo_path}", file=sys.stderr)
    
    if not os.path.isdir(repo_path) or not is_git_repo(repo_path):
        print(f"Error: {repo_path} is not a valid Git repository", file=sys.stderr)
        return
    
    commit_hashes = get_commit_hashes(repo_path)
    if not commit_hashes:
        print(f"Warning: No commits found in {repo_path}", file=sys.stderr)
        return
    
    org, repo = get_repo_info(repo_path)
    print(f"  Repository: {org}/{repo} ({len(commit_hashes)} commits)", file=sys.stderr)
    
    num_workers = 10 * cpu_count()
    commit_args = [(repo_path, h, org, repo) for h in commit_hashes]
    
    completed = 0
    with Pool(processes=num_workers) as pool:
        for result in pool.imap_unordered(process_single_commit, commit_args):
            completed += 1
            if result:
                queue.put(result)
            if completed % 100 == 0 or completed == len(commit_hashes):
                print(f"  Progress: {completed}/{len(commit_hashes)}...", file=sys.stderr, end="\r")
    
    print(f"\n  Completed {repo_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Extract commit information from Git repositories"
    )
    parser.add_argument(
        "--repos",
        nargs="+",
        help="Paths to local Git repositories"
    )
    parser.add_argument(
        "--parent-dir",
        nargs="+",
        help="One or more directories whose immediate subdirectories will be scanned for Git repositories"
    )
    parser.add_argument(
        "--output",
        default="commits.json.gz",
        help="Output file path (default: commits.json.gz)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Number of commits to write in each batch (default: 10000)"
    )
    
    args = parser.parse_args()
    
    repo_paths = []
    seen = set()
    
    def add_repo(path):
        resolved = str(Path(path).resolve())
        if resolved not in seen:
            seen.add(resolved)
            repo_paths.append(resolved)
    
    if args.repos:
        for repo_path in args.repos:
            add_repo(repo_path)
    
    if args.parent_dir:
        for parent in args.parent_dir:
            parent_path = Path(parent).expanduser().resolve()
            if not parent_path.exists():
                print(f"Warning: parent directory '{parent}' does not exist. Skipping.", file=sys.stderr)
                continue
            if not parent_path.is_dir():
                print(f"Warning: '{parent}' is not a directory. Skipping.", file=sys.stderr)
                continue
            print(f"Scanning parent directory: {parent_path}", file=sys.stderr)
            for child in sorted(parent_path.iterdir()):
                if (child / ".git").is_dir():
                    add_repo(child)
    
    if not repo_paths:
        parser.error("No repositories provided. Use --repos and/or --parent-dir.")
    
    # Create queue for reader-writer communication
    queue = Queue()
    
    # Start writer process
    writer = Process(target=writer_process, args=(queue, args.output, args.batch_size))
    writer.start()
    
    # Process repositories (readers)
    print(f"Processing {len(repo_paths)} repositories (batch size: {args.batch_size})...", file=sys.stderr)
    for repo_path in repo_paths:
        process_repository(repo_path, queue)
    
    # Signal writer that all commits are done
    queue.put(DONE)
    writer.join()


if __name__ == "__main__":
    main()

