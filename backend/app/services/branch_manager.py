"""
Branch Manager service for handling repository branch operations.
"""
import os
import subprocess
import shutil
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException

from app.models.branch import BranchInfo, BranchContext, AnalysisStatus
from app.core.config import settings


class BranchManager:
    """Manages repository branch operations and metadata."""
    
    def __init__(self):
        """Initialize the branch manager."""
        pass
    
    async def fetch_branches_from_repo(self, repo_id: str) -> List[BranchInfo]:
        """
        Fetch all available branches from an existing cloned repository.
        This method uses the existing clone instead of creating a bare clone,
        which fixes Windows compatibility issues.
        
        Args:
            repo_id: The repository ID (directory name in temp_clones)
            
        Returns:
            List of BranchInfo objects containing branch metadata
            
        Raises:
            HTTPException: If branch fetching fails
        """
        # Use the existing cloned repository path
        repo_path = os.path.join(settings.TEMP_DIR, repo_id)
        
        # Validate path exists
        if not os.path.exists(repo_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Repository not found at path: {repo_id}"
            )
        
        # Validate it's a git repository
        git_dir = os.path.join(repo_path, '.git')
        if not os.path.exists(git_dir):
            raise HTTPException(
                status_code=400, 
                detail="Path exists but is not a git repository"
            )
        
        try:
            # Fetch latest from remote to ensure we have all branches
            try:
                subprocess.run(
                    ["git", "fetch", "--all"],
                    check=True,
                    timeout=30,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=repo_path
                )
            except subprocess.CalledProcessError:
                # Fetch might fail if remote is unavailable, continue with local branches
                pass
            
            # Get list of all branches (local and remote)
            result = subprocess.run(
                ["git", "branch", "-a"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_path
            )
            
            branches = []
            default_branch = None
            seen_branches = set()
            
            # Parse branch list
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                # Skip HEAD pointer lines
                if '->' in line:
                    continue
                
                # Clean up branch name
                branch_name = line.strip()
                
                # Remove leading asterisk (current branch marker)
                if branch_name.startswith('* '):
                    branch_name = branch_name[2:]
                
                # Handle remote branches (remotes/origin/branch_name)
                if 'remotes/origin/' in branch_name:
                    branch_name = branch_name.replace('remotes/origin/', '')
                elif branch_name.startswith('origin/'):
                    branch_name = branch_name.replace('origin/', '')
                
                # Skip if we've already seen this branch
                if branch_name in seen_branches or not branch_name:
                    continue
                seen_branches.add(branch_name)
                
                # Get commit SHA for this branch
                commit_sha = await self._get_branch_commit_sha_from_repo(repo_path, branch_name)
                
                # Get commit date
                commit_date = await self._get_commit_date_from_repo(repo_path, commit_sha)
                
                # Determine if this is the default branch (usually main or master)
                is_default = branch_name in ['main', 'master']
                if is_default and default_branch is None:
                    default_branch = branch_name
                
                branches.append(BranchInfo(
                    name=branch_name,
                    commit_sha=commit_sha,
                    is_default=is_default,
                    last_commit_date=commit_date
                ))
            
            # If no default branch found, set the first one as default
            if not default_branch and branches:
                branches[0].is_default = True
                default_branch = branches[0].name
            
            # Ensure only one default branch
            if default_branch and len(branches) > 1:
                for branch in branches:
                    branch.is_default = (branch.name == default_branch)
            
            return branches
            
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=408, 
                detail="Branch fetching timed out (30s limit)."
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Git branch fetch failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error fetching branches: {str(e)}"
            )
    
    async def _get_branch_commit_sha_from_repo(self, repo_path: str, branch_name: str) -> str:
        """Get commit SHA for a branch from a regular repository."""
        try:
            # Try to get SHA for the branch
            result = subprocess.run(
                ["git", "rev-parse", f"origin/{branch_name}"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_path
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            try:
                # Fallback to local branch
                result = subprocess.run(
                    ["git", "rev-parse", branch_name],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError:
                # Fallback to HEAD
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                return result.stdout.strip()
    
    async def _get_commit_date_from_repo(self, repo_path: str, commit_sha: str) -> datetime:
        """Get commit date from a regular repository."""
        try:
            result = subprocess.run(
                ["git", "show", "-s", "--format=%ci", commit_sha],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_path
            )
            # Parse git date format: 2024-01-15 10:30:45 +0000
            date_str = result.stdout.strip()
            # Handle timezone by splitting on space and taking first two parts
            parts = date_str.split(' ')
            if len(parts) >= 2:
                date_str = f"{parts[0]} {parts[1]}"
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except (subprocess.CalledProcessError, ValueError):
            # Fallback to current time if parsing fails
            return datetime.now()
    
    async def fetch_branches(self, repo_url: str) -> List[BranchInfo]:
        """
        Fetch all available branches from a repository.
        
        Args:
            repo_url: The repository URL to fetch branches from
            
        Returns:
            List of BranchInfo objects containing branch metadata
            
        Raises:
            HTTPException: If branch fetching fails
        """
        # Create a temporary clone to fetch branch information
        temp_id = str(uuid.uuid4())
        temp_path = os.path.join(settings.TEMP_DIR, f"branch_fetch_{temp_id}")
        
        try:
            # Ensure temp dir exists
            os.makedirs(settings.TEMP_DIR, exist_ok=True)
            
            # Clone repository with all branches
            subprocess.run(
                ["git", "clone", "--bare", repo_url, temp_path],
                check=True,
                timeout=60,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=settings.TEMP_DIR
            )
            
            # Get list of all branches
            result = subprocess.run(
                ["git", "branch", "-r"],
                check=True,
                capture_output=True,
                text=True,
                cwd=temp_path
            )
            
            branches = []
            default_branch = None
            
            # Parse branch list
            for line in result.stdout.strip().split('\n'):
                if not line.strip() or '->' in line:
                    continue
                    
                branch_name = line.strip().replace('origin/', '')
                if not branch_name:
                    continue
                
                # Get commit SHA for this branch
                commit_sha = await self._get_branch_commit_sha_from_bare(temp_path, f"origin/{branch_name}")
                
                # Get commit date
                commit_date = await self._get_commit_date_from_bare(temp_path, commit_sha)
                
                # Determine if this is the default branch (usually main or master)
                is_default = branch_name in ['main', 'master'] or default_branch is None
                if is_default and default_branch is None:
                    default_branch = branch_name
                
                branches.append(BranchInfo(
                    name=branch_name,
                    commit_sha=commit_sha,
                    is_default=is_default,
                    last_commit_date=commit_date
                ))
            
            # Ensure only one default branch
            if default_branch and len(branches) > 1:
                for branch in branches:
                    branch.is_default = (branch.name == default_branch)
            
            return branches
            
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=408, 
                detail="Branch fetching timed out (60s limit)."
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Git branch fetch failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error fetching branches: {str(e)}"
            )
        finally:
            # Clean up temporary clone
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
    
    async def get_branch_commit_sha(self, repo_url: str, branch: str) -> str:
        """
        Get the latest commit SHA for a specific branch.
        
        Args:
            repo_url: The repository URL
            branch: The branch name
            
        Returns:
            The commit SHA string
            
        Raises:
            HTTPException: If commit SHA retrieval fails
        """
        temp_id = str(uuid.uuid4())
        temp_path = os.path.join(settings.TEMP_DIR, f"sha_fetch_{temp_id}")
        
        try:
            # Ensure temp dir exists
            os.makedirs(settings.TEMP_DIR, exist_ok=True)
            
            # Clone just the specific branch
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, temp_path],
                check=True,
                timeout=30,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Get the commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                cwd=temp_path
            )
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=408, 
                detail="Commit SHA fetch timed out (30s limit)."
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Git commit SHA fetch failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error fetching commit SHA: {str(e)}"
            )
        finally:
            # Clean up temporary clone
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
    
    async def switch_branch_context(self, repo_id: str, branch: str) -> BranchContext:
        """
        Switch the analysis context to a different branch.
        
        Args:
            repo_id: The repository ID
            branch: The target branch name
            
        Returns:
            BranchContext with updated information
            
        Raises:
            HTTPException: If branch switching fails
        """
        repo_path = os.path.join(settings.TEMP_DIR, repo_id)
        
        if not os.path.exists(repo_path):
            raise HTTPException(
                status_code=404, 
                detail="Repository not found"
            )
        
        try:
            # Check if branch exists locally
            result = subprocess.run(
                ["git", "branch", "-a"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_path
            )
            
            branch_exists = False
            remote_branch = f"origin/{branch}"
            
            for line in result.stdout.split('\n'):
                if branch in line.strip() or remote_branch in line.strip():
                    branch_exists = True
                    break
            
            if not branch_exists:
                # Fetch the branch from remote
                subprocess.run(
                    ["git", "fetch", "origin", branch],
                    check=True,
                    timeout=30,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=repo_path
                )
            
            # Switch to the branch
            subprocess.run(
                ["git", "checkout", branch],
                check=True,
                timeout=10,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=repo_path
            )
            
            # Get the current commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_path
            )
            
            commit_sha = sha_result.stdout.strip()
            
            return BranchContext(
                repo_id=repo_id,
                branch_name=branch,
                commit_sha=commit_sha,
                analysis_status=AnalysisStatus.NOT_STARTED
            )
            
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Branch switch failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error switching branch: {str(e)}"
            )
    
    async def clone_branch(self, repo_url: str, branch: str) -> str:
        """
        Clone a specific branch of a repository.
        
        Args:
            repo_url: The repository URL
            branch: The branch to clone
            
        Returns:
            Path to the cloned repository
            
        Raises:
            HTTPException: If cloning fails
        """
        # Validate URL (reuse existing validation)
        from app.services.cloner import validate_github_url
        
        if not validate_github_url(repo_url):
            raise HTTPException(
                status_code=400, 
                detail="Invalid repository URL. Only GitHub and GitLab are supported."
            )
        
        # Create a unique directory for the clone
        repo_id = str(uuid.uuid4())
        temp_path = os.path.join(settings.TEMP_DIR, repo_id)
        
        # Ensure temp dir exists
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        
        try:
            # Clone the specific branch
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, temp_path],
                check=True,
                timeout=30,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            return temp_path
            
        except subprocess.TimeoutExpired:
            # Cleanup if timeout
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)
            raise HTTPException(
                status_code=408, 
                detail="Repository cloning timed out (30s limit)."
            )
        except subprocess.CalledProcessError as e:
            # Cleanup if error
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)
            raise HTTPException(
                status_code=400, 
                detail=f"Git clone failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
        except Exception as e:
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path)
            raise HTTPException(
                status_code=500, 
                detail=f"An unexpected error occurred: {str(e)}"
            )
    
    async def _get_branch_commit_sha_from_bare(self, bare_repo_path: str, branch_ref: str) -> str:
        """Get commit SHA from a bare repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", branch_ref],
                check=True,
                capture_output=True,
                text=True,
                cwd=bare_repo_path
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            # Fallback to HEAD if branch ref fails
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                cwd=bare_repo_path
            )
            return result.stdout.strip()
    
    async def _get_commit_date_from_bare(self, bare_repo_path: str, commit_sha: str) -> datetime:
        """Get commit date from a bare repository."""
        try:
            result = subprocess.run(
                ["git", "show", "-s", "--format=%ci", commit_sha],
                check=True,
                capture_output=True,
                text=True,
                cwd=bare_repo_path
            )
            # Parse git date format: 2024-01-15 10:30:45 +0000
            date_str = result.stdout.strip().split(' +')[0]  # Remove timezone
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except (subprocess.CalledProcessError, ValueError):
            # Fallback to current time if parsing fails
            return datetime.now()