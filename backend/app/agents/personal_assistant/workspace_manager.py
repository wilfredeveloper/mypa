"""
Intent-Driven Workspace Manager
Simplified workspace management focused on efficiency and organization.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class IntentDrivenWorkspaceManager:
    """
    Simplified workspace manager for intent-driven execution.
    
    Key principles:
    - Workspace as scratchpad: Store intermediate results, remove when done
    - Organized file structure: Different files for different purposes
    - Minimal overhead: Only create files when actually needed
    - Clear naming: Descriptive filenames that indicate purpose
    """
    
    def __init__(self, tool_registry, task_id: str):
        self.tool_registry = tool_registry
        self.task_id = task_id
        self.virtual_fs = tool_registry._tool_instances.get("virtual_fs") if tool_registry else None
        
    async def create_task_plan_file(self, plan: Dict[str, Any]) -> Optional[str]:
        """Create a structured task plan file."""
        if not self.virtual_fs:
            return None
            
        filename = f"task_plan_{self.task_id}.md"
        content = self._generate_plan_content(plan)
        
        try:
            result = await self.virtual_fs.execute({
                "action": "create",
                "filename": filename,
                "content": content
            })
            
            if result.get("success", False):
                logger.info(f"Created task plan file: {filename}")
                return filename
                
        except Exception as e:
            logger.warning(f"Failed to create task plan file: {str(e)}")
            
        return None
    
    async def create_research_file(self, topic: str) -> Optional[str]:
        """Create a file for storing research findings."""
        if not self.virtual_fs:
            return None
            
        filename = f"research_{self.task_id}.md"
        content = f"""# Research Findings: {topic}

## Topic
{topic}

## Research Date
{datetime.utcnow().isoformat()}

## Findings
*Research results will be added here as they are gathered*

## Sources
*Sources will be listed here*

---
*This file is managed by the Intent-Driven Personal Assistant*
"""
        
        try:
            result = await self.virtual_fs.execute({
                "action": "create",
                "filename": filename,
                "content": content
            })
            
            if result.get("success", False):
                logger.info(f"Created research file: {filename}")
                return filename
                
        except Exception as e:
            logger.warning(f"Failed to create research file: {str(e)}")
            
        return None
    
    async def create_output_file(self, title: str, content_type: str = "report") -> Optional[str]:
        """Create a file for final output/deliverable."""
        if not self.virtual_fs:
            return None
            
        filename = f"{content_type}_{self.task_id}.md"
        content = f"""# {title}

## Created
{datetime.utcnow().isoformat()}

## Content
*Final output will be generated here*

---
*This file contains the final deliverable for the user*
"""
        
        try:
            result = await self.virtual_fs.execute({
                "action": "create",
                "filename": filename,
                "content": content
            })
            
            if result.get("success", False):
                logger.info(f"Created output file: {filename}")
                return filename
                
        except Exception as e:
            logger.warning(f"Failed to create output file: {str(e)}")
            
        return None
    
    async def append_research_finding(self, filename: str, finding: str, source: str = "") -> bool:
        """Append a research finding to the research file."""
        if not self.virtual_fs:
            return False
            
        try:
            # Read current content
            read_result = await self.virtual_fs.execute({
                "action": "read",
                "filename": filename
            })
            
            if not read_result.get("success", False):
                return False
                
            current_content = read_result.get("content", "")
            
            # Add new finding
            timestamp = datetime.utcnow().strftime("%H:%M:%S")
            finding_entry = f"\n### Finding ({timestamp})\n{finding}\n"
            
            if source:
                finding_entry += f"**Source**: {source}\n"
            
            # Insert before the Sources section
            if "## Sources" in current_content:
                updated_content = current_content.replace("## Sources", f"{finding_entry}\n## Sources")
            else:
                updated_content = current_content + finding_entry
            
            # Update the file
            update_result = await self.virtual_fs.execute({
                "action": "update",
                "filename": filename,
                "content": updated_content
            })
            
            return update_result.get("success", False)
            
        except Exception as e:
            logger.warning(f"Failed to append research finding: {str(e)}")
            return False
    
    async def update_plan_progress(self, filename: str, todo_id: str, status: str) -> bool:
        """Update the progress of a specific todo in the plan file."""
        if not self.virtual_fs:
            return False
            
        try:
            # Read current content
            read_result = await self.virtual_fs.execute({
                "action": "read",
                "filename": filename
            })
            
            if not read_result.get("success", False):
                return False
                
            current_content = read_result.get("content", "")
            
            # Update status icons
            status_icons = {
                "pending": "⏳",
                "in_progress": "🔄", 
                "completed": "✅",
                "failed": "❌"
            }
            
            icon = status_icons.get(status, "⏳")
            
            # Find and replace the todo status
            lines = current_content.split('\n')
            updated_lines = []
            
            for line in lines:
                if f"(ID: {todo_id})" in line:
                    # Replace the status icon
                    for old_icon in status_icons.values():
                        if old_icon in line:
                            line = line.replace(old_icon, icon)
                            break
                updated_lines.append(line)
            
            updated_content = '\n'.join(updated_lines)
            
            # Add execution log entry
            if status == "completed":
                log_entry = f"\n- {datetime.utcnow().isoformat()}: Completed todo {todo_id}"
                if "## Execution Log" in updated_content:
                    updated_content = updated_content.replace(
                        "## Execution Log",
                        f"## Execution Log{log_entry}"
                    )
            
            # Update the file
            update_result = await self.virtual_fs.execute({
                "action": "update",
                "filename": filename,
                "content": updated_content
            })
            
            return update_result.get("success", False)
            
        except Exception as e:
            logger.warning(f"Failed to update plan progress: {str(e)}")
            return False
    
    async def create_final_deliverable(self, filename: str, content: str) -> bool:
        """Create or update the final deliverable file."""
        if not self.virtual_fs:
            return False
            
        try:
            # Check if file exists
            read_result = await self.virtual_fs.execute({
                "action": "read",
                "filename": filename
            })
            
            if read_result.get("success", False):
                # File exists, update it
                current_content = read_result.get("content", "")
                
                # Replace the content section
                if "## Content" in current_content:
                    parts = current_content.split("## Content")
                    if len(parts) >= 2:
                        header = parts[0] + "## Content"
                        footer_parts = parts[1].split("---")
                        footer = "---" + footer_parts[-1] if len(footer_parts) > 1 else ""
                        
                        updated_content = f"{header}\n{content}\n\n{footer}"
                    else:
                        updated_content = current_content + f"\n\n## Content\n{content}"
                else:
                    updated_content = current_content + f"\n\n## Content\n{content}"
                
                result = await self.virtual_fs.execute({
                    "action": "update",
                    "filename": filename,
                    "content": updated_content
                })
            else:
                # File doesn't exist, create it
                full_content = f"""# Final Deliverable

## Created
{datetime.utcnow().isoformat()}

## Content
{content}

---
*This file contains the final deliverable for the user*
"""
                result = await self.virtual_fs.execute({
                    "action": "create",
                    "filename": filename,
                    "content": full_content
                })
            
            return result.get("success", False)
            
        except Exception as e:
            logger.warning(f"Failed to create final deliverable: {str(e)}")
            return False
    
    async def cleanup_workspace(self, keep_files: List[str] = None) -> bool:
        """Clean up workspace files, optionally keeping specified files."""
        if not self.virtual_fs:
            return False
            
        keep_files = keep_files or []
        
        try:
            # List all files
            list_result = await self.virtual_fs.execute({"action": "list"})
            
            if not list_result.get("success", False):
                return False
                
            files = list_result.get("files", [])
            task_files = [f for f in files if self.task_id in f]
            
            # Delete files not in keep_files list
            for filename in task_files:
                if filename not in keep_files:
                    try:
                        await self.virtual_fs.execute({
                            "action": "delete",
                            "filename": filename
                        })
                        logger.info(f"Cleaned up workspace file: {filename}")
                    except Exception as e:
                        logger.warning(f"Failed to delete file {filename}: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to cleanup workspace: {str(e)}")
            return False
    
    def _generate_plan_content(self, plan: Dict[str, Any]) -> str:
        """Generate markdown content for the plan file."""
        content = f"""# Task Plan: {self.task_id}

## Plan Summary
{plan.get('plan_summary', 'No summary provided')}

## Success Criteria
{plan.get('success_criteria', 'Complete all todos successfully')}

## Estimated Time
{plan.get('total_estimated_minutes', 0)} minutes

## Todo List
"""
        
        todos = plan.get('todos', [])
        for i, todo in enumerate(todos, 1):
            status_icon = "⏳" if todo.get('status') == "pending" else "✅" if todo.get('status') == "completed" else "🔄"
            content += f"""
### {i}. {status_icon} {todo.get('title', 'Untitled')} (ID: {todo.get('id', 'unknown')})
- **Description**: {todo.get('description', 'No description')}
- **Estimated Time**: {todo.get('estimated_minutes', 0)} minutes
- **Tool Required**: {todo.get('tool_required') or 'None'}
- **Status**: {todo.get('status', 'pending')}
- **Dependencies**: {', '.join(todo.get('dependencies', [])) if todo.get('dependencies') else 'None'}
"""

        content += f"""

## Execution Log
- Plan created: {datetime.utcnow().isoformat()}

---
*This plan is managed by the Intent-Driven Personal Assistant*
"""
        
        return content
