"""
Lazy Loader Module
Implements lazy loading of modules to reduce startup time and memory usage.
"""
import asyncio
import importlib
import sys
from typing import Any, Dict, Set, Optional, Callable
from collections import defaultdict
import logging
import time

logger = logging.getLogger(__name__)


class LazyModule:
    """Lazy-loaded module wrapper"""
    
    def __init__(self, module_name: str, loader: 'LazyLoader'):
        self.module_name = module_name
        self.loader = loader
        self._module: Optional[Any] = None
        self._loading = False
    
    def __getattr__(self, name: str) -> Any:
        """Load module on first attribute access"""
        if self._module is None and not self._loading:
            self._loading = True
            self._module = self.loader._load_module(self.module_name)
            self._loading = False
        
        if self._module is None:
            raise ImportError(f"Failed to load module: {self.module_name}")
        
        return getattr(self._module, name)


class LazyLoader:
    """
    Lazy module loader.
    
    Features:
    - Load modules on-demand
    - Track dependencies
    - Preload critical modules
    - Memory efficiency
    """
    
    def __init__(self, critical_modules: Set[str] = None):
        """
        Initialize lazy loader.
        
        Args:
            critical_modules: Modules to preload immediately
        """
        self.critical_modules = critical_modules or set()
        self.loaded_modules: Dict[str, Any] = {}
        self.lazy_modules: Dict[str, LazyModule] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.load_times: Dict[str, float] = {}
        self.stats = {
            'modules_registered': 0,
            'modules_loaded': 0,
            'total_load_time': 0.0
        }
        self._lock = asyncio.Lock()
    
    def register_module(
        self,
        module_name: str,
        depends_on: Set[str] = None,
        critical: bool = False
    ) -> LazyModule:
        """
        Register a module for lazy loading.
        
        Args:
            module_name: Full module name (e.g., 'core.arbitrage')
            depends_on: Set of module dependencies
            critical: If True, preload immediately
            
        Returns:
            LazyModule wrapper
        """
        if critical:
            self.critical_modules.add(module_name)
        
        if depends_on:
            self.dependencies[module_name] = depends_on
        
        if module_name not in self.lazy_modules:
            self.lazy_modules[module_name] = LazyModule(module_name, self)
            self.stats['modules_registered'] += 1
        
        # Preload if critical
        if critical and module_name not in self.loaded_modules:
            self._load_module(module_name)
        
        return self.lazy_modules[module_name]
    
    def _load_module(self, module_name: str) -> Any:
        """
        Load a module and its dependencies.
        
        Args:
            module_name: Module name to load
            
        Returns:
            Loaded module
        """
        if module_name in self.loaded_modules:
            return self.loaded_modules[module_name]
        
        start_time = time.time()
        
        try:
            # Load dependencies first
            if module_name in self.dependencies:
                for dep in self.dependencies[module_name]:
                    if dep not in self.loaded_modules:
                        self._load_module(dep)
            
            # Load the module
            logger.debug(f"Loading module: {module_name}")
            module = importlib.import_module(module_name)
            self.loaded_modules[module_name] = module
            
            load_time = time.time() - start_time
            self.load_times[module_name] = load_time
            self.stats['modules_loaded'] += 1
            self.stats['total_load_time'] += load_time
            
            logger.info(f"Loaded {module_name} in {load_time*1000:.1f}ms")
            
            return module
            
        except Exception as e:
            logger.error(f"Failed to load {module_name}: {e}")
            raise
    
    def preload_critical(self):
        """Preload all critical modules"""
        logger.info(f"Preloading {len(self.critical_modules)} critical modules")
        
        for module_name in self.critical_modules:
            if module_name not in self.loaded_modules:
                try:
                    self._load_module(module_name)
                except Exception as e:
                    logger.error(f"Failed to preload {module_name}: {e}")
    
    def get_module(self, module_name: str) -> Any:
        """
        Get a module, loading it if necessary.
        
        Args:
            module_name: Module name
            
        Returns:
            Loaded module
        """
        if module_name not in self.loaded_modules:
            return self._load_module(module_name)
        return self.loaded_modules[module_name]
    
    def is_loaded(self, module_name: str) -> bool:
        """Check if module is loaded"""
        return module_name in self.loaded_modules
    
    def get_stats(self) -> Dict:
        """Get loader statistics"""
        return {
            'modules_registered': self.stats['modules_registered'],
            'modules_loaded': self.stats['modules_loaded'],
            'modules_pending': len(self.lazy_modules) - self.stats['modules_loaded'],
            'total_load_time_ms': f"{self.stats['total_load_time']*1000:.1f}",
            'critical_modules': len(self.critical_modules),
            'avg_load_time_ms': (
                f"{(self.stats['total_load_time'] / self.stats['modules_loaded'])*1000:.1f}"
                if self.stats['modules_loaded'] > 0 else "0.0"
            )
        }
    
    def get_load_order(self) -> list:
        """Get the order modules were loaded in"""
        return sorted(
            self.load_times.items(),
            key=lambda x: self.load_times.get(x[0], float('inf'))
        )


# Global loader instance
_loader_instance: Optional[LazyLoader] = None


def get_lazy_loader(critical_modules: Set[str] = None) -> LazyLoader:
    """
    Get global lazy loader instance.
    
    Args:
        critical_modules: Modules to preload
        
    Returns:
        LazyLoader instance
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = LazyLoader(critical_modules=critical_modules)
    return _loader_instance
