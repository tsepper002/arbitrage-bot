"""
Auto Rollback Manager - Automatic transaction rollback on failures
Provides instant recovery from failed operations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RollbackAction:
    """Represents a rollback action."""
    action_id: str
    operation: str
    rollback_func: Callable
    rollback_args: tuple = field(default_factory=tuple)
    rollback_kwargs: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    executed: bool = False


class AutoRollbackManager:
    """
    Manages automatic rollback of failed operations.
    
    Features:
    - Stack-based rollback execution (LIFO)
    - Compensation transaction support
    - Async rollback execution
    - Rollback history tracking
    - Emergency recovery mode
    """
    
    def __init__(self):
        """Initialize auto rollback manager."""
        self.rollback_stack: List[RollbackAction] = []
        self.rollback_history: List[dict] = []
        self.lock = asyncio.Lock()
        self.in_rollback = False
        
        logger.info("AutoRollbackManager initialized")
    
    async def register_rollback(
        self,
        operation: str,
        rollback_func: Callable,
        *rollback_args,
        **rollback_kwargs
    ) -> str:
        """
        Register a rollback action for an operation.
        
        Args:
            operation: Operation name
            rollback_func: Function to call for rollback
            *rollback_args: Arguments for rollback function
            **rollback_kwargs: Keyword arguments for rollback function
        
        Returns:
            Action ID
        """
        async with self.lock:
            action_id = f"rollback_{len(self.rollback_stack)}_{int(datetime.now().timestamp())}"
            
            action = RollbackAction(
                action_id=action_id,
                operation=operation,
                rollback_func=rollback_func,
                rollback_args=rollback_args,
                rollback_kwargs=rollback_kwargs
            )
            
            self.rollback_stack.append(action)
            logger.debug(f"Registered rollback action: {operation} (id={action_id})")
            
            return action_id
    
    async def rollback(self, reason: Optional[str] = None) -> bool:
        """
        Execute all rollback actions in reverse order (LIFO).
        
        Args:
            reason: Reason for rollback
        
        Returns:
            True if all rollbacks successful
        """
        if self.in_rollback:
            logger.warning("Already in rollback, skipping")
            return False
        
        self.in_rollback = True
        success = True
        
        try:
            async with self.lock:
                if not self.rollback_stack:
                    logger.info("No rollback actions to execute")
                    return True
                
                logger.warning(f"Starting rollback of {len(self.rollback_stack)} actions. Reason: {reason}")
                
                # Execute rollbacks in reverse order (LIFO)
                while self.rollback_stack:
                    action = self.rollback_stack.pop()
                    
                    try:
                        logger.info(f"Executing rollback: {action.operation} (id={action.action_id})")
                        
                        # Execute rollback function
                        if asyncio.iscoroutinefunction(action.rollback_func):
                            result = await action.rollback_func(*action.rollback_args, **action.rollback_kwargs)
                        else:
                            result = action.rollback_func(*action.rollback_args, **action.rollback_kwargs)
                        
                        action.executed = True
                        
                        # Record in history
                        self.rollback_history.append({
                            'action_id': action.action_id,
                            'operation': action.operation,
                            'timestamp': datetime.now().isoformat(),
                            'success': True,
                            'reason': reason,
                            'result': str(result) if result else None
                        })
                        
                        logger.info(f"Rollback successful: {action.operation}")
                    
                    except Exception as e:
                        logger.error(f"Rollback failed for {action.operation}: {e}")
                        success = False
                        
                        # Record failure in history
                        self.rollback_history.append({
                            'action_id': action.action_id,
                            'operation': action.operation,
                            'timestamp': datetime.now().isoformat(),
                            'success': False,
                            'reason': reason,
                            'error': str(e)
                        })
                
                logger.info(f"Rollback completed. Success: {success}")
                return success
        
        finally:
            self.in_rollback = False
    
    async def clear_stack(self):
        """Clear rollback stack without executing (use after successful commit)."""
        async with self.lock:
            count = len(self.rollback_stack)
            self.rollback_stack.clear()
            logger.debug(f"Cleared {count} rollback actions")
    
    async def get_stack_size(self) -> int:
        """Get current size of rollback stack."""
        async with self.lock:
            return len(self.rollback_stack)
    
    async def get_rollback_history(self, limit: int = 100) -> List[dict]:
        """
        Get rollback history.
        
        Args:
            limit: Maximum number of history entries to return
        
        Returns:
            List of rollback history entries
        """
        async with self.lock:
            return self.rollback_history[-limit:]
    
    async def emergency_rollback(self, max_attempts: int = 3) -> bool:
        """
        Emergency rollback with retries.
        
        Args:
            max_attempts: Maximum number of retry attempts
        
        Returns:
            True if successful
        """
        logger.critical("EMERGENCY ROLLBACK INITIATED")
        
        for attempt in range(max_attempts):
            try:
                success = await self.rollback(reason=f"Emergency rollback (attempt {attempt + 1})")
                
                if success:
                    logger.info("Emergency rollback successful")
                    return True
                
                if attempt < max_attempts - 1:
                    logger.warning(f"Emergency rollback attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"Emergency rollback attempt {attempt + 1} error: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)
        
        logger.critical("EMERGENCY ROLLBACK FAILED AFTER ALL ATTEMPTS")
        return False
    
    async def get_stats(self) -> dict:
        """
        Get rollback manager statistics.
        
        Returns:
            Statistics dictionary
        """
        async with self.lock:
            total_rollbacks = len(self.rollback_history)
            successful_rollbacks = sum(1 for r in self.rollback_history if r.get('success'))
            
            return {
                'pending_actions': len(self.rollback_stack),
                'total_rollbacks': total_rollbacks,
                'successful_rollbacks': successful_rollbacks,
                'failed_rollbacks': total_rollbacks - successful_rollbacks,
                'success_rate': (
                    successful_rollbacks / total_rollbacks * 100
                    if total_rollbacks > 0 else 0
                ),
                'in_rollback': self.in_rollback
            }
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - rollback on exception."""
        if exc_type is not None:
            logger.warning(f"Exception detected, initiating rollback: {exc_type.__name__}")
            await self.rollback(reason=f"Exception: {exc_type.__name__}: {exc_val}")
            return False  # Re-raise exception
        else:
            # Successful completion, clear stack
            await self.clear_stack()
            return True


# Global instance
_rollback_manager: Optional[AutoRollbackManager] = None


def get_rollback_manager() -> AutoRollbackManager:
    """
    Get global rollback manager instance.
    
    Returns:
        AutoRollbackManager instance
    """
    global _rollback_manager
    
    if _rollback_manager is None:
        _rollback_manager = AutoRollbackManager()
    
    return _rollback_manager


# Usage example
"""
from core.auto_rollback import get_rollback_manager

rollback_mgr = get_rollback_manager()

# Example 1: Manual rollback registration
async def compensate_trade(order_id):
    # Cancel or reverse the trade
    await cancel_order(order_id)

# Execute operation with rollback
order_id = await execute_trade(params)
await rollback_mgr.register_rollback('execute_trade', compensate_trade, order_id)

# If something fails later
if error:
    await rollback_mgr.rollback(reason="Trade execution failed")

# Example 2: Context manager (automatic rollback on exception)
async with get_rollback_manager() as rollback:
    # Step 1: Execute trade
    order_id = await execute_trade(params)
    await rollback.register_rollback('execute_trade', cancel_order, order_id)
    
    # Step 2: Update balance
    await update_balance(amount)
    await rollback.register_rollback('update_balance', restore_balance, old_balance)
    
    # If any exception occurs, both operations will be rolled back automatically
    # If successful, rollback stack is cleared

# Example 3: Emergency rollback
if critical_error:
    await rollback_mgr.emergency_rollback()

# Get statistics
stats = await rollback_mgr.get_stats()
print(f"Pending rollback actions: {stats['pending_actions']}")
"""
