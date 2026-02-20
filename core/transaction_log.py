"""
Transaction Log - Complete audit trail for all trading operations
Records every transaction with full state for recovery and auditing.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib

logger = logging.getLogger(__name__)


class TransactionLog:
    """
    Transaction logging system for complete audit trail.
    
    Features:
    - JSON-based transaction recording
    - State snapshots before/after operations
    - Transaction chaining with checksums
    - Recovery capability from logs
    - Automatic log rotation
    """
    
    def __init__(self, log_dir: str = "transaction_logs", max_log_size_mb: int = 100):
        """
        Initialize transaction logger.
        
        Args:
            log_dir: Directory for transaction logs
            max_log_size_mb: Maximum size per log file before rotation
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_log_size = max_log_size_mb * 1024 * 1024  # Convert to bytes
        self.current_log_file = None
        self.transaction_count = 0
        self.lock = asyncio.Lock()
        
        # Initialize current log file
        self._rotate_log_if_needed()
        
        logger.info(f"TransactionLog initialized: {self.log_dir}")
    
    def _get_current_log_path(self) -> Path:
        """Get current log file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.log_dir / f"transactions_{timestamp}.jsonl"
    
    def _rotate_log_if_needed(self):
        """Rotate log file if it exceeds maximum size."""
        if self.current_log_file is None:
            self.current_log_file = self._get_current_log_path()
            return
        
        if self.current_log_file.exists():
            size = self.current_log_file.stat().st_size
            if size >= self.max_log_size:
                logger.info(f"Rotating transaction log (size: {size / 1024 / 1024:.2f}MB)")
                self.current_log_file = self._get_current_log_path()
    
    def _calculate_checksum(self, data: dict) -> str:
        """Calculate SHA-256 checksum of transaction data."""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    async def log_transaction(
        self,
        operation: str,
        params: dict,
        state_before: Optional[dict] = None,
        state_after: Optional[dict] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Log a transaction with full details.
        
        Args:
            operation: Operation name (e.g., 'execute_trade')
            params: Operation parameters
            state_before: State snapshot before operation
            state_after: State snapshot after operation
            result: Operation result
            error: Error message if operation failed
            metadata: Additional metadata
        
        Returns:
            Transaction ID
        """
        async with self.lock:
            self._rotate_log_if_needed()
            
            transaction_id = f"tx_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.transaction_count:06d}"
            self.transaction_count += 1
            
            transaction = {
                'transaction_id': transaction_id,
                'timestamp': datetime.now().isoformat(),
                'operation': operation,
                'params': params,
                'state_before': state_before,
                'state_after': state_after,
                'result': result,
                'error': error,
                'metadata': metadata or {},
                'success': error is None
            }
            
            # Add checksum
            transaction['checksum'] = self._calculate_checksum(transaction)
            
            # Write to log file
            try:
                with open(self.current_log_file, 'a') as f:
                    f.write(json.dumps(transaction) + '\n')
                
                logger.debug(f"Transaction logged: {transaction_id} ({operation})")
                return transaction_id
            
            except Exception as e:
                logger.error(f"Failed to log transaction: {e}")
                raise
    
    async def get_transaction(self, transaction_id: str) -> Optional[dict]:
        """
        Retrieve transaction by ID.
        
        Args:
            transaction_id: Transaction ID to retrieve
        
        Returns:
            Transaction dict or None if not found
        """
        async with self.lock:
            # Search through all log files
            for log_file in sorted(self.log_dir.glob("transactions_*.jsonl")):
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            
                            transaction = json.loads(line)
                            if transaction.get('transaction_id') == transaction_id:
                                return transaction
                
                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")
        
        return None
    
    async def get_recent_transactions(self, limit: int = 100, operation: Optional[str] = None) -> List[dict]:
        """
        Get recent transactions.
        
        Args:
            limit: Maximum number of transactions to return
            operation: Filter by operation name (optional)
        
        Returns:
            List of transactions
        """
        transactions = []
        
        async with self.lock:
            # Read from most recent log files first
            for log_file in sorted(self.log_dir.glob("transactions_*.jsonl"), reverse=True):
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        
                        # Read from end of file backwards
                        for line in reversed(lines):
                            if not line.strip():
                                continue
                            
                            try:
                                transaction = json.loads(line)
                                
                                # Filter by operation if specified
                                if operation and transaction.get('operation') != operation:
                                    continue
                                
                                transactions.append(transaction)
                                
                                if len(transactions) >= limit:
                                    return transactions
                            
                            except json.JSONDecodeError:
                                continue
                
                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")
        
        return transactions
    
    async def get_failed_transactions(self, limit: int = 100) -> List[dict]:
        """
        Get recent failed transactions.
        
        Args:
            limit: Maximum number to return
        
        Returns:
            List of failed transactions
        """
        failed = []
        
        async with self.lock:
            for log_file in sorted(self.log_dir.glob("transactions_*.jsonl"), reverse=True):
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            
                            transaction = json.loads(line)
                            if not transaction.get('success', True):
                                failed.append(transaction)
                                
                                if len(failed) >= limit:
                                    return failed
                
                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")
        
        return failed
    
    async def recover_state_from_transaction(self, transaction_id: str) -> Optional[dict]:
        """
        Recover state from a specific transaction.
        
        Args:
            transaction_id: Transaction to recover from
        
        Returns:
            State after transaction, or None if not found
        """
        transaction = await self.get_transaction(transaction_id)
        
        if transaction:
            return transaction.get('state_after')
        
        return None
    
    async def verify_transaction_chain(self, start_tx_id: str, end_tx_id: str) -> bool:
        """
        Verify integrity of transaction chain.
        
        Args:
            start_tx_id: Starting transaction ID
            end_tx_id: Ending transaction ID
        
        Returns:
            True if chain is valid
        """
        # Get transactions in range
        transactions = []
        found_start = False
        
        async with self.lock:
            for log_file in sorted(self.log_dir.glob("transactions_*.jsonl")):
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            
                            transaction = json.loads(line)
                            tx_id = transaction.get('transaction_id')
                            
                            if tx_id == start_tx_id:
                                found_start = True
                            
                            if found_start:
                                transactions.append(transaction)
                            
                            if tx_id == end_tx_id:
                                break
                
                except Exception as e:
                    logger.error(f"Error verifying chain: {e}")
                    return False
        
        # Verify checksums
        for transaction in transactions:
            stored_checksum = transaction.pop('checksum', None)
            calculated_checksum = self._calculate_checksum(transaction)
            
            if stored_checksum != calculated_checksum:
                logger.error(f"Checksum mismatch for transaction {transaction['transaction_id']}")
                return False
        
        logger.info(f"Transaction chain verified: {len(transactions)} transactions")
        return True
    
    async def get_stats(self) -> dict:
        """
        Get transaction log statistics.
        
        Returns:
            Statistics dictionary
        """
        total_transactions = 0
        failed_transactions = 0
        total_size = 0
        
        async with self.lock:
            for log_file in self.log_dir.glob("transactions_*.jsonl"):
                try:
                    total_size += log_file.stat().st_size
                    
                    with open(log_file, 'r') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            
                            total_transactions += 1
                            try:
                                transaction = json.loads(line)
                                if not transaction.get('success', True):
                                    failed_transactions += 1
                            except json.JSONDecodeError:
                                continue
                
                except Exception as e:
                    logger.error(f"Error calculating stats: {e}")
        
        return {
            'total_transactions': total_transactions,
            'failed_transactions': failed_transactions,
            'success_rate': (
                (total_transactions - failed_transactions) / total_transactions * 100
                if total_transactions > 0 else 0
            ),
            'total_size_mb': total_size / 1024 / 1024,
            'log_files': len(list(self.log_dir.glob("transactions_*.jsonl")))
        }


# Global instance
_transaction_log: Optional[TransactionLog] = None


def get_transaction_logger(log_dir: str = "transaction_logs") -> TransactionLog:
    """
    Get global transaction logger instance.
    
    Args:
        log_dir: Directory for transaction logs
    
    Returns:
        TransactionLog instance
    """
    global _transaction_log
    
    if _transaction_log is None:
        _transaction_log = TransactionLog(log_dir=log_dir)
    
    return _transaction_log


# Usage example
"""
from core.transaction_log import get_transaction_logger

tx_logger = get_transaction_logger()

# Log a successful trade
await tx_logger.log_transaction(
    operation='execute_trade',
    params={'symbol': 'BTC/USDT', 'amount': 100},
    state_before={'balance': 10000},
    state_after={'balance': 9900, 'position': 100},
    result={'order_id': '12345', 'filled': 100},
    metadata={'strategy': 'arbitrage'}
)

# Log a failed operation
await tx_logger.log_transaction(
    operation='execute_trade',
    params={'symbol': 'BTC/USDT', 'amount': 100},
    state_before={'balance': 10000},
    error='Insufficient balance',
    metadata={'strategy': 'arbitrage'}
)

# Retrieve recent transactions
recent = await tx_logger.get_recent_transactions(limit=10)

# Get failed transactions
failed = await tx_logger.get_failed_transactions(limit=5)

# Get statistics
stats = await tx_logger.get_stats()
print(f"Success rate: {stats['success_rate']:.2f}%")
"""
