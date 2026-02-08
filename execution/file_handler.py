"""
File Handler - Workspace-Only File Operations for Phase-2A
Provides safe file read/create operations within a configured workspace.

HARD SAFETY RULES:
- ALL paths must be within workspace directory
- Path escape detection (.., symlinks, absolute external paths)
- Read-only for launch_app
- Create-only for type_text (reject if exists)
- No delete, no overwrite, no append
"""
import logging
from pathlib import Path
from typing import Optional
from common.actions import Action, ActionResult

logger = logging.getLogger(__name__)


class FileHandler:
    """
    Safe file operations handler.
    
    Enforces workspace-only access with strict path validation.
    Only supports read (launch_app) and create (type_text) operations.
    """
    
    def __init__(self, workspace_path: str):
        """
        Initialize the file handler.
        
        Args:
            workspace_path: Absolute path to allowed workspace directory
        """
        self.workspace = Path(workspace_path).resolve()
        
        # Create workspace if it doesn't exist
        if not self.workspace.exists():
            self.workspace.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created workspace: {self.workspace}")
        
        if not self.workspace.is_dir():
            raise ValueError(f"Workspace path is not a directory: {workspace_path}")
        
        logger.info(f"FileHandler initialized: workspace={self.workspace}")
    
    def execute_action(self, action: Action) -> ActionResult:
        """
        Execute a file context action.
        
        Args:
            action: Action with context="file"
            
        Returns:
            ActionResult with execution status
        """
        if action.context != "file":
            return ActionResult(
                action=action,
                success=False,
                message="Invalid context",
                error=f"FileHandler only handles file context, got: {action.context}"
            )
        
        try:
            if action.action_type == "launch_app":
                # launch_app + file = READ
                return self._read_file(action)
            elif action.action_type == "type_text":
                # type_text + file = CREATE
                return self._create_file(action)
            elif action.action_type == "close_app":
                # close_app + file = ALWAYS REJECT
                return ActionResult(
                    action=action,
                    success=False,
                    message="Operation not supported",
                    error="close_app not supported in file context"
                )
            else:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Unknown action type",
                    error=f"FileHandler does not support: {action.action_type}"
                )
        
        except Exception as e:
            logger.error(f"File action failed: {e}", exc_info=True)
            return ActionResult(
                action=action,
                success=False,
                message="File action failed",
                error=str(e)
            )
    
    def _validate_path(self, file_path: str) -> Path:
        """
        Validate that path is within workspace.
        
        Args:
            file_path: File path to validate
            
        Returns:
            Resolved Path object
            
        Raises:
            ValueError: If path escapes workspace
        """
        # Resolve to absolute path
        if Path(file_path).is_absolute():
            # Absolute path - must be within workspace
            resolved = Path(file_path).resolve()
        else:
            # Relative path - resolve relative to workspace
            resolved = (self.workspace / file_path).resolve()
        
        # Check if resolved path is within workspace
        try:
            resolved.relative_to(self.workspace)
        except ValueError:
            raise ValueError(
                f"Path escape detected: '{file_path}' resolves outside workspace. "
                f"All file operations must be within: {self.workspace}"
            )
        
        return resolved
    
    def _read_file(self, action: Action) -> ActionResult:
        """
        Read a file (launch_app + file context).
        
        Args:
            action: launch_app action with target=file_path
            
        Returns:
            ActionResult with file content in message
        """
        file_path = action.target
        logger.info(f"Reading file: {file_path}")
        
        try:
            # Validate path
            resolved_path = self._validate_path(file_path)
            
            # Check file exists
            if not resolved_path.exists():
                return ActionResult(
                    action=action,
                    success=False,
                    message="File not found",
                    error=f"File does not exist: {file_path}"
                )
            
            if not resolved_path.is_file():
                return ActionResult(
                    action=action,
                    success=False,
                    message="Not a file",
                    error=f"Path is not a file: {file_path}"
                )
            
            # Read file
            content = resolved_path.read_text(encoding='utf-8')
            
            logger.info(f"[OK] Read file: {resolved_path} ({len(content)} chars)")
            return ActionResult(
                action=action,
                success=True,
                message=f"Read {len(content)} characters from {file_path}"
            )
        
        except ValueError as e:
            # Path validation error
            return ActionResult(
                action=action,
                success=False,
                message="Path validation failed",
                error=str(e)
            )
        except Exception as e:
            return ActionResult(
                action=action,
                success=False,
                message="Read failed",
                error=str(e)
            )
    
    def _create_file(self, action: Action) -> ActionResult:
        """
        Create a new file (type_text + file context).
        
        Args:
            action: type_text action with target=file_path, text=content
            
        Returns:
            ActionResult
        """
        file_path = action.target
        content = action.text
        
        logger.info(f"Creating file: {file_path}")
        
        try:
            # Validate path
            resolved_path = self._validate_path(file_path)
            
            # Check file does NOT exist (CREATE only, no overwrite)
            if resolved_path.exists():
                return ActionResult(
                    action=action,
                    success=False,
                    message="File already exists",
                    error=f"Cannot overwrite existing file: {file_path}. Create-only mode."
                )
            
            # Create parent directories if needed
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            resolved_path.write_text(content, encoding='utf-8')
            
            logger.info(f"[OK] Created file: {resolved_path} ({len(content)} chars)")
            return ActionResult(
                action=action,
                success=True,
                message=f"Created file: {file_path} ({len(content)} characters)"
            )
        
        except ValueError as e:
            # Path validation error
            return ActionResult(
                action=action,
                success=False,
                message="Path validation failed",
                error=str(e)
            )
        except Exception as e:
            return ActionResult(
                action=action,
                success=False,
                message="Create failed",
                error=str(e)
            )
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists within workspace.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if file exists
        """
        try:
            resolved_path = self._validate_path(file_path)
            return resolved_path.exists() and resolved_path.is_file()
        except (ValueError, OSError):
            return False
    
    def read_file_content(self, file_path: str) -> str:
        """
        Read file content for observations (Phase-2B).
        
        Args:
            file_path: File path (relative to workspace)
            
        Returns:
            File content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is invalid or outside workspace
        """
        logger.info(f"Reading file content: {file_path}")
        
        # Validate path
        resolved_path = self._validate_path(file_path)
        
        # Check file exists
        if not resolved_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Read and return content
        content = resolved_path.read_text(encoding='utf-8')
        logger.info(f"[OK] Read file: {resolved_path} ({len(content)} chars)")
        
        return content
