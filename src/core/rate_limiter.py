"""
Adaptive Rate Limiter for AI Gateway
Provides concurrency limiting with adaptive control based on response time and error rate.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict
from enum import Enum

logger = logging.getLogger("ai-gateway.rate_limiter")


class LimitMode(Enum):
    """Rate limit mode enumeration"""
    FIXED = "fixed"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.
    
    Attributes:
        max_concurrency: Maximum concurrent requests. None or 0 enables adaptive mode.
        min_concurrency: Minimum concurrency in adaptive mode.
        max_adaptive_concurrency: Upper limit for adaptive mode.
        response_time_low: Response time below this is considered good (seconds).
        response_time_high: Response time above this is considered slow (seconds).
        error_rate_threshold: Error rate threshold for triggering degradation.
        increase_step: Step size for increasing concurrency.
        decrease_factor: Factor for decreasing concurrency (0.8 means reduce to 80%).
        stats_window_size: Number of recent requests to consider for statistics.
        cooldown_seconds: Cooldown period between adjustments.
    """
    max_concurrency: Optional[int] = None
    min_concurrency: int = 1
    max_adaptive_concurrency: int = 100
    response_time_low: float = 1.0
    response_time_high: float = 5.0
    error_rate_threshold: float = 0.1
    increase_step: int = 2
    decrease_factor: float = 0.8
    stats_window_size: int = 100
    cooldown_seconds: float = 5.0

    @property
    def mode(self) -> LimitMode:
        """Determine the limit mode based on configuration."""
        if self.max_concurrency is None or self.max_concurrency <= 0:
            return LimitMode.ADAPTIVE
        return LimitMode.FIXED


@dataclass
class RequestRecord:
    """
    Record of a single request for statistics.
    
    Attributes:
        timestamp: When the request started.
        response_time: Time taken for the request (seconds).
        is_error: Whether the request resulted in an error.
        status_code: HTTP status code of the response.
    """
    timestamp: float
    response_time: float
    is_error: bool
    status_code: int = 200


@dataclass
class ChannelStats:
    """
    Statistics for a channel using sliding window.
    
    Attributes:
        records: Deque of recent request records.
        total_requests: Total number of requests recorded.
        total_errors: Total number of errors.
        total_response_time: Sum of all response times.
    """
    records: deque = field(default_factory=lambda: deque(maxlen=100))
    total_requests: int = 0
    total_errors: int = 0
    total_response_time: float = 0.0

    def add_record(self, record: RequestRecord):
        """Add a new request record to the statistics."""
        if len(self.records) == self.records.maxlen:
            old_record = self.records[0]
            self.total_requests -= 1
            if old_record.is_error:
                self.total_errors -= 1
            self.total_response_time -= old_record.response_time

        self.records.append(record)
        self.total_requests += 1
        if record.is_error:
            self.total_errors += 1
        self.total_response_time += record.response_time

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time from recent records."""
        if not self.records:
            return 0.0
        return self.total_response_time / len(self.records)

    @property
    def error_rate(self) -> float:
        """Calculate error rate from recent records."""
        if not self.records:
            return 0.0
        return self.total_errors / len(self.records)

    @property
    def sample_count(self) -> int:
        """Get the number of samples in the current window."""
        return len(self.records)

    def reset(self):
        """Reset all statistics."""
        self.records.clear()
        self.total_requests = 0
        self.total_errors = 0
        self.total_response_time = 0.0


class AdaptiveLimiter:
    """
    Adaptive rate limiter that adjusts concurrency based on response time and error rate.
    
    This limiter supports two modes:
    - Fixed mode: Uses a static maximum concurrency limit.
    - Adaptive mode: Dynamically adjusts the limit based on performance metrics.
    
    The adaptive algorithm works as follows:
    1. Monitor response time and error rate in a sliding window.
    2. If response time is low and error rate is low, increase concurrency.
    3. If response time is high, decrease concurrency gradually.
    4. If error rate is high, decrease concurrency aggressively.
    """

    def __init__(self, channel_id: int, channel_name: str, config: RateLimitConfig):
        """
        Initialize the adaptive limiter.
        
        Args:
            channel_id: ID of the channel this limiter is for.
            channel_name: Name of the channel for logging.
            config: Rate limit configuration.
        """
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.config = config
        self.stats = ChannelStats(
            records=deque(maxlen=config.stats_window_size)
        )

        self._semaphore: Optional[asyncio.Semaphore] = None
        self._current_limit: int = 0
        self._last_adjustment_time: float = 0.0
        self._lock = asyncio.Lock()

        self._initialize_limit()

    def _initialize_limit(self):
        """Initialize the concurrency limit based on mode."""
        if self.config.mode == LimitMode.FIXED:
            self._current_limit = self.config.max_concurrency
        else:
            self._current_limit = self.config.min_concurrency

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get or create the semaphore for concurrency control."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._current_limit)
        return self._semaphore

    @property
    def current_limit(self) -> int:
        """Get the current concurrency limit."""
        return self._current_limit

    @property
    def mode(self) -> LimitMode:
        """Get the current limit mode."""
        return self.config.mode

    @property
    def is_adaptive(self) -> bool:
        """Check if the limiter is in adaptive mode."""
        return self.config.mode == LimitMode.ADAPTIVE

    async def acquire(self) -> bool:
        """
        Acquire a slot for processing a request.
        
        Returns:
            True if acquired successfully.
        """
        semaphore = self._get_semaphore()
        await semaphore.acquire()
        return True

    def release(self):
        """Release a slot after request completion."""
        if self._semaphore:
            self._semaphore.release()

    def record_request(
        self,
        response_time: float,
        is_error: bool,
        status_code: int = 200
    ):
        """
        Record a completed request for statistics.
        
        Args:
            response_time: Time taken for the request in seconds.
            is_error: Whether the request resulted in an error.
            status_code: HTTP status code of the response.
        """
        record = RequestRecord(
            timestamp=time.time(),
            response_time=response_time,
            is_error=is_error,
            status_code=status_code
        )
        self.stats.add_record(record)

        if self.is_adaptive:
            self._maybe_adjust_limit()

    def _maybe_adjust_limit(self):
        """
        Check if adjustment is needed and perform it if so.
        
        This method implements the core adaptive algorithm:
        - Increase concurrency when performance is good.
        - Decrease concurrency when response time is high.
        - Aggressively decrease when error rate is high.
        """
        now = time.time()

        if now - self._last_adjustment_time < self.config.cooldown_seconds:
            return

        if self.stats.sample_count < 10:
            return

        avg_response_time = self.stats.avg_response_time
        error_rate = self.stats.error_rate

        old_limit = self._current_limit
        adjusted = False

        if error_rate > self.config.error_rate_threshold:
            new_limit = max(
                self.config.min_concurrency,
                int(self._current_limit * 0.5)
            )
            if new_limit != self._current_limit:
                self._current_limit = new_limit
                adjusted = True
                logger.warning(
                    f"[{self.channel_name}] High error rate ({error_rate:.2%}), "
                    f"reducing concurrency: {old_limit} -> {self._current_limit}"
                )

        elif avg_response_time > self.config.response_time_high:
            new_limit = max(
                self.config.min_concurrency,
                int(self._current_limit * self.config.decrease_factor)
            )
            if new_limit != self._current_limit:
                self._current_limit = new_limit
                adjusted = True
                logger.info(
                    f"[{self.channel_name}] High response time ({avg_response_time:.2f}s), "
                    f"reducing concurrency: {old_limit} -> {self._current_limit}"
                )

        elif (avg_response_time < self.config.response_time_low and
              error_rate < self.config.error_rate_threshold * 0.5):
            new_limit = min(
                self.config.max_adaptive_concurrency,
                self._current_limit + self.config.increase_step
            )
            if new_limit != self._current_limit:
                self._current_limit = new_limit
                adjusted = True
                logger.info(
                    f"[{self.channel_name}] Good performance (response: {avg_response_time:.2f}s, "
                    f"error rate: {error_rate:.2%}), increasing concurrency: {old_limit} -> {self._current_limit}"
                )

        if adjusted:
            self._last_adjustment_time = now
            self._recreate_semaphore()

    def _recreate_semaphore(self):
        """Recreate the semaphore with the new limit."""
        old_semaphore = self._semaphore
        self._semaphore = asyncio.Semaphore(self._current_limit)

        if old_semaphore:
            current_waiters = getattr(old_semaphore, '_waiters', None)
            if current_waiters:
                for waiter in list(current_waiters):
                    if not waiter.done():
                        try:
                            self._semaphore.acquire_nowait()
                        except asyncio.SemaphoreError:
                            break

    def update_config(self, config: RateLimitConfig):
        """
        Update the rate limit configuration.
        
        Args:
            config: New rate limit configuration.
        """
        old_mode = self.config.mode
        self.config = config

        if config.mode == LimitMode.FIXED:
            self._current_limit = config.max_concurrency
            self._recreate_semaphore()
            logger.info(
                f"[{self.channel_name}] Switched to fixed mode, "
                f"concurrency limit: {self._current_limit}"
            )
        elif old_mode == LimitMode.FIXED:
            self._current_limit = config.min_concurrency
            self._recreate_semaphore()
            logger.info(
                f"[{self.channel_name}] Switched to adaptive mode, "
                f"starting concurrency: {self._current_limit}"
            )

    def get_stats(self) -> Dict:
        """
        Get current statistics for monitoring.
        
        Returns:
            Dictionary containing current statistics.
        """
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "mode": self.mode.value,
            "current_limit": self._current_limit,
            "avg_response_time": round(self.stats.avg_response_time, 3),
            "error_rate": round(self.stats.error_rate, 4),
            "sample_count": self.stats.sample_count,
            "total_requests": self.stats.total_requests,
            "total_errors": self.stats.total_errors,
        }

    def reset_stats(self):
        """Reset all statistics."""
        self.stats.reset()
        logger.info(f"[{self.channel_name}] Statistics reset")


class RateLimiterManager:
    """
    Manager for rate limiters across all channels.
    
    This class manages individual limiters for each channel and provides
    a unified interface for acquiring/releasing slots and recording metrics.
    """

    def __init__(self):
        """Initialize the rate limiter manager."""
        self._limiters: Dict[int, AdaptiveLimiter] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_limiter(
        self,
        channel_id: int,
        channel_name: str,
        config: RateLimitConfig
    ) -> AdaptiveLimiter:
        """
        Get an existing limiter or create a new one.
        
        Args:
            channel_id: ID of the channel.
            channel_name: Name of the channel.
            config: Rate limit configuration.
            
        Returns:
            The AdaptiveLimiter for the channel.
        """
        async with self._lock:
            if channel_id in self._limiters:
                limiter = self._limiters[channel_id]
                limiter.update_config(config)
                return limiter

            limiter = AdaptiveLimiter(channel_id, channel_name, config)
            self._limiters[channel_id] = limiter
            return limiter

    def get_limiter(self, channel_id: int) -> Optional[AdaptiveLimiter]:
        """
        Get an existing limiter without creating a new one.
        
        Args:
            channel_id: ID of the channel.
            
        Returns:
            The AdaptiveLimiter if exists, None otherwise.
        """
        return self._limiters.get(channel_id)

    def remove_limiter(self, channel_id: int):
        """
        Remove a limiter for a channel.
        
        Args:
            channel_id: ID of the channel to remove.
        """
        if channel_id in self._limiters:
            del self._limiters[channel_id]

    def get_all_stats(self) -> list:
        """
        Get statistics for all limiters.
        
        Returns:
            List of statistics dictionaries.
        """
        return [limiter.get_stats() for limiter in self._limiters.values()]

    def reset_all_stats(self):
        """Reset statistics for all limiters."""
        for limiter in self._limiters.values():
            limiter.reset_stats()

    async def acquire(self, channel_id: int) -> bool:
        """
        Acquire a slot for a channel.
        
        Args:
            channel_id: ID of the channel.
            
        Returns:
            True if acquired successfully.
            
        Raises:
            KeyError: If no limiter exists for the channel.
        """
        limiter = self._limiters.get(channel_id)
        if not limiter:
            return True
        return await limiter.acquire()

    def release(self, channel_id: int):
        """
        Release a slot for a channel.
        
        Args:
            channel_id: ID of the channel.
        """
        limiter = self._limiters.get(channel_id)
        if limiter:
            limiter.release()

    def record_request(
        self,
        channel_id: int,
        response_time: float,
        is_error: bool,
        status_code: int = 200
    ):
        """
        Record a completed request for a channel.
        
        Args:
            channel_id: ID of the channel.
            response_time: Time taken for the request in seconds.
            is_error: Whether the request resulted in an error.
            status_code: HTTP status code of the response.
        """
        limiter = self._limiters.get(channel_id)
        if limiter:
            limiter.record_request(response_time, is_error, status_code)


class RateLimitContext:
    """
    Context manager for rate-limited request execution.
    
    Usage:
        async with RateLimitContext(manager, channel_id) as ctx:
            # Perform request
            ctx.record_success(response_time)
            # or
            ctx.record_error(response_time, status_code)
    """

    def __init__(
        self,
        manager: RateLimiterManager,
        channel_id: int,
        timeout: float = 30.0
    ):
        """
        Initialize the rate limit context.
        
        Args:
            manager: The rate limiter manager.
            channel_id: ID of the channel.
            timeout: Maximum time to wait for acquiring a slot.
        """
        self.manager = manager
        self.channel_id = channel_id
        self.timeout = timeout
        self._start_time: Optional[float] = None
        self._recorded = False

    async def __aenter__(self) -> "RateLimitContext":
        """Acquire a slot and enter the context."""
        self._start_time = time.time()
        await asyncio.wait_for(
            self.manager.acquire(self.channel_id),
            timeout=self.timeout
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release the slot and record metrics if not already recorded."""
        if not self._recorded and self._start_time:
            response_time = time.time() - self._start_time
            is_error = exc_type is not None
            self.manager.record_request(
                self.channel_id,
                response_time,
                is_error,
                500 if is_error else 200
            )
        self.manager.release(self.channel_id)
        return False

    def record_success(self, response_time: Optional[float] = None):
        """
        Record a successful request.
        
        Args:
            response_time: Optional custom response time. If None, uses elapsed time.
        """
        if self._recorded:
            return
        self._recorded = True

        if response_time is None and self._start_time:
            response_time = time.time() - self._start_time

        if response_time is not None:
            self.manager.record_request(
                self.channel_id,
                response_time,
                False,
                200
            )

    def record_error(
        self,
        response_time: Optional[float] = None,
        status_code: int = 500
    ):
        """
        Record a failed request.
        
        Args:
            response_time: Optional custom response time. If None, uses elapsed time.
            status_code: HTTP status code of the error.
        """
        if self._recorded:
            return
        self._recorded = True

        if response_time is None and self._start_time:
            response_time = time.time() - self._start_time

        if response_time is not None:
            self.manager.record_request(
                self.channel_id,
                response_time,
                True,
                status_code
            )
