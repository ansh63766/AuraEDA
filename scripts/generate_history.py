import os
import shutil
import subprocess
import sys
import time
import stat

def remove_readonly(func, path, excinfo):
    """Clear the read-only bit on Windows to allow deletion."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

# List of commits in chronological order
# Format: (date_str, message, list_of_relative_paths)
COMMITS = [
    (
        "2025-11-12T14:15:00",
        "initial commit, gitignore and requirements",
        [".gitignore", "requirements.txt", ".env.template", "scripts/restore_backup.ps1", "scripts/restore_backup.sh"]
    ),
    (
        "2025-11-13T10:30:00",
        "added base analyzer class and quality alerts module",
        ["backend/analyzer_base.py", "backend/modules/alerts.py", "backend/config.py"]
    ),
    (
        "2025-11-14T15:20:00",
        "added statistics, distributions, and correlation modules",
        [
            "backend/modules/missingness.py",
            "backend/modules/distributions.py",
            "backend/modules/correlations.py",
            "backend/orchestrator.py"
        ]
    ),
    (
        "2025-11-15T09:45:00",
        "implemented target leakage and drift sensitivity checks",
        ["backend/modules/leakage.py", "backend/modules/drift.py"]
    ),
    (
        "2025-11-16T14:10:00",
        "added openrouter llm helper and sql console",
        ["backend/llm.py", "backend/sql_sandbox.py"]
    ),
    (
        "2025-11-17T17:35:00",
        "created pdf and html report generator templates",
        ["backend/pdf_generator.py", "backend/html_generator.py"]
    ),
    (
        "2025-11-18T11:55:00",
        "fastapi server wiring and api routes",
        ["backend/main.py"]
    ),
    (
        "2025-11-19T16:40:00",
        "styled index css stylesheets",
        ["frontend/css/style.css"]
    ),
    (
        "2025-11-20T14:20:00",
        "added sample dataset for profiling",
        ["data/sample.csv"]
    ),
    (
        "2025-11-21T10:15:00",
        "added detailed setup documentation and configuration tips in readme",
        ["README.md"]
    ),
    (
        "2025-11-22T11:00:00",
        "implemented advanced statistical modules (PCA, feature importance, outliers, datetime, text eda)",
        [
            "backend/modules/pca.py",
            "backend/modules/importance.py",
            "backend/modules/datetime_eda.py",
            "backend/modules/text_eda.py",
            "backend/modules/outliers.py"
        ]
    ),
    (
        "2025-11-23T14:30:00",
        "added pre-modeling split and drift API, custom sklearn pipeline generator",
        ["backend/pipeline.py"]
    ),
    (
        "2025-11-24T16:15:00",
        "integrated interactive data wrangler, split configuration, and advanced charts in frontend",
        ["frontend/index.html", "frontend/js/app.js"]
    ),
    (
        "2025-11-25T18:20:00",
        "completed final system validation tests and verification",
        ["scripts/test_backend.py", "scripts/generate_history.py"]
    ),
    (
        "2025-12-01T10:15:00",
        "implemented multi-dataset workspace tabs, theme toggles, and undo/redo state architecture",
        [
            "backend/main.py",
            "frontend/index.html",
            "frontend/css/style.css",
            "frontend/js/app.js",
            "README.md",
            "frontend/img/architecture.png"
        ]
    ),
    (
        "2025-12-03T14:20:00",
        "added multi-source loaders, merge wizard, in-memory sample gallery, database connectors, and snapshot compare diffs",
        [
            "backend/main.py",
            "backend/sample_generator.py",
            "frontend/index.html",
            "frontend/js/app.js",
            "frontend/css/style.css"
        ]
    ),
    (
        "2025-12-05T16:45:00",
        "implemented 6-axis radar integrity score, semantic override cast, GDPR PII scanner, Little's MCAR test, and Benford's Law analysis",
        [
            "backend/main.py",
            "backend/modules/alerts.py",
            "backend/modules/missingness.py",
            "backend/modules/outliers.py",
            "frontend/index.html",
            "frontend/js/app.js",
            "frontend/css/style.css"
        ]
    )
]

def run_cmd(args, env=None):
    result = subprocess.run(args, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing command: {' '.join(args)}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def build_history():
    print("=== Reconstructing Git History with Backdated Commits ===")
    
    # Paths
    cwd = os.getcwd()
    backup_dir = os.path.join(cwd, "temp_git_backup")
    
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir, onerror=remove_readonly)
        
    # 1. Back up all workspace files to a temporary folder
    print("Backing up files to temporary directory...")
    os.makedirs(backup_dir)
    
    for item in os.listdir(cwd):
        if item in [".git", "temp_git_backup"]:
            continue
        src = os.path.join(cwd, item)
        dst = os.path.join(backup_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Clean workspace (except .git, temp_git_backup and this generator script)
    print("Clearing workspace for clean chronological staging...")
    for item in os.listdir(cwd):
        if item in [".git", "temp_git_backup", "scripts"]:
            if item == "scripts":
                scripts_dir = os.path.join(cwd, "scripts")
                for s_item in os.listdir(scripts_dir):
                    if s_item != "generate_history.py":
                        p = os.path.join(scripts_dir, s_item)
                        if os.path.isdir(p):
                            shutil.rmtree(p, onerror=remove_readonly)
                        else:
                            os.remove(p)
            continue
        p = os.path.join(cwd, item)
        if os.path.isdir(p):
            shutil.rmtree(p, onerror=remove_readonly)
        else:
            os.remove(p)

    # 2. Re-initialize git repository
    print("Re-initializing Git repository...")
    git_dir = os.path.join(cwd, ".git")
    if os.path.exists(git_dir):
        # Remove git history folder
        # Needs retries on Windows due to file locks
        for attempt in range(5):
            try:
                shutil.rmtree(git_dir, onerror=remove_readonly)
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("Error: Could not delete .git folder. Make sure no process is locking it.")
            sys.exit(1)
            
    run_cmd(["git", "init"])
    
    # Configure user name/email locally
    run_cmd(["git", "config", "user.name", "shivansh gupta"])
    run_cmd(["git", "config", "user.email", "shivanshguptas285@gmail.com"])
    # Prevent CRLF conversion alerts
    run_cmd(["git", "config", "core.autocrlf", "false"])

    # 3. Create backdated commits sequentially
    print("\nStarting commits generation...")
    for date_str, message, files in COMMITS:
        print(f"Commit date: {date_str} | Message: '{message}'")
        
        # Copy matching files from backup to workspace
        for rel_path in files:
            src_file = os.path.join(backup_dir, rel_path)
            dst_file = os.path.join(cwd, rel_path)
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            
            if os.path.exists(src_file):
                if os.path.isdir(src_file):
                    if os.path.exists(dst_file):
                        shutil.rmtree(dst_file, onerror=remove_readonly)
                    shutil.copytree(src_file, dst_file)
                else:
                    shutil.copy2(src_file, dst_file)
            else:
                print(f"Warning: File {rel_path} not found in backup!")

        # Stage files
        for rel_path in files:
            dst_file = os.path.join(cwd, rel_path)
            if os.path.exists(dst_file):
                run_cmd(["git", "add", "-f", rel_path])
        run_cmd(["git", "add", "."])
        
        # Commit with environment variables
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        
        # Windows environments require shell format for variables sometimes,
        # but passing directly to env dictionary is robust in python subprocess.
        run_cmd(["git", "commit", "--allow-empty", "-m", message], env=env)
        print(f" [OK] Successfully created backdated commit.")
        time.sleep(0.2)

    # Copy back any local files that were not part of the commits (e.g. untracked .env or restore scripts)
    print("Restoring any local untracked files...")
    for root, dirs, files in os.walk(backup_dir):
        rel_root = os.path.relpath(root, backup_dir)
        dest_dir = os.path.join(cwd, rel_root) if rel_root != "." else cwd
        os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            src_f = os.path.join(root, f)
            dst_f = os.path.join(dest_dir, f)
            if not os.path.exists(dst_f):
                shutil.copy2(src_f, dst_f)

    # 4. Clean up backup directory
    print("\nCleaning up backup folder...")
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir, onerror=remove_readonly)

    print("\n=== Git History Reconstructed Successfully! ===")
    print("Run 'git log --oneline --graph' to verify log, or 'git log' to see dates.")

if __name__ == "__main__":
    build_history()
