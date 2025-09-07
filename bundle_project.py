# bundle_project.py
# !/usr/env/bin python3
# -*- coding: utf-8 -*-

"""
Master Bundler Script for the flashmvp Project.

This script acts as a runner to execute all individual module-specific bundler
scripts located in the 'project_bundles' subdirectory. It automatically discovers
any script following the 'bundle_project_*.py' naming convention and runs them
sequentially.

This allows for a single command to generate all necessary project bundles,
improving workflow efficiency.

Version: 1.1.0
Created: 2025-08-29
Updated: 2025-08-30 - Moved from tools/ to project root directory
"""

import subprocess
import sys
from pathlib import Path

# --- ANSI Color Codes for Better Output ---
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
NC = '\033[0m'  # No Color

def main():
    """
    Finds and executes all module-specific bundler scripts.
    """
    # [修改] 调整项目根目录的计算方式
    # 此脚本现在位于项目根目录，所以项目根目录就是其父目录。
    project_root = Path(__file__).resolve().parent
    
    # The target directory for bundler scripts is 'project_bundles'.
    bundlers_dir = project_root / 'project_bundles'
    
    print(f"{BLUE}==========================================={NC}")
    print(f"{BLUE}🚀 flashmvp Master Bundler Initializing...{NC}")
    print(f"{BLUE}==========================================={NC}")
    
    # --- 1. Validate that the bundlers directory exists ---
    if not bundlers_dir.is_dir():
        print(f"{RED}Error: Bundlers directory not found at '{bundlers_dir.as_posix()}'{NC}")
        print(f"{YELLOW}Please ensure this script is in the project root and the 'project_bundles' directory exists.{NC}")
        sys.exit(1)
        
    # --- 2. Find all scripts matching the pattern 'bundle_project_*.py' ---
    script_pattern = 'bundle_project_*.py'
    scripts_to_run = sorted(list(bundlers_dir.glob(script_pattern)))
    
    if not scripts_to_run:
        print(f"{YELLOW}Warning: No bundler scripts found matching '{script_pattern}' in the '{bundlers_dir.name}' directory.{NC}")
        print("Nothing to do. Exiting.")
        sys.exit(0)
        
    print(f"\n{GREEN}Found {len(scripts_to_run)} bundler script(s) to execute:{NC}")
    for script in scripts_to_run:
        print(f"  - {script.name}")
        
    # --- 3. Execute each script sequentially ---
    total_scripts = len(scripts_to_run)
    success_count = 0
    failure_count = 0
    
    for i, script_path in enumerate(scripts_to_run):
        print(f"\n{YELLOW}--- [{i+1}/{total_scripts}] Executing: {script_path.name} ---{NC}")
        
        try:
            # Execute the script using the same Python interpreter that is running this master script.
            # This ensures consistency with virtual environments.
            # We let the subprocess print its output directly to the console.
            result = subprocess.run(
                [sys.executable, str(script_path)], 
                check=True  # This will raise CalledProcessError if the script returns a non-zero exit code.
            )
            print(f"{GREEN}--- Success: {script_path.name} completed successfully. ---{NC}")
            success_count += 1
            
        except subprocess.CalledProcessError as e:
            print(f"{RED}--- Failure: {script_path.name} failed with exit code {e.returncode}. ---{NC}")
            print(f"{YELLOW}Please check the output above for error messages from the script.{NC}")
            failure_count += 1
        except FileNotFoundError:
            print(f"{RED}--- Critical Failure: Could not find the Python interpreter at '{sys.executable}'. ---{NC}")
            print(f"{YELLOW}Cannot continue. Aborting execution.{NC}")
            failure_count = total_scripts - i
            break
        except Exception as e:
            print(f"{RED}--- An unexpected error occurred while trying to run {script_path.name}: {e} ---{NC}")
            failure_count += 1

    # --- 4. Final Summary ---
    print(f"\n{BLUE}==========================================={NC}")
    print(f"{BLUE}✅ All Bundling Tasks Finished.{NC}")
    print(f"{BLUE}==========================================={NC}")
    print(f"  {GREEN}Successful Scripts: {success_count}{NC}")
    print(f"  {RED}Failed Scripts:     {failure_count}{NC}")
    print(f"{BLUE}==========================================={NC}")

    # Exit with a non-zero status code if any script failed, useful for CI/CD pipelines.
    if failure_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()