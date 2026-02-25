"""
Auto Parameter Tuner - Real parameter optimization using UCB1.
Uses Upper Confidence Bound algorithm to balance exploration vs exploitation
when searching for optimal trading parameters.
"""
import logging
import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Parameter search space
_PARAM_RANGES = {
    'min_roi': (0.0005, 0.01),
    'max_exposure': (50.0, 500.0),
    'safety_factor': (0.5, 2.0),
    'scan_interval': (0.5, 10.0),
}

_NUM_ARMS = 20  # discretized parameter sets to explore


class AutoParameterTuner:
    """Tunes strategy parameters using UCB1 multi-armed bandit."""

    def __init__(self):
        self.parameter_history: List[dict] = []
        self.best_parameters: Dict[str, Any] = {}
        self.performance_scores: Dict[str, float] = {}

        # UCB1 state: list of (params_dict, total_reward, count)
        self._arms: List[dict] = []
        self._total_pulls = 0

        # Generate initial arms (random parameter sets)
        random.seed(int(time.time()) % 2**31)
        for _ in range(_NUM_ARMS):
            params = {}
            for name, (lo, hi) in _PARAM_RANGES.items():
                params[name] = round(random.uniform(lo, hi), 6)
            self._arms.append({'params': params, 'total_reward': 0.0,
                               'count': 0, 'rewards': []})

        logger.info("✅ AutoParameterTuner initialized (%d arms)", len(self._arms))

    # ----- core API ----------------------------------------------------------

    def record_performance(self, params: Dict, profit: float, trades: int = 1,
                           strategy_name: str = '', performance: float = None):
        """Record a parameter set's performance result.

        Backward compat: also accepts (strategy_name, parameters, performance).
        """
        try:
            reward = performance if performance is not None else profit
            self.parameter_history.append({
                'parameters': dict(params),
                'profit': profit,
                'trades': trades,
                'reward': reward,
                'timestamp': time.time(),
            })
            if len(self.parameter_history) > 2000:
                self.parameter_history = self.parameter_history[-1000:]

            # Match to nearest arm and update
            arm = self._find_nearest_arm(params)
            if arm is not None:
                arm['total_reward'] += reward
                arm['count'] += 1
                arm['rewards'].append(reward)
                self._total_pulls += 1

            # Track global best
            if not self.best_parameters or reward > self.performance_scores.get('best', float('-inf')):
                self.best_parameters = dict(params)
                self.performance_scores['best'] = reward
        except Exception as e:
            logger.error(f"Error recording performance: {e}")

    def suggest_parameters(self) -> Dict[str, Any]:
        """Suggest next parameter set to try using UCB1."""
        try:
            # If any arm untried, explore it first
            for arm in self._arms:
                if arm['count'] == 0:
                    return dict(arm['params'])

            if self._total_pulls == 0:
                return dict(self._arms[0]['params'])

            # UCB1: argmax( mean_reward + c * sqrt(ln(N) / n_i) )
            log_total = math.log(self._total_pulls)
            best_ucb = float('-inf')
            best_arm = self._arms[0]

            for arm in self._arms:
                mean_r = arm['total_reward'] / arm['count']
                exploration = math.sqrt(2.0 * log_total / arm['count'])
                ucb = mean_r + exploration
                if ucb > best_ucb:
                    best_ucb = ucb
                    best_arm = arm

            # Add small perturbation for diversity
            suggested = {}
            for name, val in best_arm['params'].items():
                lo, hi = _PARAM_RANGES.get(name, (val * 0.5, val * 2.0))
                noise = random.gauss(0, (hi - lo) * 0.05)
                suggested[name] = round(max(lo, min(hi, val + noise)), 6)

            return suggested
        except Exception as e:
            logger.error(f"Error suggesting parameters: {e}")
            return {name: (lo + hi) / 2 for name, (lo, hi) in _PARAM_RANGES.items()}

    def get_best_parameters(self, strategy_name: str = '') -> Dict[str, Any]:
        """Return the best-performing parameter set found so far."""
        try:
            if self.best_parameters:
                return dict(self.best_parameters)
            # Fallback: midpoint of ranges
            return {name: round((lo + hi) / 2, 6)
                    for name, (lo, hi) in _PARAM_RANGES.items()}
        except Exception as e:
            logger.error(f"Error getting best params: {e}")
            return {}

    def tune(self, strategy_name: str = '', param_ranges: Dict[str, tuple] = None,
             performance_metric: str = 'sharpe_ratio') -> Dict[str, Any]:
        """Backward-compatible tune method."""
        try:
            if param_ranges:
                for name, (lo, hi) in param_ranges.items():
                    _PARAM_RANGES[name] = (lo, hi)
            return self.suggest_parameters()
        except Exception as e:
            logger.error(f"Error in tune: {e}")
            return {}

    # ----- internals ---------------------------------------------------------

    def _find_nearest_arm(self, params: dict) -> Optional[dict]:
        """Find the arm closest to the given parameter set."""
        best_dist = float('inf')
        best_arm = None
        for arm in self._arms:
            dist = 0.0
            for name in _PARAM_RANGES:
                lo, hi = _PARAM_RANGES[name]
                rng = hi - lo if hi > lo else 1.0
                v1 = (params.get(name, 0.0) - lo) / rng
                v2 = (arm['params'].get(name, 0.0) - lo) / rng
                dist += (v1 - v2) ** 2
            if dist < best_dist:
                best_dist = dist
                best_arm = arm
        return best_arm


def get_auto_parameter_tuner():
    """Factory function"""
    return AutoParameterTuner()
