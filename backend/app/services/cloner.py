import os
import shutil
import subprocess
import uuid
import re
from fastapi import HTTPException
from app.core.config import settings

def validate_github_url(url: str) -> bool:
    """
    Validates that the URL is a valid GitHub or GitLab URL.
    """
    # Simple regex for github/gitlab
    pattern = r"^(https?://)?(www\.)?(github\.com|gitlab\.com)/[\w-]+/[\w.-]+/?$"
    return re.match(pattern, url) is not None

def clone_repository(url: str, branch: str = None) -> str:
    """
    Clones a repository to a temporary directory.
    Returns the path to the cloned repository.
    
    Args:
        url: Repository URL to clone
        branch: Optional specific branch to clone. If None, clones default branch.
    """
    if not validate_github_url(url):
        raise HTTPException(status_code=400, detail="Invalid repository URL. Only GitHub and GitLab are supported.")

    # Create a unique directory for the clone
    repo_id = str(uuid.uuid4())
    temp_path = os.path.join(settings.TEMP_DIR, repo_id)
    
    # Ensure temp dir exists
    os.makedirs(settings.TEMP_DIR, exist_ok=True)

    try:
        # Build git clone command
        clone_cmd = ["git", "clone"]
        
        if branch:
            # Clone specific branch with full history for branch switching
            clone_cmd.extend(["--branch", branch])
        else:
            # Default shallow clone for backward compatibility
            clone_cmd.extend(["--depth", "1"])
        
        clone_cmd.extend([url, temp_path])
        
        # Run git clone with timeout of 30 seconds
        subprocess.run(
            clone_cmd,
            check=True,
            timeout=30,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # If we cloned with full history, fetch all remote branches for switching
        if branch:
            subprocess.run(
                ["git", "fetch", "--all"],
                check=True,
                timeout=15,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=temp_path
            )
            
    except subprocess.TimeoutExpired:
        # Cleanup if timeout
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        raise HTTPException(status_code=408, detail="Repository cloning timed out (30s limit).")
    except subprocess.CalledProcessError as e:
         # Cleanup if error
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        raise HTTPException(status_code=400, detail=f"Git clone failed: {e.stderr.decode()}")
    except Exception as e:
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

    return temp_path


def clone_repository_with_branches(url: str) -> str:
    """
    Clones a repository with full branch support for branch switching.
    Returns the path to the cloned repository.
    
    Args:
        url: Repository URL to clone
    """
    if not validate_github_url(url):
        raise HTTPException(status_code=400, detail="Invalid repository URL. Only GitHub and GitLab are supported.")

    # Create a unique directory for the clone
    repo_id = str(uuid.uuid4())
    temp_path = os.path.join(settings.TEMP_DIR, repo_id)
    
    # Ensure temp dir exists
    os.makedirs(settings.TEMP_DIR, exist_ok=True)

    try:
        # Clone with full history to enable branch switching
        subprocess.run(
            ["git", "clone", url, temp_path],
            check=True,
            timeout=60,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Fetch all remote branches
        subprocess.run(
            ["git", "fetch", "--all"],
            check=True,
            timeout=30,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=temp_path
        )
        
    except subprocess.TimeoutExpired:
        # Cleanup if timeout
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        raise HTTPException(status_code=408, detail="Repository cloning timed out (60s limit).")
    except subprocess.CalledProcessError as e:
         # Cleanup if error
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        raise HTTPException(status_code=400, detail=f"Git clone failed: {e.stderr.decode()}")
    except Exception as e:
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

    return temp_path
