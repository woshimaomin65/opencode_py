"""
File routes for OpenCode server.

Provides API endpoints for file operations:
- Search text and files
- List and read files
- Get file status (git)
- Find symbols (LSP)
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from opencode.file import (
    list_directory,
    read_file,
    get_file_info,
    FileInfo,
)
from opencode.file.ripgrep import search as ripgrep_search, Match
from opencode.lsp import workspace_symbol, Symbol
from opencode.project import get_project_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/file", tags=["file"])


# GET /file/find - Find text
@router.get("/find")
async def find_text(
    pattern: str = Query(..., description="Text pattern to search for"),
):
    """
    Find text.
    
    Search for text patterns across files in the project using ripgrep.
    """
    try:
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        cwd = current_project.directory if current_project else "."
        
        result = await ripgrep_search(
            cwd=cwd,
            pattern=pattern,
            limit=10,
        )
        return [match.data if hasattr(match, 'data') else match for match in result]
    except Exception as e:
        logger.error(f"Error searching text: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /file/find/file - Find files
@router.get("/find/file")
async def find_files(
    query: str = Query(..., description="File name or pattern to search for"),
    dirs: Optional[str] = Query(None, description="Include directories (true/false)"),
    type: Optional[str] = Query(None, description="Type filter (file/directory)"),
    limit: Optional[int] = Query(10, ge=1, le=200, description="Maximum number of results"),
):
    """
    Find files.
    
    Search for files or directories by name or pattern in the project directory.
    """
    try:
        from opencode.file import search_files
        
        include_dirs = dirs != "false"
        results = await search_files(
            query=query,
            limit=limit,
            include_dirs=include_dirs,
            type_filter=type,
        )
        return results
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /file/find/symbol - Find symbols
@router.get("/find/symbol")
async def find_symbols(
    query: str = Query(..., description="Symbol name to search for"),
):
    """
    Find symbols.
    
    Search for workspace symbols like functions, classes, and variables using LSP.
    """
    try:
        # LSP symbol search may not be fully implemented yet
        result = await workspace_symbol(query)
        return [symbol.model_dump() if hasattr(symbol, 'model_dump') else symbol for symbol in result]
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        # Return empty list if LSP is not available
        return []


# GET /file/file - List files
@router.get("/file")
async def list_files(
    path: str = Query(..., description="Directory path to list"),
):
    """
    List files.
    
    List files and directories in a specified path.
    """
    try:
        content = await list_directory(path)
        return [node.model_dump() if hasattr(node, 'model_dump') else node for node in content]
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /file/file/content - Read file
@router.get("/file/content")
async def read_file_content(
    path: str = Query(..., description="File path to read"),
):
    """
    Read file.
    
    Read the content of a specified file.
    """
    try:
        content = await read_file(path)
        return content if isinstance(content, dict) else {"content": content}
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /file/file/status - Get file status
@router.get("/file/status")
async def get_file_status():
    """
    Get file status.
    
    Get the git status of all files in the project.
    """
    try:
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        
        if not current_project:
            return []
        
        # Get git status
        status = await project_manager.get_file_status(current_project.directory)
        return [info.model_dump() if hasattr(info, 'model_dump') else info for info in status]
    except Exception as e:
        logger.error(f"Error getting file status: {e}")
        raise HTTPException(status_code=400, detail=str(e))
