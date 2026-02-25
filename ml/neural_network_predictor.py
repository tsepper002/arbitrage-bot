"""
Neural Network Predictor - Real 2-layer neural network using only stdlib + math.
Input(5) → Hidden(8, tanh) → Output(1, sigmoid).
Online backpropagation with gradient descent.
"""
import logging
import math
import random
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_INPUT_SIZE = 5
_HIDDEN_SIZE = 8


class NeuralNetworkPredictor:
    """Real 2-layer neural network for trade profitability prediction."""

    def __init__(self, input_size: int = _INPUT_SIZE, hidden_size: int = _HIDDEN_SIZE,
                 output_size: int = 1):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.is_trained = False
        self.prediction_cache: Dict[str, tuple] = {}
        self.train_steps = 0

        # Xavier-ish initialization
        bound_ih = 1.0 / math.sqrt(input_size)
        bound_ho = 1.0 / math.sqrt(hidden_size)

        random.seed(42)
        # Weights: input→hidden  (hidden_size x input_size)
        self.w_ih = [[random.uniform(-bound_ih, bound_ih)
                       for _ in range(input_size)] for _ in range(hidden_size)]
        self.b_h = [random.uniform(-bound_ih, bound_ih) for _ in range(hidden_size)]
        # Weights: hidden→output  (1 x hidden_size)
        self.w_ho = [random.uniform(-bound_ho, bound_ho) for _ in range(hidden_size)]
        self.b_o = 0.0

        logger.info("✅ NeuralNetworkPredictor initialized (%d→%d→1)",
                     input_size, hidden_size)

    # ----- activation functions ----------------------------------------------

    @staticmethod
    def _tanh(x: float) -> float:
        x = max(-20.0, min(20.0, x))
        return math.tanh(x)

    @staticmethod
    def _sigmoid(x: float) -> float:
        x = max(-20.0, min(20.0, x))
        return 1.0 / (1.0 + math.exp(-x))

    # ----- forward pass ------------------------------------------------------

    def _forward(self, features: List[float]) -> tuple:
        """Returns (hidden_activations, output)."""
        # Pad/truncate to input_size
        x = list(features[:self.input_size])
        while len(x) < self.input_size:
            x.append(0.0)

        # Hidden layer
        h = []
        for j in range(self.hidden_size):
            z = self.b_h[j]
            for i in range(self.input_size):
                z += self.w_ih[j][i] * x[i]
            h.append(self._tanh(z))

        # Output layer
        z_o = self.b_o
        for j in range(self.hidden_size):
            z_o += self.w_ho[j] * h[j]
        output = self._sigmoid(z_o)

        return x, h, output

    # ----- public API --------------------------------------------------------

    def predict(self, features: List[float], symbol: str = "BTC/USDT") -> float:
        """Predict probability of profitable trade [0-1]."""
        try:
            if not features:
                return 0.5

            cache_key = f"{symbol}_{hash(tuple(features[:self.input_size]))}"
            if cache_key in self.prediction_cache:
                ct, cp = self.prediction_cache[cache_key]
                if time.time() - ct < 30:
                    return cp

            _, _, output = self._forward(features)
            self.prediction_cache[cache_key] = (time.time(), output)
            return output
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return 0.5

    def train(self, features, target: float = None, lr: float = 0.01,
              X_train=None, y_train=None, epochs: int = 10):
        """Online backpropagation (single sample) or batch training.

        Backward-compatible: supports old-style train(X_train, y_train, epochs).
        """
        try:
            # Old-style batch call
            if X_train is not None and y_train is not None:
                for _ in range(epochs):
                    for xi, yi in zip(X_train, y_train):
                        self._train_single(list(xi), float(yi), lr)
                self.is_trained = True
                logger.info("✅ Neural network batch training complete (%d epochs)", epochs)
                return

            # New-style single-sample call
            if isinstance(features, list) and target is not None:
                self._train_single(features, target, lr)
                self.train_steps += 1
                self.is_trained = True
                self.prediction_cache.clear()
        except Exception as e:
            logger.error(f"Error training network: {e}")

    def _train_single(self, features: List[float], target: float, lr: float):
        """One step of backpropagation."""
        x, h, output = self._forward(features)
        # Output error (binary cross-entropy derivative simplifies to)
        d_output = output - target  # dL/dz_o for sigmoid + BCE

        # Gradients for hidden→output weights
        for j in range(self.hidden_size):
            self.w_ho[j] -= lr * d_output * h[j]
        self.b_o -= lr * d_output

        # Backprop to hidden layer
        for j in range(self.hidden_size):
            d_h = d_output * self.w_ho[j] * (1.0 - h[j] * h[j])  # tanh derivative
            for i in range(self.input_size):
                self.w_ih[j][i] -= lr * d_h * x[i]
            self.b_h[j] -= lr * d_h

    def predict_batch(self, features_batch: List[List[float]]) -> List[float]:
        """Predict for batch of feature vectors."""
        try:
            return [self.predict(f) for f in features_batch]
        except Exception as e:
            logger.error(f"Error predicting batch: {e}")
            return [0.5] * len(features_batch)


def get_neural_network_predictor():
    """Factory function"""
    return NeuralNetworkPredictor()
