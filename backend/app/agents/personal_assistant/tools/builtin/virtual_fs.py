"""
Virtual File System Tool for Personal Assistant.

Enhanced to support the four-phase execution model with mandatory session files:
- thoughts.txt: Meta-cognitive analysis and thinking log
- plan.txt: Strategic planning and execution tracking
- web_search_results.txt: Web search results and insights
"""

import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

from app.agents.personal_assistant.tools.base import BaseTool

logger = logging.getLogger(__name__)


class VirtualFile:
    """Represents a virtual file in memory."""

    def __init__(self, filename: str, content: str = "", metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.filename = filename
        self.content = content
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.size = len(content.encode('utf-8'))
        self.version = 1

    def update_content(self, new_content: str) -> None:
        """Update file content and metadata."""
        self.content = new_content
        self.updated_at = datetime.utcnow()
        self.size = len(new_content.encode('utf-8'))
        self.version += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "filename": self.filename,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "size_bytes": self.size,
            "version": self.version
        }


class VirtualFileSystemTool(BaseTool):
    """
    Enhanced Virtual File System for the four-phase execution model.

    This tool provides:
    - In-memory file operations (create, read, update, delete, append, exists)
    - Session-based storage with automatic cleanup
    - File versioning and metadata tracking
    - Content search and filtering capabilities
    - Mandatory session files with structured templates
    - Automatic session initialization
    """

    # Mandatory session files that are automatically created
    MANDATORY_FILES = ["thoughts.txt", "plan.txt", "web_search_results.txt"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files_by_session: Dict[str, Dict[str, VirtualFile]] = {}  # session_id -> {filename -> VirtualFile}
        self._current_session_id = None

    def set_session_context(self, session_id: str, user_timezone: str = "UTC", user_id: str = None) -> None:
        """Set the current session context and initialize mandatory files."""
        self._current_session_id = session_id
        # Initialize session with mandatory files if not already done
        if session_id not in self._files_by_session:
            self._initialize_session(session_id, user_timezone, user_id)

    def _get_session_files(self, session_id: Optional[str] = None) -> Dict[str, VirtualFile]:
        """Get files for a specific session."""
        session_id = session_id or self._current_session_id
        if not session_id:
            return {}

        if session_id not in self._files_by_session:
            self._files_by_session[session_id] = {}
        return self._files_by_session[session_id]

    def _initialize_session(self, session_id: str, user_timezone: str = "UTC", user_id: str = None) -> None:
        """Initialize a new session with mandatory files."""
        try:
            self._files_by_session[session_id] = {}
            session_files = self._files_by_session[session_id]

            current_time = datetime.now(timezone.utc).isoformat()

            # Create thoughts.txt
            thoughts_content = self._get_thoughts_template(session_id, current_time, user_timezone, user_id)
            session_files["thoughts.txt"] = VirtualFile("thoughts.txt", thoughts_content, {"type": "mandatory", "template": "thoughts"})

            # Create plan.txt
            plan_content = self._get_plan_template(session_id, current_time)
            session_files["plan.txt"] = VirtualFile("plan.txt", plan_content, {"type": "mandatory", "template": "plan"})

            # Create web_search_results.txt
            search_content = self._get_search_results_template(session_id, current_time)
            session_files["web_search_results.txt"] = VirtualFile("web_search_results.txt", search_content, {"type": "mandatory", "template": "search_results"})

            logger.info(f"Initialized session {session_id} with {len(self.MANDATORY_FILES)} mandatory files")

        except Exception as e:
            logger.error(f"Failed to initialize session {session_id}: {str(e)}")
            # Ensure session exists even if initialization fails
            if session_id not in self._files_by_session:
                self._files_by_session[session_id] = {}

    def _get_thoughts_template(self, session_id: str, timestamp: str, user_timezone: str, user_id: str) -> str:
        """Get the structured template for thoughts.txt."""
        return f"""SESSION: {session_id}
CREATED: {timestamp}
USER_TIMEZONE: {user_timezone}
USER_ID: {user_id or "unknown"}

=== INITIAL ANALYSIS ===
USER_REQUEST: [To be filled when user makes request]
PRIMARY_GOAL: [Main objective identified]
COMPLEXITY_LEVEL: [Single Tool/Multi-Tool/Complex Multi-Tool]
PLANNING_TYPE: [Procedural/Domain/Hybrid]
REQUIRED_TOOLS: [list of tools needed]
ESTIMATED_STEPS: [number of steps anticipated]

=== THINKING LOG ===
[TIMESTAMP] GOAL_DECOMPOSITION: [broken down sub-goals]
[TIMESTAMP] DEPENDENCIES_IDENTIFIED: [tool dependencies and order]
[TIMESTAMP] RISK_ASSESSMENT: [potential issues or blockers]
[TIMESTAMP] SUCCESS_CRITERIA: [how to measure completion]

=== ONGOING THOUGHTS ===
[Add new analytical thoughts below with timestamps]
"""

    def _get_plan_template(self, session_id: str, timestamp: str) -> str:
        """Get the structured template for plan.txt."""
        return f"""SESSION: {session_id}
PLAN_TYPE: [Procedural/Domain/Hybrid]
CREATED: {timestamp}
LAST_UPDATED: {timestamp}
OVERALL_STATUS: [Planning/In Progress/Completed/Failed/Paused]

=== PLAN OVERVIEW ===
PRIMARY_GOAL: [main user objective]
SUCCESS_DEFINITION: [what constitutes success]
ESTIMATED_DURATION: [time estimate]
TOOLS_REQUIRED: [comprehensive tool list]
CRITICAL_DEPENDENCIES: [must-complete-first items]

=== EXECUTION STEPS ===

[Steps will be added here as plan is created]

=== PLAN METRICS ===
TOTAL_STEPS: 0
COMPLETED_STEPS: 0
FAILED_STEPS: 0
COMPLETION_RATE: 0%
CURRENT_STEP: [step number]

=== FINAL EVALUATION ===
OVERALL_SUCCESS: [Yes/No/Partial]
USER_GOAL_ACHIEVED: [Yes/No/Partially]
ISSUES_ENCOUNTERED: [list of problems]
LESSONS_LEARNED: [insights for future similar requests]
USER_FEEDBACK: [if provided]
"""

    def _get_search_results_template(self, session_id: str, timestamp: str) -> str:
        """Get the structured template for web_search_results.txt."""
        return f"""SESSION: {session_id}
CREATED: {timestamp}

=== SEARCH STRATEGY ===
RESEARCH_OBJECTIVE: [why searches are needed]
SEARCH_SCOPE: [what information is being sought]

=== SEARCH RESULTS LOG ===

[Search results will be added here as searches are performed]

=== SEARCH SUMMARY ===
TOTAL_SEARCHES: 0
MOST_VALUABLE_INSIGHT: [key discovery]
INFORMATION_GAPS: [what still needs research]
"""

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute virtual file system operations.

        Parameters:
            action (str): Action to perform - 'create', 'read', 'update', 'delete', 'append', 'exists', 'list', 'search', 'write'
            file_path (str): Path/name of the file for most operations (supports both file_path and filename)
            filename (str): Alternative parameter name for file path (for backward compatibility)
            content (str, optional): File content for 'create', 'update', 'append', and 'write' actions
            search_term (str, optional): Search term for 'search' action
            metadata (dict, optional): File metadata for 'create' and 'update' actions
            session_id (str, optional): Session ID for session-scoped operations
            user_timezone (str, optional): User timezone for session initialization
            user_id (str, optional): User ID for session initialization

        Returns:
            File system operation result
        """
        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "list").lower()
        session_id = parameters.get("session_id")
        user_timezone = parameters.get("user_timezone", "UTC")
        user_id = parameters.get("user_id")

        # Set session context if provided
        if session_id:
            self.set_session_context(session_id, user_timezone, user_id)

        try:
            # Support both file_path and filename parameters
            filename = parameters.get("file_path") or parameters.get("filename")

            if action in ["create", "write"]:
                content = parameters.get("content", "")
                metadata = parameters.get("metadata", {})

                if not filename:
                    return await self.handle_error(
                        ValueError("file_path is required for 'create/write' action"),
                        "Missing file path"
                    )

                # 'write' action overwrites existing files, 'create' fails if file exists
                return await self._create_or_write_file(filename, content, metadata, overwrite=(action == "write"))

            elif action == "read":
                if not filename:
                    return await self.handle_error(
                        ValueError("file_path is required for 'read' action"),
                        "Missing file path"
                    )
                return await self._read_file(filename)

            elif action == "update":
                content = parameters.get("content")
                metadata = parameters.get("metadata")

                if not filename:
                    return await self.handle_error(
                        ValueError("file_path is required for 'update' action"),
                        "Missing file path"
                    )

                return await self._update_file(filename, content, metadata)

            elif action == "append":
                content = parameters.get("content", "")

                if not filename:
                    return await self.handle_error(
                        ValueError("file_path is required for 'append' action"),
                        "Missing file path"
                    )

                return await self._append_to_file(filename, content)

            elif action == "exists":
                if not filename:
                    return await self.handle_error(
                        ValueError("file_path is required for 'exists' action"),
                        "Missing file path"
                    )
                return await self._check_file_exists(filename)

            elif action == "delete":
                if not filename:
                    return await self.handle_error(
                        ValueError("file_path is required for 'delete' action"),
                        "Missing file path"
                    )
                return await self._delete_file(filename)

            elif action == "list":
                return await self._list_files()

            elif action == "search":
                search_term = parameters.get("search_term")
                if not search_term:
                    return await self.handle_error(
                        ValueError("search_term is required for 'search' action"),
                        "Missing search term"
                    )
                return await self._search_files(search_term)

            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

        except Exception as e:
            return await self.handle_error(e, f"Action: {action}")

    async def _create_or_write_file(self, filename: str, content: str, metadata: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
        """Create a new virtual file or write to existing file."""
        try:
            session_files = self._get_session_files()

            # Check if file already exists
            if filename in session_files and not overwrite:
                return await self.handle_error(
                    ValueError(f"File '{filename}' already exists"),
                    "File already exists"
                )

            # Validate filename
            if not self._is_valid_filename(filename):
                return await self.handle_error(
                    ValueError(f"Invalid filename: {filename}"),
                    "Invalid filename"
                )

            operation = "write" if (filename in session_files and overwrite) else "create"

            # Create or update virtual file
            if filename in session_files and overwrite:
                # Update existing file
                virtual_file = session_files[filename]
                virtual_file.update_content(content)
                if metadata:
                    virtual_file.metadata.update(metadata)
            else:
                # Create new file
                virtual_file = VirtualFile(filename, content, metadata)
                session_files[filename] = virtual_file

            return await self.create_success_response({
                "message": f"File '{filename}' {operation}d successfully",
                "file": virtual_file.to_dict(),
                "operation": operation
            })

        except Exception as e:
            return await self.handle_error(e, f"Creating/writing file: {filename}")

    async def _append_to_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Append content to an existing virtual file."""
        try:
            session_files = self._get_session_files()

            if filename not in session_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            virtual_file = session_files[filename]
            old_size = virtual_file.size

            # Append content
            new_content = virtual_file.content + content
            virtual_file.update_content(new_content)

            return await self.create_success_response({
                "message": f"Content appended to '{filename}' successfully",
                "file": virtual_file.to_dict(),
                "bytes_added": virtual_file.size - old_size,
                "operation": "append"
            })

        except Exception as e:
            return await self.handle_error(e, f"Appending to file: {filename}")

    async def _check_file_exists(self, filename: str) -> Dict[str, Any]:
        """Check if a virtual file exists."""
        try:
            session_files = self._get_session_files()
            exists = filename in session_files

            return await self.create_success_response({
                "exists": exists,
                "filename": filename,
                "operation": "exists"
            })

        except Exception as e:
            return await self.handle_error(e, f"Checking file existence: {filename}")

    async def _read_file(self, filename: str) -> Dict[str, Any]:
        """Read a virtual file."""
        try:
            session_files = self._get_session_files()

            if filename not in session_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            virtual_file = session_files[filename]

            return await self.create_success_response({
                "file": virtual_file.to_dict(),
                "operation": "read"
            })

        except Exception as e:
            return await self.handle_error(e, f"Reading file: {filename}")

    async def _update_file(self, filename: str, content: Optional[str], metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Update a virtual file."""
        try:
            session_files = self._get_session_files()

            if filename not in session_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            virtual_file = session_files[filename]
            old_version = virtual_file.version

            # Update content if provided
            if content is not None:
                virtual_file.update_content(content)

            # Update metadata if provided
            if metadata is not None:
                virtual_file.metadata.update(metadata)
                virtual_file.updated_at = datetime.utcnow()

            return await self.create_success_response({
                "message": f"File '{filename}' updated successfully",
                "file": virtual_file.to_dict(),
                "previous_version": old_version,
                "operation": "update"
            })

        except Exception as e:
            return await self.handle_error(e, f"Updating file: {filename}")

    async def _delete_file(self, filename: str) -> Dict[str, Any]:
        """Delete a virtual file."""
        try:
            session_files = self._get_session_files()

            if filename not in session_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            # Prevent deletion of mandatory files
            if filename in self.MANDATORY_FILES:
                return await self.handle_error(
                    ValueError(f"Cannot delete mandatory file '{filename}'"),
                    "Mandatory file deletion not allowed"
                )

            deleted_file = session_files.pop(filename)

            return await self.create_success_response({
                "message": f"File '{filename}' deleted successfully",
                "deleted_file": {
                    "filename": deleted_file.filename,
                    "size_bytes": deleted_file.size,
                    "version": deleted_file.version
                },
                "operation": "delete"
            })

        except Exception as e:
            return await self.handle_error(e, f"Deleting file: {filename}")

    async def _list_files(self) -> Dict[str, Any]:
        """List all virtual files."""
        try:
            session_files = self._get_session_files()
            files_info = []
            total_size = 0

            for filename, virtual_file in session_files.items():
                file_info = {
                    "filename": filename,
                    "size_bytes": virtual_file.size,
                    "created_at": virtual_file.created_at.isoformat(),
                    "updated_at": virtual_file.updated_at.isoformat(),
                    "version": virtual_file.version,
                    "has_metadata": bool(virtual_file.metadata)
                }
                files_info.append(file_info)
                total_size += virtual_file.size

            # Sort by creation date (newest first)
            files_info.sort(key=lambda x: x["created_at"], reverse=True)

            return await self.create_success_response({
                "files": files_info,
                "total_count": len(files_info),
                "total_size_bytes": total_size,
                "operation": "list"
            })

        except Exception as e:
            return await self.handle_error(e, "Listing files")

    async def _search_files(self, search_term: str) -> Dict[str, Any]:
        """Search for files by content or filename."""
        try:
            session_files = self._get_session_files()
            matching_files = []
            search_term_lower = search_term.lower()

            for filename, virtual_file in session_files.items():
                matches = []

                # Search in filename
                if search_term_lower in filename.lower():
                    matches.append("filename")

                # Search in content
                if search_term_lower in virtual_file.content.lower():
                    matches.append("content")

                    # Find context around matches
                    content_lines = virtual_file.content.split('\n')
                    matching_lines = []
                    for i, line in enumerate(content_lines):
                        if search_term_lower in line.lower():
                            # Add line with context
                            start = max(0, i - 1)
                            end = min(len(content_lines), i + 2)
                            context = content_lines[start:end]
                            matching_lines.append({
                                "line_number": i + 1,
                                "line": line,
                                "context": context
                            })

                    if matching_lines:
                        matches.append({"content_matches": matching_lines})

                # Search in metadata
                if virtual_file.metadata:
                    metadata_str = str(virtual_file.metadata).lower()
                    if search_term_lower in metadata_str:
                        matches.append("metadata")

                if matches:
                    matching_files.append({
                        "filename": filename,
                        "matches": matches,
                        "file_info": {
                            "size_bytes": virtual_file.size,
                            "created_at": virtual_file.created_at.isoformat(),
                            "updated_at": virtual_file.updated_at.isoformat(),
                            "version": virtual_file.version
                        }
                    })

            return await self.create_success_response({
                "search_term": search_term,
                "matching_files": matching_files,
                "total_matches": len(matching_files),
                "operation": "search"
            })

        except Exception as e:
            return await self.handle_error(e, f"Searching files: {search_term}")

    def _is_valid_filename(self, filename: str) -> bool:
        """Validate filename for security and compatibility."""
        if not filename or len(filename) > 255:
            return False

        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
        if any(char in filename for char in invalid_chars):
            return False

        # Check for reserved names (Windows)
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        if filename.upper().split('.')[0] in reserved_names:
            return False

        # Check for path traversal attempts
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            return False

        return True

    async def cleanup_session(self, session_id: Optional[str] = None) -> None:
        """Clean up all files for a specific session."""
        try:
            session_id = session_id or self._current_session_id
            if session_id and session_id in self._files_by_session:
                file_count = len(self._files_by_session[session_id])
                del self._files_by_session[session_id]
                logger.info(f"Cleaned up {file_count} virtual files for session {session_id}")
            else:
                logger.warning(f"No session found for cleanup: {session_id}")
        except Exception as e:
            logger.error(f"Error during session cleanup: {str(e)}")

    def get_storage_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get storage statistics for a session or all sessions."""
        try:
            if session_id:
                # Stats for specific session
                session_files = self._get_session_files(session_id)
                total_files = len(session_files)
                total_size = sum(vf.size for vf in session_files.values())

                file_types = {}
                for filename in session_files.keys():
                    ext = os.path.splitext(filename)[1].lower() or 'no_extension'
                    file_types[ext] = file_types.get(ext, 0) + 1

                return {
                    "session_id": session_id,
                    "total_files": total_files,
                    "total_size_bytes": total_size,
                    "file_types": file_types,
                    "average_file_size": total_size / total_files if total_files > 0 else 0,
                    "mandatory_files_present": sum(1 for f in self.MANDATORY_FILES if f in session_files)
                }
            else:
                # Stats for all sessions
                total_sessions = len(self._files_by_session)
                total_files = sum(len(files) for files in self._files_by_session.values())
                total_size = sum(
                    sum(vf.size for vf in files.values())
                    for files in self._files_by_session.values()
                )

                return {
                    "total_sessions": total_sessions,
                    "total_files": total_files,
                    "total_size_bytes": total_size,
                    "average_files_per_session": total_files / total_sessions if total_sessions > 0 else 0,
                    "average_file_size": total_size / total_files if total_files > 0 else 0
                }
        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}")
            return {"error": str(e)}