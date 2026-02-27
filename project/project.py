"""
Project module for OpenCode.

Handles project management including:
- Project discovery
- VCS (Version Control System) integration
- Project state management
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class VCSType(Enum):
    """Version control system type."""
    GIT = "git"
    HG = "hg"
    SVN = "svn"
    NONE = "none"


@dataclass
class VCSInfo:
    """Version control system information."""
    type: VCSType
    root: Path
    current_branch: Optional[str] = None
    current_commit: Optional[str] = None
    is_dirty: bool = False
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0


@dataclass
class ProjectInfo:
    """Project information."""
    name: str
    root: Path
    vcs: Optional[VCSInfo] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    file_count: int = 0
    languages: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class VCSManager:
    """Manager for version control operations."""
    
    async def detect_vcs(self, path: Path) -> Optional[VCSInfo]:
        """
        Detect VCS for a path.
        
        Args:
            path: Path to check
            
        Returns:
            VCSInfo or None
        """
        path = Path(path)
        
        # Check for Git
        git_dir = path / ".git"
        if git_dir.exists():
            return await self._get_git_info(path)
        
        # Check for Mercurial
        hg_dir = path / ".hg"
        if hg_dir.exists():
            return await self._get_hg_info(path)
        
        # Check for SVN
        svn_dir = path / ".svn"
        if svn_dir.exists():
            return await self._get_svn_info(path)
        
        return None
    
    async def _get_git_info(self, path: Path) -> VCSInfo:
        """Get Git repository info."""
        import subprocess
        
        try:
            # Get current branch
            result = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            branch = stdout.decode('utf-8').strip() if result.returncode == 0 else None
            
            # Get current commit
            result = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            commit = stdout.decode('utf-8').strip() if result.returncode == 0 else None
            
            # Check if dirty
            result = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            is_dirty = bool(stdout.decode('utf-8').strip()) if result.returncode == 0 else False
            
            # Get upstream info
            result = await asyncio.create_subprocess_exec(
                "git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            ahead, behind = 0, 0
            if result.returncode == 0:
                parts = stdout.decode('utf-8').strip().split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])
            
            return VCSInfo(
                type=VCSType.GIT,
                root=path,
                current_branch=branch,
                current_commit=commit,
                is_dirty=is_dirty,
                ahead=ahead,
                behind=behind,
            )
            
        except Exception:
            return VCSInfo(type=VCSType.GIT, root=path)
    
    async def _get_hg_info(self, path: Path) -> VCSInfo:
        """Get Mercurial repository info."""
        # Simplified - would need full implementation
        return VCSInfo(type=VCSType.HG, root=path)
    
    async def _get_svn_info(self, path: Path) -> VCSInfo:
        """Get SVN repository info."""
        # Simplified - would need full implementation
        return VCSInfo(type=VCSType.SVN, root=path)
    
    async def get_status(self, path: Path) -> list[dict]:
        """
        Get VCS status for a path.
        
        Args:
            path: Path to check
            
        Returns:
            List of status entries
        """
        vcs_info = await self.detect_vcs(path)
        
        if not vcs_info or vcs_info.type != VCSType.GIT:
            return []
        
        import subprocess
        
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            
            if result.returncode != 0:
                return []
            
            status_lines = []
            for line in stdout.decode('utf-8').splitlines():
                if len(line) >= 3:
                    status_lines.append({
                        "status": line[:2].strip(),
                        "path": line[3:],
                    })
            
            return status_lines
            
        except Exception:
            return []
    
    async def get_diff(self, path: Path) -> str:
        """
        Get VCS diff for a path.
        
        Args:
            path: Path to check
            
        Returns:
            Diff string
        """
        vcs_info = await self.detect_vcs(path)
        
        if not vcs_info or vcs_info.type != VCSType.GIT:
            return ""
        
        import subprocess
        
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "diff",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                return stdout.decode('utf-8')
            
        except Exception:
            pass
        
        return ""
    
    async def get_log(self, path: Path, limit: int = 10) -> list[dict]:
        """
        Get VCS log for a path.
        
        Args:
            path: Path to check
            limit: Maximum number of entries
            
        Returns:
            List of log entries
        """
        vcs_info = await self.detect_vcs(path)
        
        if not vcs_info or vcs_info.type != VCSType.GIT:
            return []
        
        import subprocess
        
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "log", f"-{limit}", "--format=%H|%an|%ae|%ai|%s",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            
            if result.returncode != 0:
                return []
            
            log_entries = []
            for line in stdout.decode('utf-8').splitlines():
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    log_entries.append({
                        "commit": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    })
            
            return log_entries
            
        except Exception:
            return []


class ProjectManager:
    """Manager for project operations."""
    
    def __init__(self):
        self._vcs_manager = VCSManager()
        self._projects: dict[str, ProjectInfo] = {}
    
    async def discover_project(self, path: Path) -> ProjectInfo:
        """
        Discover project information for a path.
        
        Args:
            path: Path to check
            
        Returns:
            ProjectInfo
        """
        path = Path(path).resolve()
        
        # Find project root (look for common project files)
        project_root = await self._find_project_root(path)
        
        # Get project name
        name = project_root.name
        
        # Get VCS info
        vcs_info = await self._vcs_manager.detect_vcs(project_root)
        
        # Get file count and languages
        file_count, languages = await self._analyze_project(project_root)
        
        # Get timestamps
        try:
            stat = project_root.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime)
            modified_at = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            created_at = modified_at = None
        
        project_info = ProjectInfo(
            name=name,
            root=project_root,
            vcs=vcs_info,
            created_at=created_at,
            modified_at=modified_at,
            file_count=file_count,
            languages=languages,
        )
        
        self._projects[str(project_root)] = project_info
        return project_info
    
    async def _find_project_root(self, path: Path) -> Path:
        """Find the project root starting from a path."""
        # Markers for project root
        markers = [
            ".git",
            ".opencode.json",
            "package.json",
            "pyproject.toml",
            "setup.py",
            "Cargo.toml",
            "go.mod",
            "composer.json",
            "pom.xml",
            "build.gradle",
        ]
        
        current = path
        checked = set()
        
        while current != current.parent and str(current) not in checked:
            checked.add(str(current))
            
            for marker in markers:
                if (current / marker).exists():
                    return current
            
            current = current.parent
        
        return path
    
    async def _analyze_project(self, path: Path) -> tuple[int, list[str]]:
        """
        Analyze a project for file count and languages.
        
        Returns:
            Tuple of (file_count, languages)
        """
        file_count = 0
        language_extensions = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "JavaScript",
            ".tsx": "TypeScript",
            ".rs": "Rust",
            ".go": "Go",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C/C++",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".cs": "C#",
            ".fs": "F#",
            ".ex": "Elixir",
            ".erl": "Erlang",
            ".hs": "Haskell",
            ".clj": "Clojure",
            ".ml": "OCaml",
            ".r": "R",
            ".R": "R",
            ".sql": "SQL",
            ".sh": "Shell",
            ".bash": "Shell",
            ".zsh": "Shell",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".json": "JSON",
            ".xml": "XML",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".less": "Less",
            ".md": "Markdown",
            ".rst": "reStructuredText",
            ".lua": "Lua",
            ".vim": "VimL",
        }
        
        languages_set: set[str] = set()
        
        try:
            for root, dirs, files in os.walk(path):
                # Skip hidden and common ignored directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'vendor', 'target', 'build', 'dist', '__pycache__')]
                
                for file in files:
                    if not file.startswith('.'):
                        file_count += 1
                        
                        # Detect language
                        ext = Path(file).suffix.lower()
                        if ext in language_extensions:
                            languages_set.add(language_extensions[ext])
        except PermissionError:
            pass
        
        return file_count, sorted(list(languages_set))
    
    def get_project(self, path: Path) -> Optional[ProjectInfo]:
        """Get cached project info."""
        return self._projects.get(str(Path(path).resolve()))
    
    def list_projects(self) -> list[ProjectInfo]:
        """List all discovered projects."""
        return list(self._projects.values())
    
    def clear_cache(self) -> None:
        """Clear project cache."""
        self._projects.clear()


# Global project manager instance
_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """Get the global project manager."""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager
