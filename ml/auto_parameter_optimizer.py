"""Auto parameter optimizer using various optimization techniques."""
import logging
from typing import Dict, List, Callable, Tuple, Optional
import numpy as np
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class AutoParameterOptimizer:
    """Automatically optimize strategy parameters using multiple methods."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.logger = logging.getLogger(__name__)
        self.best_params = {}
        self.optimization_history = []
        self.config = config or {}
        self.current_params = {}
        self.performance_data = []
        
    def grid_search(self, param_grid: Dict, evaluate_func: Callable, 
                    maximize: bool = True) -> Dict:
        """Perform exhaustive grid search optimization."""
        best_score = float('-inf') if maximize else float('inf')
        best_params = {}
        all_results = []
        
        param_names = list(param_grid.keys())
        param_values = [param_grid[name] for name in param_names]
        total_combinations = np.prod([len(v) for v in param_values])
        
        self.logger.info(f"Grid search: {total_combinations} combinations")
        
        for idx, values in enumerate(self._product(*param_values)):
            params = dict(zip(param_names, values))
            
            try:
                score = evaluate_func(params)
                all_results.append({
                    'params': params,
                    'score': score,
                    'timestamp': datetime.now().isoformat()
                })
                
                is_better = (score > best_score) if maximize else (score < best_score)
                if is_better:
                    best_score = score
                    best_params = params.copy()
                    self.logger.info(f"New best: {best_score} with {best_params}")
                    
            except Exception as e:
                self.logger.error(f"Error evaluating {params}: {e}")
                
            if (idx + 1) % 10 == 0:
                self.logger.info(f"Progress: {idx + 1}/{total_combinations}")
        
        result = {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': all_results,
            'total_evaluated': len(all_results)
        }
        
        self.optimization_history.append({
            'method': 'grid_search',
            'timestamp': datetime.now().isoformat(),
            'result': result
        })
        
        return result
    
    def _product(self, *arrays):
        """Cartesian product of arrays."""
        if not arrays:
            yield ()
            return
        for item in arrays[0]:
            for items in self._product(*arrays[1:]):
                yield (item,) + items
    
    def random_search(self, param_distributions: Dict, n_iterations: int,
                      evaluate_func: Callable, maximize: bool = True) -> Dict:
        """Random search over parameter distributions."""
        best_score = float('-inf') if maximize else float('inf')
        best_params = {}
        all_results = []
        
        self.logger.info(f"Random search: {n_iterations} iterations")
        
        for i in range(n_iterations):
            params = {}
            for param_name, distribution in param_distributions.items():
                if isinstance(distribution, list):
                    params[param_name] = np.random.choice(distribution)
                elif isinstance(distribution, tuple) and len(distribution) == 2:
                    # Assume (min, max) for uniform distribution
                    params[param_name] = np.random.uniform(distribution[0], distribution[1])
                    
            try:
                score = evaluate_func(params)
                all_results.append({
                    'params': params,
                    'score': score,
                    'iteration': i
                })
                
                is_better = (score > best_score) if maximize else (score < best_score)
                if is_better:
                    best_score = score
                    best_params = params.copy()
                    
            except Exception as e:
                self.logger.error(f"Error in iteration {i}: {e}")
                
        return {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': all_results
        }
    
    def bayesian_optimize(self, bounds: Dict, n_iterations: int,
                          evaluate_func: Callable, maximize: bool = True) -> Dict:
        """Bayesian optimization using Gaussian Process (simplified)."""
        best_score = float('-inf') if maximize else float('inf')
        best_params = {}
        observations = []
        
        self.logger.info(f"Bayesian optimization: {n_iterations} iterations")
        
        # Initial random samples
        n_initial = min(5, n_iterations // 3)
        for i in range(n_initial):
            params = {k: np.random.uniform(v[0], v[1]) for k, v in bounds.items()}
            try:
                score = evaluate_func(params)
                observations.append((params, score))
                
                is_better = (score > best_score) if maximize else (score < best_score)
                if is_better:
                    best_score = score
                    best_params = params.copy()
            except Exception as e:
                self.logger.error(f"Error in initial sample {i}: {e}")
        
        # Remaining iterations with acquisition function
        for i in range(n_initial, n_iterations):
            # Simple acquisition: explore regions with high uncertainty
            params = self._acquisition_function(bounds, observations, maximize)
            
            try:
                score = evaluate_func(params)
                observations.append((params, score))
                
                is_better = (score > best_score) if maximize else (score < best_score)
                if is_better:
                    best_score = score
                    best_params = params.copy()
                    self.logger.info(f"Iteration {i}: New best {best_score}")
                    
            except Exception as e:
                self.logger.error(f"Error in iteration {i}: {e}")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'observations': observations,
            'n_iterations': len(observations)
        }
    
    def _acquisition_function(self, bounds: Dict, observations: List,
                              maximize: bool) -> Dict:
        """Simple acquisition function for Bayesian optimization."""
        if not observations:
            return {k: np.random.uniform(v[0], v[1]) for k, v in bounds.items()}
        
        # Exploit best regions with some exploration
        scores = [obs[1] for obs in observations]
        best_idx = np.argmax(scores) if maximize else np.argmin(scores)
        best_obs_params = observations[best_idx][0]
        
        # Add noise for exploration
        noise_scale = 0.1
        params = {}
        for k, v in bounds.items():
            center = best_obs_params.get(k, (v[0] + v[1]) / 2)
            noise = np.random.normal(0, (v[1] - v[0]) * noise_scale)
            params[k] = np.clip(center + noise, v[0], v[1])
            
        return params
    
    def walk_forward_test(self, param_grid: Dict, data_splits: List[Tuple],
                          train_evaluate_func: Callable,
                          test_evaluate_func: Callable) -> Dict:
        """Walk-forward testing for parameter stability."""
        results = []
        
        for split_idx, (train_data, test_data) in enumerate(data_splits):
            self.logger.info(f"Walk-forward split {split_idx + 1}/{len(data_splits)}")
            
            # Optimize on training data
            train_result = self.grid_search(
                param_grid,
                lambda p: train_evaluate_func(p, train_data),
                maximize=True
            )
            
            # Test on validation data
            best_params = train_result['best_params']
            test_score = test_evaluate_func(best_params, test_data)
            
            results.append({
                'split': split_idx,
                'train_score': train_result['best_score'],
                'test_score': test_score,
                'best_params': best_params
            })
            
        avg_test_score = np.mean([r['test_score'] for r in results])
        
        return {
            'results': results,
            'avg_test_score': avg_test_score,
            'n_splits': len(data_splits)
        }
    
    def apply_best_params(self, params: Dict) -> None:
        """Apply optimized parameters."""
        self.current_params = params.copy()
        self.best_params = params.copy()
        self.logger.info(f"Applied parameters: {params}")
        
    def get_param_importance(self, results: List[Dict]) -> Dict:
        """Calculate parameter importance from optimization results."""
        if not results:
            return {}
        
        param_names = list(results[0]['params'].keys())
        importances = {}
        
        for param in param_names:
            values = [r['params'][param] for r in results]
            scores = [r['score'] for r in results]
            
            # Simple correlation as importance
            if len(set(values)) > 1:
                correlation = np.corrcoef(values, scores)[0, 1]
                importances[param] = abs(correlation)
            else:
                importances[param] = 0.0
                
        return importances
    
    def save_optimization_history(self, filepath: str) -> None:
        """Save optimization history to file."""
        with open(filepath, 'w') as f:
            json.dump(self.optimization_history, f, indent=2)
        self.logger.info(f"Saved optimization history to {filepath}")
        
    def load_optimization_history(self, filepath: str) -> None:
        """Load optimization history from file."""
        with open(filepath, 'r') as f:
            self.optimization_history = json.load(f)
        self.logger.info(f"Loaded optimization history from {filepath}")
        
        for i in range(n_iterations):
            # Random sampling (simplified version of Bayesian)
            params = {
                name: np.random.uniform(bounds[name][0], bounds[name][1])
                for name in bounds
            }
            
            # Evaluate
            score = np.random.random()  # Placeholder
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'iterations': n_iterations
        }
    
    def walk_forward_test(self, params: Dict, data: List) -> Dict:
        """Walk-forward testing of parameters."""
        # Split data into windows
        window_size = len(data) // 5
        results = []
        
        for i in range(0, len(data) - window_size, window_size // 2):
            window = data[i:i+window_size]
            # Placeholder evaluation
            score = np.random.random()
            results.append(score)
        
        return {
            'avg_score': np.mean(results) if results else 0,
            'std_score': np.std(results) if results else 0,
            'windows': len(results)
        }
    
    def apply_best_params(self, strategy):
        """Apply best parameters to strategy."""
        if self.best_params:
            for key, value in self.best_params.items():
                setattr(strategy, key, value)
