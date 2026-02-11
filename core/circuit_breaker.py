"""
Circuit Breaker Pattern Implementation
Prevents cascading failures by automatically stopping requests to failing services.
"""

import asyncio
import time
from typing import Dict, Optional, Callable, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    Automatically trips when failure threshold is reached,
    then tests recovery after cooldown period.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        half_open_timeout: float = 30.0
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Successes needed in half-open to close
            timeout: Seconds to wait before trying half-open
            half_open_timeout: Seconds to stay in half-open state
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_timeout = half_open_timeout
        
        # Per-service circuit state
        self.circuits: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    def _get_circuit(self, service: str) -> Dict[str, Any]:
        """Get or create circuit state for service"""
        if service not in self.circuits:
            self.circuits[service] = {
                "state": CircuitState.CLOSED,
                "failures": 0,
                "successes": 0,
                "last_failure_time": 0,
                "opened_at": 0,
            }
        return self.circuits[service]
    
    async def call(
        self,
        service: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            service: Service name
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            circuit = self._get_circuit(service)
            
            # Check if circuit is open
            if circuit["state"] == CircuitState.OPEN:
                time_since_open = time.time() - circuit["opened_at"]
                
                if time_since_open >= self.timeout:
                    # Try half-open state
                    circuit["state"] = CircuitState.HALF_OPEN
                    circuit["successes"] = 0
                    logger.info(f"Circuit {service}: OPEN -> HALF_OPEN")
                else:
                    # Still open, reject request
                    raise Exception(
                        f"Circuit breaker OPEN for {service}. "
                        f"Retry in {self.timeout - time_since_open:.1f}s"
                    )
        
        # Try to execute function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - update circuit
            async with self._lock:
                circuit = self._get_circuit(service)
                
                if circuit["state"] == CircuitState.HALF_OPEN:
                    circuit["successes"] += 1
                    
                    if circuit["successes"] >= self.success_threshold:
                        # Close circuit
                        circuit["state"] = CircuitState.CLOSED
                        circuit["failures"] = 0
                        circuit["successes"] = 0
                        logger.info(f"Circuit {service}: HALF_OPEN -> CLOSED")
                
                elif circuit["state"] == CircuitState.CLOSED:
                    # Reset failure counter on success
                    circuit["failures"] = 0
            
            return result
            
        except Exception as e:
            # Failure - update circuit
            async with self._lock:
                circuit = self._get_circuit(service)
                circuit["failures"] += 1
                circuit["last_failure_time"] = time.time()
                
                if circuit["state"] == CircuitState.HALF_OPEN:
                    # Failed in half-open, back to open
                    circuit["state"] = CircuitState.OPEN
                    circuit["opened_at"] = time.time()
                    circuit["failures"] = 0
                    circuit["successes"] = 0
                    logger.warning(f"Circuit {service}: HALF_OPEN -> OPEN")
                
                elif circuit["state"] == CircuitState.CLOSED:
                    if circuit["failures"] >= self.failure_threshold:
                        # Too many failures, open circuit
                        circuit["state"] = CircuitState.OPEN
                        circuit["opened_at"] = time.time()
                        logger.error(
                            f"Circuit {service}: CLOSED -> OPEN "
                            f"(failures: {circuit['failures']})"
                        )
            
            raise
    
    def protect(self, service: str):
        """
        Context manager for circuit breaker protection.
        
        Usage:
            with breaker.protect("api"):
                # code here
        """
        return CircuitBreakerContext(self, service)
    
    def get_state(self, service: str) -> CircuitState:
        """Get current state of circuit for service"""
        circuit = self._get_circuit(service)
        return circuit["state"]
    
    def get_stats(self, service: str) -> Dict[str, Any]:
        """Get statistics for service circuit"""
        circuit = self._get_circuit(service)
        return {
            "state": circuit["state"].value,
            "failures": circuit["failures"],
            "successes": circuit["successes"],
            "last_failure": circuit["last_failure_time"],
        }
    
    def reset(self, service: str):
        """Manually reset circuit for service"""
        if service in self.circuits:
            self.circuits[service] = {
                "state": CircuitState.CLOSED,
                "failures": 0,
                "successes": 0,
                "last_failure_time": 0,
                "opened_at": 0,
            }
            logger.info(f"Circuit {service}: manually reset to CLOSED")


class CircuitBreakerContext:
    """Context manager for circuit breaker"""
    
    def __init__(self, breaker: CircuitBreaker, service: str):
        self.breaker = breaker
        self.service = service
    
    async def __aenter__(self):
        # Check if circuit is open
        async with self.breaker._lock:
            circuit = self.breaker._get_circuit(self.service)
            
            if circuit["state"] == CircuitState.OPEN:
                time_since_open = time.time() - circuit["opened_at"]
                
                if time_since_open < self.breaker.timeout:
                    raise Exception(
                        f"Circuit breaker OPEN for {self.service}. "
                        f"Retry in {self.breaker.timeout - time_since_open:.1f}s"
                    )
                else:
                    # Try half-open
                    circuit["state"] = CircuitState.HALF_OPEN
                    circuit["successes"] = 0
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self.breaker._lock:
            circuit = self.breaker._get_circuit(self.service)
            
            if exc_type is None:
                # Success
                if circuit["state"] == CircuitState.HALF_OPEN:
                    circuit["successes"] += 1
                    
                    if circuit["successes"] >= self.breaker.success_threshold:
                        circuit["state"] = CircuitState.CLOSED
                        circuit["failures"] = 0
                        circuit["successes"] = 0
                
                elif circuit["state"] == CircuitState.CLOSED:
                    circuit["failures"] = 0
            
            else:
                # Failure
                circuit["failures"] += 1
                circuit["last_failure_time"] = time.time()
                
                if circuit["state"] == CircuitState.HALF_OPEN:
                    circuit["state"] = CircuitState.OPEN
                    circuit["opened_at"] = time.time()
                    circuit["failures"] = 0
                    circuit["successes"] = 0
                
                elif circuit["state"] == CircuitState.CLOSED:
                    if circuit["failures"] >= self.breaker.failure_threshold:
                        circuit["state"] = CircuitState.OPEN
                        circuit["opened_at"] = time.time()
        
        return False  # Re-raise exception


# Global circuit breaker instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker(
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 60.0
) -> CircuitBreaker:
    """
    Get or create global circuit breaker instance.
    
    Args:
        failure_threshold: Failures before opening circuit
        success_threshold: Successes to close from half-open
        timeout: Seconds before trying half-open
        
    Returns:
        CircuitBreaker instance
    """
    global _circuit_breaker
    
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout
        )
    
    return _circuit_breaker
