"""
Virtual File System Tool for Personal Assistant.
"""

import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
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
    Virtual File System for temporary data storage during task execution.

    This tool provides:
    - In-memory file operations (create, read, update, delete)
    - Session-based storage with automatic cleanup
    - File versioning and metadata tracking
    - Content search and filtering capabilities
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._virtual_files: Dict[str, VirtualFile] = {}  # filename -> VirtualFile
        self._session_id = None

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute virtual file system operations.

        Parameters:
            action (str): Action to perform - 'create', 'read', 'update', 'delete', 'list', 'search'
            filename (str): Name of the file for most operations
            content (str, optional): File content for 'create' and 'update' actions
            search_term (str, optional): Search term for 'search' action
            metadata (dict, optional): File metadata for 'create' and 'update' actions

        Returns:
            File system operation result
        """
        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "list").lower()

        try:
            if action == "create":
                filename = parameters.get("filename")
                content = parameters.get("content", "")
                metadata = parameters.get("metadata", {})

                if not filename:
                    return await self.handle_error(
                        ValueError("filename is required for 'create' action"),
                        "Missing filename"
                    )

                return await self._create_file(filename, content, metadata)

            elif action == "read":
                filename = parameters.get("filename")
                if not filename:
                    return await self.handle_error(
                        ValueError("filename is required for 'read' action"),
                        "Missing filename"
                    )
                return await self._read_file(filename)

            elif action == "update":
                filename = parameters.get("filename")
                content = parameters.get("content")
                metadata = parameters.get("metadata")

                if not filename:
                    return await self.handle_error(
                        ValueError("filename is required for 'update' action"),
                        "Missing filename"
                    )

                return await self._update_file(filename, content, metadata)

            elif action == "delete":
                filename = parameters.get("filename")
                if not filename:
                    return await self.handle_error(
                        ValueError("filename is required for 'delete' action"),
                        "Missing filename"
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

    async def _create_file(self, filename: str, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new virtual file."""
        try:
            # Check if file already exists
            if filename in self._virtual_files:
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

            # Create virtual file
            virtual_file = VirtualFile(filename, content, metadata)
            self._virtual_files[filename] = virtual_file

            return await self.create_success_response({
                "message": f"File '{filename}' created successfully",
                "file": virtual_file.to_dict(),
                "operation": "create"
            })

        except Exception as e:
            return await self.handle_error(e, f"Creating file: {filename}")

    async def _read_file(self, filename: str) -> Dict[str, Any]:
        """Read a virtual file."""
        try:
            if filename not in self._virtual_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            virtual_file = self._virtual_files[filename]

            return await self.create_success_response({
                "file": virtual_file.to_dict(),
                "operation": "read"
            })

        except Exception as e:
            return await self.handle_error(e, f"Reading file: {filename}")

    async def _update_file(self, filename: str, content: Optional[str], metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Update a virtual file."""
        try:
            if filename not in self._virtual_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            virtual_file = self._virtual_files[filename]
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
            if filename not in self._virtual_files:
                return await self.handle_error(
                    ValueError(f"File '{filename}' not found"),
                    "File not found"
                )

            deleted_file = self._virtual_files.pop(filename)

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
            files_info = []
            total_size = 0

            for filename, virtual_file in self._virtual_files.items():
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
            matching_files = []
            search_term_lower = search_term.lower()

            for filename, virtual_file in self._virtual_files.items():
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

    async def cleanup_session(self) -> None:
        """Clean up all files for the current session."""
        try:
            file_count = len(self._virtual_files)
            self._virtual_files.clear()
            logger.info(f"Cleaned up {file_count} virtual files for session")
        except Exception as e:
            logger.error(f"Error during session cleanup: {str(e)}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_files = len(self._virtual_files)
        total_size = sum(vf.size for vf in self._virtual_files.values())

        file_types = {}
        for filename in self._virtual_files.keys():
            ext = os.path.splitext(filename)[1].lower() or 'no_extension'
            file_types[ext] = file_types.get(ext, 0) + 1

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "file_types": file_types,
            "average_file_size": total_size / total_files if total_files > 0 else 0
        }