"""
WebSocket Compression Module
Implements permessage-deflate compression for WebSocket connections.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """WebSocket compression levels"""
    NONE = 0
    LOW = 1
    MEDIUM = 6
    HIGH = 9


class WSCompressor:
    """
    WebSocket compression handler.
    
    Features:
    - Permessage-deflate compression
    - Automatic negotiation
    - Fallback to uncompressed
    - Statistics tracking
    """
    
    def __init__(
        self,
        compression_level: CompressionLevel = CompressionLevel.MEDIUM,
        enable_client_max_window_bits: bool = True,
        enable_server_max_window_bits: bool = True
    ):
        """
        Initialize WebSocket compressor.
        
        Args:
            compression_level: Compression level (0-9)
            enable_client_max_window_bits: Enable client window bits
            enable_server_max_window_bits: Enable server window bits
        """
        self.compression_level = compression_level
        self.enable_client_max_window_bits = enable_client_max_window_bits
        self.enable_server_max_window_bits = enable_server_max_window_bits
        
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'bytes_before_compression': 0,
            'bytes_after_compression': 0,
            'bytes_before_decompression': 0,
            'bytes_after_decompression': 0
        }
        
        self._lock = asyncio.Lock()
    
    def get_compression_params(self) -> Dict[str, Any]:
        """
        Get compression parameters for WebSocket connection.
        
        Returns:
            Dictionary of compression parameters
        """
        if self.compression_level == CompressionLevel.NONE:
            return {}
        
        params = {
            'permessage-deflate': {
                'compression_level': self.compression_level.value,
                'client_max_window_bits': 15 if self.enable_client_max_window_bits else None,
                'server_max_window_bits': 15 if self.enable_server_max_window_bits else None,
                'client_no_context_takeover': False,
                'server_no_context_takeover': False
            }
        }
        
        return params
    
    async def track_sent(self, original_size: int, compressed_size: int):
        """
        Track sent message statistics.
        
        Args:
            original_size: Size before compression
            compressed_size: Size after compression
        """
        async with self._lock:
            self.stats['messages_sent'] += 1
            self.stats['bytes_before_compression'] += original_size
            self.stats['bytes_after_compression'] += compressed_size
    
    async def track_received(self, compressed_size: int, decompressed_size: int):
        """
        Track received message statistics.
        
        Args:
            compressed_size: Size before decompression
            decompressed_size: Size after decompression
        """
        async with self._lock:
            self.stats['messages_received'] += 1
            self.stats['bytes_before_decompression'] += compressed_size
            self.stats['bytes_after_decompression'] += decompressed_size
    
    def get_stats(self) -> Dict:
        """Get compression statistics"""
        sent_ratio = (
            (1 - self.stats['bytes_after_compression'] / self.stats['bytes_before_compression']) * 100
            if self.stats['bytes_before_compression'] > 0 else 0
        )
        
        received_ratio = (
            (1 - self.stats['bytes_before_decompression'] / self.stats['bytes_after_decompression']) * 100
            if self.stats['bytes_after_decompression'] > 0 else 0
        )
        
        return {
            'compression_level': self.compression_level.name,
            'messages_sent': self.stats['messages_sent'],
            'messages_received': self.stats['messages_received'],
            'sent_compression_ratio': f"{sent_ratio:.1f}%",
            'received_compression_ratio': f"{received_ratio:.1f}%",
            'bytes_saved_sent': self.stats['bytes_before_compression'] - self.stats['bytes_after_compression'],
            'bytes_saved_received': self.stats['bytes_after_decompression'] - self.stats['bytes_before_decompression']
        }
    
    def should_compress(self, message_size: int) -> bool:
        """
        Determine if message should be compressed.
        
        Args:
            message_size: Size of message in bytes
            
        Returns:
            True if should compress, False otherwise
        """
        if self.compression_level == CompressionLevel.NONE:
            return False
        
        # Don't compress very small messages (overhead not worth it)
        return message_size > 100


# Global compressor instance
_compressor_instance: Optional[WSCompressor] = None


def get_ws_compressor(
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
) -> WSCompressor:
    """
    Get global WebSocket compressor instance.
    
    Args:
        compression_level: Compression level
        
    Returns:
        WSCompressor instance
    """
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = WSCompressor(compression_level=compression_level)
    return _compressor_instance
