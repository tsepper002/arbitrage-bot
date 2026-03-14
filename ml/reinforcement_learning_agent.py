"""
Reinforcement Learning Agent - Real Q-learning for trading decisions.
State: discretized (spread_bucket, volatility_bucket, trend_bucket) → 5×5×3 = 75 states.
Actions: TRADE, SKIP, WAIT.  Epsilon-greedy exploration with decay.
"""
import logging
import random
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ACTIONS = ['TRADE', 'SKIP', 'WAIT']
_SPREAD_BINS = 5
_VOL_BINS = 5
_TREND_BINS = 3


class ReinforcementLearningAgent:
    """Q-learning agent for arbitrage trading decisions."""

    def __init__(self, state_size: int = 10, action_size: int = 3):
        self.state_size = state_size
        self.action_size = action_size
        self.actions = ACTIONS[:action_size]

        # Q-table: (state_tuple, action_str) → float
        self.q_table: Dict[tuple, float] = {}

        # Hyper-parameters
        self.gamma = 0.95
        self.learning_rate = 0.1
        self.epsilon = 0.3  # 70% exploitation from start (arbitrage is well-defined)
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995

        self.episode_count = 0
        self.memory: List[dict] = []
        logger.info("✅ ReinforcementLearningAgent initialized")

    # ----- state discretization ----------------------------------------------

    @staticmethod
    def _bucket(value: float, edges: list) -> int:
        """Return bucket index for value given sorted edge list."""
        for i, edge in enumerate(edges):
            if value < edge:
                return i
        return len(edges)

    def _discretize_state(self, features: dict) -> tuple:
        """Convert continuous features to a discrete state tuple."""
        spread = features.get('spread', 0.0)
        volatility = features.get('volatility', 0.0)
        trend = features.get('trend', 0.0)

        spread_edges = [0.0005, 0.001, 0.002, 0.005]   # 5 buckets
        vol_edges = [0.005, 0.01, 0.02, 0.05]           # 5 buckets
        trend_edges = [-0.001, 0.001]                     # 3 buckets

        return (
            self._bucket(spread, spread_edges),
            self._bucket(volatility, vol_edges),
            self._bucket(trend, trend_edges),
        )

    # ----- Q-value helpers ---------------------------------------------------

    def _q(self, state: tuple, action: str) -> float:
        return self.q_table.get((state, action), 0.0)

    def _best_action(self, state: tuple) -> str:
        if not self.actions:
            return 'hold'
        best_a, best_q = self.actions[0], self._q(state, self.actions[0])
        for a in self.actions[1:]:
            qv = self._q(state, a)
            if qv > best_q:
                best_a, best_q = a, qv
        return best_a

    def _max_q(self, state: tuple) -> float:
        return max(self._q(state, a) for a in self.actions)

    # ----- public API --------------------------------------------------------

    def get_action(self, state_features: Any, exploration: bool = True) -> Any:
        """Epsilon-greedy action selection.

        Accepts dict (new API) or list (backward compat).
        Returns action string (new) or int index (if called with list state).
        """
        try:
            # Backward compat: list → convert to dict
            if isinstance(state_features, list):
                features = {
                    'spread': state_features[0] if len(state_features) > 0 else 0,
                    'volatility': state_features[1] if len(state_features) > 1 else 0,
                    'trend': state_features[2] if len(state_features) > 2 else 0,
                }
                return_int = True
            else:
                features = state_features
                return_int = False

            state = self._discretize_state(features)

            if exploration and random.random() < self.epsilon:
                # Bias exploration toward TRADE (60%) since profitable spreads should be taken
                action = random.choices(self.actions, weights=[0.6, 0.2, 0.2], k=1)[0]
            else:
                action = self._best_action(state)

            if return_int:
                return ACTIONS.index(action) if action in ACTIONS else 2
            return action
        except Exception as e:
            logger.error(f"Error getting action: {e}")
            return 2 if isinstance(state_features, list) else 'WAIT'

    def update(self, state, action, reward: float, next_state):
        """Q-table update: Q(s,a) ← Q(s,a) + α [r + γ max_a' Q(s',a') − Q(s,a)]."""
        try:
            s = self._to_state(state)
            ns = self._to_state(next_state)
            a = action if isinstance(action, str) else ACTIONS[min(action, len(ACTIONS) - 1)]

            old_q = self._q(s, a)
            td_target = reward + self.gamma * self._max_q(ns)
            self.q_table[(s, a)] = old_q + self.learning_rate * (td_target - old_q)
        except Exception as e:
            logger.error(f"Error updating Q-table: {e}")

    def remember(self, state, action, reward: float, next_state, done: bool = False):
        """Store experience and do a Q-update."""
        try:
            self.update(state, action, reward, next_state)
            self.memory.append({
                'state': state, 'action': action,
                'reward': reward, 'next_state': next_state, 'done': done
            })
            if len(self.memory) > 10000:
                self.memory = self.memory[-5000:]
            if done:
                self.episode_count += 1
                if self.epsilon > self.epsilon_min:
                    self.epsilon *= self.epsilon_decay
        except Exception as e:
            logger.error(f"Error storing memory: {e}")

    def train(self, batch_size: int = 32):
        """Replay training from memory buffer."""
        try:
            if len(self.memory) < batch_size:
                return
            batch = random.sample(self.memory, batch_size)
            for exp in batch:
                self.update(exp['state'], exp['action'],
                            exp['reward'], exp['next_state'])
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay
            logger.debug("RL train step, epsilon=%.4f, Q-size=%d",
                         self.epsilon, len(self.q_table))
        except Exception as e:
            logger.error(f"Error training agent: {e}")

    # ----- helpers -----------------------------------------------------------

    def _to_state(self, raw) -> tuple:
        if isinstance(raw, dict):
            return self._discretize_state(raw)
        if isinstance(raw, (list, tuple)):
            features = {
                'spread': raw[0] if len(raw) > 0 else 0,
                'volatility': raw[1] if len(raw) > 1 else 0,
                'trend': raw[2] if len(raw) > 2 else 0,
            }
            return self._discretize_state(features)
        return (0, 0, 0)


def get_reinforcement_learning_agent():
    """Factory function"""
    return ReinforcementLearningAgent()
