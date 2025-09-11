"""
BAML Utilities for Aivesdrop
Provides utilities for working with BAML (Boundary ML) including collector management
and LLM client utilities for tracking usage and performance.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import asyncio
from dataclasses import dataclass, asdict

# Rate limiting imports
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Import BAML components
try:
    # Try importing from the local baml_client directory
    import sys
    import os

    os.environ["BAML_LOG"] = "error"
    # Add the backend directory to path for imports
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from baml_client.async_client import b  # BAML async client
    from baml_py import Collector  # Import Collector from baml_py
    BAML_AVAILABLE = True
except ImportError as e:
    logging.warning(f"BAML not available: {e}")
    b = None
    Collector = None
    BAML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class UsageMetrics:
    """Data class to store usage metrics from BAML collector."""
    function_name: str
    timestamp: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    duration_ms: Optional[float] = None
    cost_estimate: Optional[float] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class TokenPricing:
    """Token pricing calculator for Gemini models."""

    # Pricing per 1M tokens (as of Jan 2025 - verify current pricing)
    GEMINI_PRICING = {
        "gemini-1.5-flash":    {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro":      {"input": 1.25, "output": 5.00},
        "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    }


    @classmethod
    def calculate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for token usage."""
        if model not in cls.GEMINI_PRICING:
            return 0.0

        pricing = cls.GEMINI_PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class BAMLCollectorManager:
    """Manages BAML collectors for tracking LLM usage."""

    def __init__(self,
                 enable_logging: bool = True,
                 log_file: Optional[str] = None,
                 custom_handlers: Optional[List[Callable[[UsageMetrics], None]]] = None):
        """
        Initialize collector manager.

        Args:
            enable_logging: Enable basic logging of usage metrics
            log_file: Optional file path to save usage logs
            custom_handlers: List of custom functions to handle usage metrics
        """
        self.enable_logging = enable_logging
        self.log_file = log_file
        self.custom_handlers = custom_handlers or []
        self.usage_history: List[UsageMetrics] = []

        # Initialize collector if BAML is available
        if BAML_AVAILABLE and Collector:
            self.collector = Collector()
        else:
            self.collector = None
            logger.warning("BAML Collector not available - usage tracking disabled")

        # Set up logging
        if self.enable_logging:
            self.logger = logging.getLogger(__name__)

    def _extract_usage_metrics(self, function_log: Any, function_name: str) -> UsageMetrics:
        """Extract usage metrics from BAML function log."""
        metrics = UsageMetrics(
            function_name=function_name,
            timestamp=datetime.now().isoformat(),
            success=True  # Default to success, will be updated if errors found
        )

        # Extract timing information
        if hasattr(function_log, 'timing') and function_log.timing:
            if hasattr(function_log.timing, 'duration_ms'):
                metrics.duration_ms = function_log.timing.duration_ms

        # Extract usage information from calls
        calls = getattr(function_log, 'calls', []) or []
        if calls:
            total_input_tokens = 0
            total_output_tokens = 0

            for call in calls:
                # Extract usage information
                if hasattr(call, 'usage') and call.usage:
                    total_input_tokens += getattr(call.usage, 'input_tokens', 0) or 0
                    total_output_tokens += getattr(call.usage, 'output_tokens', 0) or 0

                # Get model information from request
                if hasattr(call, 'http_request') and call.http_request and not metrics.model:
                    request_data = getattr(call.http_request, 'body', None)
                    if request_data and hasattr(request_data, 'model'):
                        metrics.model = request_data.model
                    else:
                        # Default to the model from BAML config
                        metrics.model = "gemini-1.5-flash"

                # Check for errors in HTTP response
                if hasattr(call, 'http_response') and call.http_response:
                    # Check status code for errors
                    status_code = getattr(call.http_response, 'status_code', None)
                    if status_code and status_code >= 400:
                        metrics.success = False
                        response_body = getattr(call.http_response, 'body', None)
                        metrics.error_message = f"HTTP {status_code}: {response_body}" if response_body else f"HTTP {status_code}"

                    # Get finish reason from response
                    if not metrics.finish_reason:
                        response_data = getattr(call.http_response, 'body', None)
                        if response_data and hasattr(response_data, 'candidates') and response_data.candidates:
                            candidate = response_data.candidates[0]
                            if hasattr(candidate, 'finishReason'):
                                metrics.finish_reason = candidate.finishReason

            metrics.input_tokens = total_input_tokens
            metrics.output_tokens = total_output_tokens
            metrics.total_tokens = total_input_tokens + total_output_tokens

            # Calculate cost estimate
            if metrics.model and metrics.input_tokens and metrics.output_tokens:
                metrics.cost_estimate = TokenPricing.calculate_cost(
                    metrics.model, metrics.input_tokens, metrics.output_tokens
                )

        return metrics

    def _log_metrics(self, metrics: UsageMetrics):
        """Log usage metrics."""
        if self.enable_logging:
            cost_str = f"${metrics.cost_estimate:.6f}" if metrics.cost_estimate is not None else "N/A"
            duration_str = f"{metrics.duration_ms}ms" if metrics.duration_ms is not None else "N/A"

            self.logger.info(
                f"BAML Call - Function: {metrics.function_name}, "
                f"Tokens: {metrics.total_tokens}, "
                f"Duration: {duration_str}, "
                f"Cost: {cost_str}, "
                f"Success: {metrics.success}"
            )

        # Save to file if specified
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(asdict(metrics)) + '\n')
            except Exception as e:
                logger.error(f"Failed to write metrics to log file: {e}")

    def process_function_logs(self, function_name: str):
        """Process all function logs from collector."""
        if not self.collector:
            return

        function_logs = self.collector.logs

        for log in function_logs:
            metrics = self._extract_usage_metrics(log, function_name)
            self.usage_history.append(metrics)
            self._log_metrics(metrics)

            # Run custom handlers
            for handler in self.custom_handlers:
                try:
                    handler(metrics)
                except Exception as e:
                    if self.enable_logging:
                        self.logger.error(f"Error in custom handler: {e}")

    def get_total_usage(self) -> Dict[str, Any]:
        """Get aggregated usage statistics."""
        if not self.usage_history:
            return {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "average_duration_ms": 0.0,
            }

        successful_calls = [m for m in self.usage_history if m.success]

        return {
            "total_calls": len(self.usage_history),
            "successful_calls": len(successful_calls),
            "failed_calls": len(self.usage_history) - len(successful_calls),
            "total_tokens": sum(m.total_tokens or 0 for m in successful_calls),
            "total_input_tokens": sum(m.input_tokens or 0 for m in successful_calls),
            "total_output_tokens": sum(m.output_tokens or 0 for m in successful_calls),
            "total_cost": sum(m.cost_estimate or 0 for m in successful_calls),
            "average_duration_ms": sum(m.duration_ms or 0 for m in successful_calls) / len(successful_calls) if successful_calls else 0,
        }

    def clear_history(self):
        """Clear usage history. Note: Collector logs cannot be cleared."""
        self.usage_history.clear()


class BAMLGeminiLLM:
    """
    A utility class for calling Gemini models using BAML with collector tracking.

    This class provides a convenient interface for making LLM calls while automatically
    tracking usage metrics, costs, and performance through BAML's collector system.
    """

    def __init__(self,
                 collector_manager: Optional[BAMLCollectorManager] = None,
                 enable_streaming: bool = False):
        """
        Initialize the BAML Gemini LLM utility.

        Args:
            collector_manager: Optional BAMLCollectorManager instance for tracking
            enable_streaming: Whether to enable streaming responses by default
        """
        self.collector_manager = collector_manager or BAMLCollectorManager()
        self.enable_streaming = enable_streaming

    async def call_function(self,
                          function_name: str,
                          **kwargs) -> Any:
        """
        Call a BAML function with collector tracking.

        Args:
            function_name: Name of the BAML function to call
            **kwargs: Arguments to pass to the BAML function

        Returns:
            The result from the BAML function call
        """
        if not BAML_AVAILABLE or not b:
            raise RuntimeError("BAML is not available - please install baml-py and configure properly")

        try:
            # Get the BAML function dynamically
            if not hasattr(b, function_name):
                raise AttributeError(f"BAML function '{function_name}' not found")

            baml_function = getattr(b, function_name)

            # Prepare options with collector if available
            baml_options = {}
            if self.collector_manager.collector:
                baml_options["collector"] = self.collector_manager.collector

            # Call the function with collector tracking
            result = await baml_function(**kwargs, baml_options=baml_options)

            # Process the logs after the call
            self.collector_manager.process_function_logs(function_name)

            return result

        except Exception as e:
            # Still process logs even if there was an error
            self.collector_manager.process_function_logs(function_name)
            raise e

    async def call_with_options(self,
                              function_name: str,
                              options: Dict[str, Any],
                              **kwargs) -> Any:
        """
        Call a BAML function with custom options and collector tracking.

        Args:
            function_name: Name of the BAML function to call
            options: Custom options to pass to the BAML function
            **kwargs: Arguments to pass to the BAML function

        Returns:
            The result from the BAML function call
        """
        if not BAML_AVAILABLE or not b:
            raise RuntimeError("BAML is not available - please install baml-py and configure properly")

        try:
            if not hasattr(b, function_name):
                raise AttributeError(f"BAML function '{function_name}' not found")

            baml_function = getattr(b, function_name)

            # Merge collector with user options
            merged_options = options.copy()
            if self.collector_manager.collector:
                merged_options["collector"] = self.collector_manager.collector

            result = await baml_function(**kwargs, baml_options=merged_options)

            # Process the logs after the call
            self.collector_manager.process_function_logs(function_name)

            return result

        except Exception as e:
            self.collector_manager.process_function_logs(function_name)
            raise e

    def call_function_stream(self,
                           function_name: str,
                           **kwargs):
        """
        Call a BAML function with streaming enabled.

        Args:
            function_name: Name of the BAML function to call (will use streaming version)
            **kwargs: Arguments to pass to the BAML function

        Returns:
            BAML streaming iterator for partial responses
        """
        if not BAML_AVAILABLE:
            raise RuntimeError("BAML is not available - please install baml-py and configure properly")

        try:
            # Import the async client for streaming
            from baml_client.async_client import b as async_b

            # Get the streaming version of the BAML function from async client
            if not hasattr(async_b.stream, function_name):
                raise AttributeError(f"BAML streaming function '{function_name}' not found")

            baml_stream_function = getattr(async_b.stream, function_name)

            # Prepare options with collector if available
            baml_options = {}
            if self.collector_manager.collector:
                baml_options["collector"] = self.collector_manager.collector

            # Call the streaming function with collector tracking
            # Note: This returns a BamlStream object that supports async iteration
            stream = baml_stream_function(**kwargs, baml_options=baml_options)

            # Return the stream for the caller to iterate over
            return stream

        except Exception as e:
            # Still process logs even if there was an error
            self.collector_manager.process_function_logs(function_name)
            raise e

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return self.collector_manager.get_total_usage()


class RateLimitedBAMLGeminiLLM(BAMLGeminiLLM):
    """
    Enhanced BAML Gemini LLM with built-in rate limiting for free tier usage.

    This class extends BAMLGeminiLLM to add:
    - Rate limiting to respect Gemini free tier limits
    - Automatic retry with exponential backoff
    - Better error handling for quota exceeded errors
    """

    def __init__(self,
                 collector_manager: Optional[BAMLCollectorManager] = None,
                 enable_streaming: bool = False,
                 rate_limit_rpm: int = 8,  # Conservative: 8 requests per minute (under 10 RPM limit)
                 rate_limit_rpd: int = 180):  # Conservative: 180 requests per day (under 200 RPD limit)
        """
        Initialize rate-limited BAML Gemini LLM.

        Args:
            collector_manager: Optional BAMLCollectorManager instance for tracking
            enable_streaming: Whether to enable streaming responses by default
            rate_limit_rpm: Requests per minute limit (default: 8 for free tier)
            rate_limit_rpd: Requests per day limit (default: 180 for free tier)
        """
        super().__init__(collector_manager, enable_streaming)

        # Initialize rate limiters
        self.rpm_limiter = AsyncLimiter(rate_limit_rpm, 60)  # X requests per 60 seconds
        self.rpd_limiter = AsyncLimiter(rate_limit_rpd, 86400)  # X requests per day (86400 seconds)

        logger.info(f"Rate limiting initialized: {rate_limit_rpm} RPM, {rate_limit_rpd} RPD")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((Exception,))  # Adjust for specific Gemini exceptions
    )
    async def call_function(self,
                          function_name: str,
                          **kwargs) -> Any:
        """
        Call a BAML function with rate limiting and retry logic.

        Args:
            function_name: Name of the BAML function to call
            **kwargs: Arguments to pass to the BAML function

        Returns:
            The result from the BAML function call
        """
        # Apply rate limiting before making the call
        async with self.rpm_limiter:  # Respect RPM limit
            async with self.rpd_limiter:  # Respect RPD limit
                try:
                    logger.debug(f"Making rate-limited BAML call to {function_name}")
                    return await super().call_function(function_name, **kwargs)
                except Exception as e:
                    # Log the error for debugging
                    logger.warning(f"BAML call failed for {function_name}: {str(e)}")
                    # Check if it's a rate limit error and add context
                    if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                        logger.error(f"Rate limit exceeded for {function_name}. Consider upgrading to paid tier.")
                    raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((Exception,))
    )
    async def call_with_options(self,
                              function_name: str,
                              options: Dict[str, Any],
                              **kwargs) -> Any:
        """
        Call a BAML function with custom options and rate limiting.

        Args:
            function_name: Name of the BAML function to call
            options: Custom options to pass to the BAML function
            **kwargs: Arguments to pass to the BAML function

        Returns:
            The result from the BAML function call
        """
        # Apply rate limiting before making the call
        async with self.rpm_limiter:  # Respect RPM limit
            async with self.rpd_limiter:  # Respect RPD limit
                try:
                    logger.debug(f"Making rate-limited BAML call to {function_name} with custom options")
                    return await super().call_with_options(function_name, options, **kwargs)
                except Exception as e:
                    # Log the error for debugging
                    logger.warning(f"BAML call with options failed for {function_name}: {str(e)}")
                    # Check if it's a rate limit error and add context
                    if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                        logger.error(f"Rate limit exceeded for {function_name}. Consider upgrading to paid tier.")
                    raise

    def call_function_stream(self,
                           function_name: str,
                           **kwargs):
        """
        Call a BAML function with streaming enabled and rate limiting.

        Args:
            function_name: Name of the BAML function to call (will use streaming version)
            **kwargs: Arguments to pass to the BAML function

        Returns:
            BAML streaming iterator for partial responses
        """
        try:
            logger.debug(f"Making rate-limited BAML streaming call to {function_name}")

            # Call the parent's streaming method
            # Note: For now, we'll return the stream directly and handle rate limiting
            # at the service level if needed. The async client handles the streaming properly.
            stream = super().call_function_stream(function_name, **kwargs)

            return stream

        except Exception as e:
            # Log the error for debugging
            logger.warning(f"BAML streaming call failed for {function_name}: {str(e)}")
            # Check if it's a rate limit error and add context
            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                logger.error(f"Rate limit exceeded for streaming {function_name}. Consider upgrading to paid tier.")
            raise

    def update_rate_limits(self, rpm: int, rpd: int):
        """
        Update rate limits (useful when upgrading tiers).

        Args:
            rpm: New requests per minute limit
            rpd: New requests per day limit
        """
        self.rpm_limiter = AsyncLimiter(rpm, 60)
        self.rpd_limiter = AsyncLimiter(rpd, 86400)
        logger.info(f"Rate limits updated: {rpm} RPM, {rpd} RPD")

    def get_usage_history(self) -> List[UsageMetrics]:
        """Get detailed usage history."""
        return self.collector_manager.usage_history.copy()

    def clear_tracking_data(self):
        """Clear all tracking data."""
        self.collector_manager.clear_history()