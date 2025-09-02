"""
Tavily Web Search Tool for Personal Assistant.
"""

import os
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.agents.personal_assistant.tools.base import BaseTool

logger = logging.getLogger(__name__)


class TavilySearchTool(BaseTool):
    """
    Tool for performing web searches using the Tavily Search API.

    This tool provides:
    - Web search with customizable parameters
    - Structured results with title, URL, content, and relevance
    - Rate limiting and error handling
    - Query validation and sanitization
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com"
        
        if not self.api_key:
            logger.warning("TAVILY_API_KEY not found in environment variables")

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute web search using Tavily API.

        Parameters:
            query (str): Search query (required)
            max_results (int, optional): Maximum number of results (default: 5, max: 20)
            search_depth (str, optional): Search depth - 'basic' or 'advanced' (default: 'basic')
            include_domains (list, optional): List of domains to include in search
            exclude_domains (list, optional): List of domains to exclude from search

        Returns:
            Search results with structured data
        """
        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        if not self.api_key:
            return await self.handle_error(
                ValueError("TAVILY_API_KEY not configured"),
                "Missing API key"
            )

        query = parameters.get("query", "").strip()
        if not query:
            return await self.handle_error(
                ValueError("query is required"),
                "Missing search query"
            )

        # Validate and sanitize parameters
        try:
            max_results = int(parameters.get("max_results", 5))
            max_results = min(max(max_results, 1), 20)
        except (ValueError, TypeError):
            max_results = 5

        search_depth = parameters.get("search_depth", "basic")
        if search_depth not in ["basic", "advanced"]:
            search_depth = "basic"

        include_domains = parameters.get("include_domains", [])
        exclude_domains = parameters.get("exclude_domains", [])

        # Sanitize query to prevent injection attacks
        query = self._sanitize_query(query)

        try:
            results = await self._perform_search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_domains=include_domains,
                exclude_domains=exclude_domains
            )

            return await self.create_success_response(
                result={
                    "query": query,
                    "results": results,
                    "total_results": len(results),
                    "search_depth": search_depth
                },
                metadata={
                    "search_timestamp": datetime.utcnow().isoformat(),
                    "api_provider": "tavily"
                }
            )

        except Exception as e:
            return await self.handle_error(e, f"Search query: {query}")

    async def _perform_search(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_domains: List[str],
        exclude_domains: List[str]
    ) -> List[Dict[str, Any]]:
        """Perform the actual search using Tavily API."""
        
        # Prepare request payload
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False
        }

        # Add domain filters if provided
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(
                    f"{self.base_url}/search",
                    json=payload,
                    headers={
                        "Content-Type": "application/json"
                    }
                ) as response:
                    
                    if response.status == 401:
                        raise ValueError("Invalid API key")
                    elif response.status == 429:
                        raise ValueError("Rate limit exceeded")
                    elif response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"API error {response.status}: {error_text}")

                    data = await response.json()
                    return self._format_results(data)

            except aiohttp.ClientError as e:
                raise ValueError(f"Network error: {str(e)}")
            except asyncio.TimeoutError:
                raise ValueError("Search request timed out")

    def _format_results(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Tavily API response into structured results."""
        formatted_results = []
        
        # Get the main results
        results = api_response.get("results", [])
        
        for result in results:
            formatted_result = {
                "title": result.get("title", "").strip(),
                "url": result.get("url", "").strip(),
                "content": result.get("content", "").strip(),
                "score": result.get("score", 0.0),
                "published_date": result.get("published_date"),
                "raw_content": result.get("raw_content", "").strip() if result.get("raw_content") else None
            }
            
            # Only include results with valid title and URL
            if formatted_result["title"] and formatted_result["url"]:
                formatted_results.append(formatted_result)

        return formatted_results

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query to prevent injection attacks."""
        # Remove potentially dangerous characters and limit length
        query = query.strip()
        
        # Remove null bytes and control characters
        query = ''.join(char for char in query if ord(char) >= 32)
        
        # Limit query length
        if len(query) > 500:
            query = query[:500]
            
        return query

    async def is_available(self) -> bool:
        """Check if the Tavily API is available and configured."""
        return bool(self.api_key)

    def get_usage_info(self) -> Dict[str, Any]:
        """Get information about tool usage and limits."""
        return {
            "max_results_limit": 20,
            "supported_search_depths": ["basic", "advanced"],
            "supports_domain_filtering": True,
            "rate_limited": True,
            "requires_api_key": True,
            "api_configured": bool(self.api_key)
        }
