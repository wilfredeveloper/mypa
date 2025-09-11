"""
Centralized parameter processing and validation service.

This service handles all parameter parsing, transformation, and validation
for tools in the personal assistant system, eliminating the need for
tool-specific JSON parsing logic.
"""

from typing import Dict, Any, Optional, Union, Callable, Awaitable
from jsonschema import validate, ValidationError
import json
import re
import logging
from datetime import datetime


class ParameterProcessingError(Exception):
    """Custom exception for parameter processing errors."""
    
    def __init__(self, message: str, tool_name: str = None, original_error: Exception = None):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(message)


class ParameterProcessor:
    """Centralized parameter processing and validation service."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._tool_transformers: Dict[str, Callable] = {
            'google_calendar': self._transform_google_calendar_params,
            # Add other tool transformers here as needed
        }
    
    async def process_baml_parameters(
        self, 
        raw_parameters: Union[str, Dict[str, Any]], 
        tool_schema: Dict[str, Any],
        tool_name: str
    ) -> Dict[str, Any]:
        """
        Process parameters from BAML response with schema validation.
        
        Args:
            raw_parameters: Raw parameters from BAML (string or dict)
            tool_schema: JSON schema for the tool
            tool_name: Name of the tool for error context
            
        Returns:
            Validated and processed parameters
            
        Raises:
            ParameterProcessingError: If processing or validation fails
        """
        try:
            self.logger.debug(f"Processing parameters for {tool_name}: {raw_parameters}")
            
            # Step 1: Parse to dict if string
            if isinstance(raw_parameters, str):
                parsed_params = await self._parse_json_string(raw_parameters)
            else:
                parsed_params = raw_parameters.copy() if raw_parameters else {}
            
            # Step 2: Apply tool-specific transformations
            transformed_params = await self._apply_tool_transformations(
                parsed_params, tool_name
            )
            
            # Step 3: Validate against schema
            validated_params = await self._validate_parameters(
                transformed_params, tool_schema, tool_name
            )
            
            self.logger.debug(f"Successfully processed parameters for {tool_name}")
            return validated_params
            
        except Exception as e:
            if isinstance(e, ParameterProcessingError):
                raise
            raise ParameterProcessingError(
                f"Failed to process parameters for {tool_name}: {str(e)}",
                tool_name=tool_name,
                original_error=e
            ) from e
    
    async def _parse_json_string(self, json_str: str) -> Dict[str, Any]:
        """Parse JSON string with intelligent error recovery."""
        if not json_str or not json_str.strip():
            return {}
            
        json_str = json_str.strip()
        
        # Try standard JSON first
        try:
            result = json.loads(json_str)
            if isinstance(result, dict):
                return result
            else:
                raise ParameterProcessingError(
                    f"Expected JSON object, got {type(result).__name__}: {result}"
                )
        except json.JSONDecodeError:
            self.logger.debug("Standard JSON parsing failed, attempting fixes")
        
        # Apply intelligent fixes
        fixed_json = self._fix_common_json_issues(json_str)
        
        try:
            result = json.loads(fixed_json)
            if isinstance(result, dict):
                self.logger.debug("Successfully parsed JSON after fixes")
                return result
            else:
                raise ParameterProcessingError(
                    f"Expected JSON object after fixes, got {type(result).__name__}: {result}"
                )
        except json.JSONDecodeError as e:
            raise ParameterProcessingError(
                f"Could not parse JSON after fixes: {str(e)}\n"
                f"Original: {json_str}\n"
                f"Fixed: {fixed_json}"
            )
    
    def _fix_common_json_issues(self, json_str: str) -> str:
        """Apply common JSON fixes in a systematic way."""
        fixed = json_str
        
        # 1. Replace single quotes with double quotes
        fixed = fixed.replace("'", '"')
        
        # 2. Quote unquoted keys
        fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)
        
        # 3. Quote unquoted string values (but not numbers/booleans/null)
        def quote_unquoted_values(match):
            value = match.group(1).strip()
            # Don't quote if it's already quoted, or if it's a number, boolean, null, or object/array
            if (value.startswith(('"', '{', '[')) or 
                value.lower() in ['true', 'false', 'null'] or
                re.match(r'^-?\d+\.?\d*([eE][+-]?\d+)?$', value)):
                return match.group(0)
            return f': "{value}"'
        
        fixed = re.sub(r':\s*([^",\[\]{}]+?)(?=\s*[,}])', quote_unquoted_values, fixed)
        
        # 4. Remove trailing commas
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        
        # 5. Fix common datetime patterns
        fixed = re.sub(
            r':\s*([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[^",}\]]*)',
            r': "\1"',
            fixed
        )
        
        return fixed

    async def _apply_tool_transformations(
        self,
        params: Dict[str, Any],
        tool_name: str
    ) -> Dict[str, Any]:
        """Apply tool-specific parameter transformations."""
        transformer = self._tool_transformers.get(tool_name)
        if transformer:
            try:
                return await transformer(params)
            except Exception as e:
                raise ParameterProcessingError(
                    f"Tool transformation failed for {tool_name}: {str(e)}",
                    tool_name=tool_name,
                    original_error=e
                )

        return params

    async def _transform_google_calendar_params(
        self,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform Google Calendar specific parameters."""
        transformed = params.copy()

        # Handle event_data parsing
        if 'event_data' in transformed and isinstance(transformed['event_data'], str):
            try:
                transformed['event_data'] = await self._parse_json_string(transformed['event_data'])
            except ParameterProcessingError as e:
                raise ParameterProcessingError(
                    f"Failed to parse event_data: {str(e)}",
                    tool_name="google_calendar",
                    original_error=e
                )

        # Handle time_range parsing
        if 'time_range' in transformed and isinstance(transformed['time_range'], str):
            try:
                transformed['time_range'] = await self._parse_json_string(transformed['time_range'])
            except ParameterProcessingError as e:
                # For time_range, try to extract key-value pairs manually
                time_range_str = transformed['time_range']
                try:
                    time_range_dict = self._parse_time_range_string(time_range_str)
                    transformed['time_range'] = time_range_dict
                except Exception:
                    raise ParameterProcessingError(
                        f"Failed to parse time_range: {str(e)}",
                        tool_name="google_calendar",
                        original_error=e
                    )

        return transformed

    def _parse_time_range_string(self, time_range_str: str) -> Dict[str, Any]:
        """Parse time_range string using regex extraction."""
        time_range_dict = {}

        # Extract start time
        start_match = re.search(r"start\s*:\s*([^,}]+)", time_range_str)
        if start_match:
            time_range_dict["start"] = start_match.group(1).strip().strip("'\"")

        # Extract end time
        end_match = re.search(r"end\s*:\s*([^,}]+)", time_range_str)
        if end_match:
            time_range_dict["end"] = end_match.group(1).strip().strip("'\"")

        # Extract max_results
        max_match = re.search(r"max_results\s*:\s*([0-9]+)", time_range_str)
        if max_match:
            try:
                time_range_dict["max_results"] = int(max_match.group(1))
            except ValueError:
                pass

        return time_range_dict

    async def _validate_parameters(
        self,
        params: Dict[str, Any],
        schema: Dict[str, Any],
        tool_name: str
    ) -> Dict[str, Any]:
        """Validate parameters against JSON schema."""
        if not schema:
            self.logger.warning(f"No schema provided for {tool_name}, skipping validation")
            return params

        try:
            validate(instance=params, schema=schema)
            return params
        except ValidationError as e:
            error_path = ' -> '.join(str(p) for p in e.absolute_path) if e.absolute_path else 'root'
            raise ParameterProcessingError(
                f"Schema validation failed for {tool_name}: {e.message}\n"
                f"Failed at path: {error_path}\n"
                f"Parameters: {params}",
                tool_name=tool_name,
                original_error=e
            )

    def register_tool_transformer(
        self,
        tool_name: str,
        transformer: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Register a custom transformer for a tool."""
        self._tool_transformers[tool_name] = transformer
        self.logger.info(f"Registered transformer for tool: {tool_name}")

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about parameter processing."""
        return {
            "registered_transformers": list(self._tool_transformers.keys()),
            "processor_version": "1.0.0",
            "created_at": datetime.utcnow().isoformat()
        }
