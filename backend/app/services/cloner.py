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

def clone_repository(url: str) -> str:
    """
    Clones a repository to a temporary directory.
    Returns the path to the cloned repository.
    """
    if not validate_github_url(url):
        raise HTTPException(status_code=400, detail="Invalid repository URL. Only GitHub and GitLab are supported.")

    # Create a unique directory for the clone
    repo_id = str(uuid.uuid4())
    temp_path = os.path.join(settings.TEMP_DIR, repo_id)
    
    # Ensure temp dir exists
    os.makedirs(settings.TEMP_DIR, exist_ok=True)

    try:
        # Run git clone --depth 1
        # strict timeout of 30 seconds
        subprocess.run(
            ["git", "clone", "--depth", "1", url, temp_path],
            check=True,
            timeout=30,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
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
