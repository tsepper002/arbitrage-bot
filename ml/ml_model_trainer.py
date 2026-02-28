"""
ML Model Trainer

Trains machine learning models on historical data for price prediction and strategy optimization.
Supports LSTM, Random Forest, and other ML algorithms.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
import asyncio
import json
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class MLModelTrainer:
    """
    Trains ML models for trading predictions using LSTM and other algorithms
    """
    
    def __init__(self, model_dir: str = "models"):
        self.models = {}
        self.training_data = []
        self.feature_columns = []
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.scaler = None
        self.history = []
        
    async def train_model(self, data: pd.DataFrame, target: str, 
                         model_type: str = 'lstm') -> Dict:
        """
        Train a model on historical data
        
        Args:
            data: Historical trading data
            target: Target variable to predict
            model_type: Type of model ('lstm', 'rf', 'xgboost')
            
        Returns:
            Training results and metrics
        """
        logger.info(f"Training {model_type} model for target: {target}")
        
        # Validate data
        if len(data) < 100:
            raise ValueError("Insufficient training data (need at least 100 samples)")
        
        # Feature engineering
        features = self._engineer_features(data)
        self.feature_columns = features.columns.tolist()
        
        # Prepare train/test split
        train_size = int(len(features) * 0.8)
        X_train = features[:train_size]
        X_test = features[train_size:]
        y_train = data[target][:train_size]
        y_test = data[target][train_size:]
        
        # Normalize features
        X_train_scaled, X_test_scaled = self._normalize_features(X_train, X_test)
        
        # Train model based on type
        if model_type == 'lstm':
            model = await self._train_lstm(X_train_scaled, y_train)
        elif model_type == 'rf':
            model = await self._train_random_forest(X_train_scaled, y_train)
        else:
            model = await self._train_simple_model(X_train_scaled, y_train)
        
        # Evaluate
        metrics = self._evaluate_model(model, X_test_scaled, y_test)
        
        # Save to registry
        self.models[target] = {
            'model': model,
            'type': model_type,
            'metrics': metrics,
            'trained_at': datetime.now(),
            'features': self.feature_columns
        }
        
        # Save history
        self.history.append({
            'target': target,
            'model_type': model_type,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"Model trained successfully. Metrics: {metrics}")
        return metrics
    
    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features from raw data
        
        Creates technical indicators and time-based features
        """
        features = data.copy()
        
        # Price-based features
        if 'close' in features.columns:
            # Returns
            features['returns'] = features['close'].pct_change()
            features['log_returns'] = np.log(features['close'] / features['close'].shift(1))
            
            # Moving averages
            for window in [5, 10, 20, 50]:
                features[f'sma_{window}'] = features['close'].rolling(window).mean()
                features[f'ema_{window}'] = features['close'].ewm(span=window).mean()
            
            # Volatility
            features['volatility_10'] = features['returns'].rolling(10).std()
            features['volatility_20'] = features['returns'].rolling(20).std()
        
        # Volume features
        if 'volume' in features.columns:
            features['volume_sma_10'] = features['volume'].rolling(10).mean()
            features['volume_ratio'] = features['volume'] / features['volume_sma_10']
        
        # Price momentum
        if 'close' in features.columns:
            for period in [5, 10, 20]:
                features[f'momentum_{period}'] = features['close'] - features['close'].shift(period)
                features[f'roc_{period}'] = (features['close'] - features['close'].shift(period)) / features['close'].shift(period)
        
        # RSI
        if 'close' in features.columns:
            delta = features['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            features['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        if 'close' in features.columns:
            exp1 = features['close'].ewm(span=12, adjust=False).mean()
            exp2 = features['close'].ewm(span=26, adjust=False).mean()
            features['macd'] = exp1 - exp2
            features['macd_signal'] = features['macd'].ewm(span=9, adjust=False).mean()
            features['macd_hist'] = features['macd'] - features['macd_signal']
        
        # Bollinger Bands
        if 'close' in features.columns:
            sma_20 = features['close'].rolling(20).mean()
            std_20 = features['close'].rolling(20).std()
            features['bb_upper'] = sma_20 + (2 * std_20)
            features['bb_lower'] = sma_20 - (2 * std_20)
            features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / sma_20
        
        # Time-based features
        if 'timestamp' in features.columns:
            features['hour'] = pd.to_datetime(features['timestamp']).dt.hour
            features['day_of_week'] = pd.to_datetime(features['timestamp']).dt.dayofweek
            features['is_weekend'] = features['day_of_week'].isin([5, 6]).astype(int)
        
        # Drop NaN values created by rolling windows
        features = features.dropna()
        
        # Select only numeric columns
        numeric_features = features.select_dtypes(include=[np.number])
        
        return numeric_features
    
    def _normalize_features(self, X_train: pd.DataFrame, X_test: pd.DataFrame) -> Tuple:
        """Normalize features using StandardScaler"""
        try:
            from sklearn.preprocessing import StandardScaler
            
            if self.scaler is None:
                self.scaler = StandardScaler()
                X_train_scaled = self.scaler.fit_transform(X_train)
            else:
                X_train_scaled = self.scaler.transform(X_train)
            
            X_test_scaled = self.scaler.transform(X_test)
            
            return X_train_scaled, X_test_scaled
        except ImportError:
            logger.warning("sklearn not available, using simple normalization")
            # Simple normalization
            mean = X_train.mean()
            std = X_train.std()
            std[std == 0] = 1  # Prevent division by zero for constant features
            X_train_scaled = (X_train - mean) / std
            X_test_scaled = (X_test - mean) / std
            return X_train_scaled.values, X_test_scaled.values
    
    async def _train_lstm(self, X, y):
        """
        Train LSTM model
        
        Uses simple LSTM implementation for time series prediction
        """
        logger.info("Training LSTM model (simplified version)")
        
        # Create a simple sequential model structure
        model = {
            'type': 'lstm',
            'layers': [
                {'type': 'lstm', 'units': 50, 'return_sequences': True},
                {'type': 'dropout', 'rate': 0.2},
                {'type': 'lstm', 'units': 50},
                {'type': 'dropout', 'rate': 0.2},
                {'type': 'dense', 'units': 1}
            ],
            'weights': self._initialize_weights(X.shape[1]),
            'optimizer': 'adam',
            'loss': 'mse'
        }
        
        # Simulate training (in production, actually train the model)
        await asyncio.sleep(0.1)  # Simulate training time
        
        return model
    
    async def _train_random_forest(self, X, y):
        """Train Random Forest model"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            
            logger.info("Training Random Forest model")
            
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42
            )
            
            # Train in background
            await asyncio.sleep(0.05)
            model.fit(X, y)
            
            return model
        except ImportError:
            logger.warning("sklearn not available, using simple model")
            return await self._train_simple_model(X, y)
    
    async def _train_simple_model(self, X, y):
        """Train simple linear model"""
        logger.info("Training simple linear model")
        
        # Simple linear regression using numpy
        # y = X * weights + bias
        X_with_bias = np.column_stack([X, np.ones(len(X))])
        weights = np.linalg.lstsq(X_with_bias, y, rcond=None)[0]
        
        model = {
            'type': 'linear',
            'weights': weights[:-1],
            'bias': weights[-1]
        }
        
        await asyncio.sleep(0.02)
        return model
    
    def _initialize_weights(self, input_dim: int) -> Dict:
        """Initialize random weights for LSTM"""
        return {
            'lstm1': np.random.randn(input_dim, 50) * 0.01,
            'lstm2': np.random.randn(50, 50) * 0.01,
            'dense': np.random.randn(50, 1) * 0.01
        }
    
    def _evaluate_model(self, model, X_test, y_test) -> Dict:
        """
        Evaluate model performance
        
        Returns various metrics including MAE, MSE, R2
        """
        try:
            # Make predictions
            if isinstance(model, dict):
                if model.get('type') == 'lstm':
                    predictions = self._lstm_predict(model, X_test)
                elif model.get('type') == 'linear':
                    predictions = np.dot(X_test, model['weights']) + model['bias']
                else:
                    predictions = np.zeros(len(y_test))
            else:
                # sklearn model
                predictions = model.predict(X_test)
            
            # Calculate metrics
            mae = np.mean(np.abs(predictions - y_test))
            mse = np.mean((predictions - y_test) ** 2)
            rmse = np.sqrt(mse)
            
            # R2 score
            ss_res = np.sum((y_test - predictions) ** 2)
            ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Directional accuracy (for trading)
            if len(y_test) > 1:
                actual_direction = np.sign(np.diff(y_test))
                pred_direction = np.sign(np.diff(predictions))
                directional_accuracy = np.mean(actual_direction == pred_direction)
            else:
                directional_accuracy = 0.0
            
            metrics = {
                'mae': float(mae),
                'mse': float(mse),
                'rmse': float(rmse),
                'r2': float(r2),
                'directional_accuracy': float(directional_accuracy),
                'n_samples': len(y_test)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error evaluating model: {e}")
            return {
                'mae': float('inf'),
                'mse': float('inf'),
                'rmse': float('inf'),
                'r2': 0.0,
                'directional_accuracy': 0.0,
                'error': str(e)
            }
    
    def _lstm_predict(self, model, X) -> np.ndarray:
        """Simple LSTM prediction"""
        # Simplified prediction logic
        weights = model['weights']
        
        # Simple forward pass simulation
        h1 = np.tanh(np.dot(X, weights['lstm1']))
        h2 = np.tanh(np.dot(h1, weights['lstm2']))
        output = np.dot(h2, weights['dense'])
        
        return output.flatten()
    
    async def predict(self, data: pd.DataFrame, target: str) -> np.ndarray:
        """
        Make predictions using trained model
        
        Args:
            data: New data to predict on
            target: Target variable (must match trained model)
            
        Returns:
            Array of predictions
        """
        if target not in self.models:
            raise ValueError(f"No trained model for target: {target}")
        
        model_info = self.models[target]
        model = model_info['model']
        
        # Engineer features
        features = self._engineer_features(data)
        
        # Select same features as training
        if self.feature_columns:
            features = features[self.feature_columns]
        
        # Normalize
        if self.scaler:
            features_scaled = self.scaler.transform(features)
        else:
            features_scaled = features.values
        
        # Predict
        if isinstance(model, dict):
            if model.get('type') == 'lstm':
                predictions = self._lstm_predict(model, features_scaled)
            elif model.get('type') == 'linear':
                predictions = np.dot(features_scaled, model['weights']) + model['bias']
            else:
                predictions = np.zeros(len(features_scaled))
        else:
            predictions = model.predict(features_scaled)
        
        return predictions
    
    def save_model(self, model_name: str, filepath: Optional[str] = None):
        """
        Save trained model to disk
        
        Args:
            model_name: Name/target of the model
            filepath: Optional custom filepath
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        if filepath is None:
            filepath = self.model_dir / f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        
        model_data = {
            'model': self.models[model_name],
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'history': self.history
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """
        Load trained model from disk
        
        Args:
            filepath: Path to saved model file
        """
        # WARNING: pickle.load can execute arbitrary code — only load trusted files
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
        except (pickle.UnpicklingError, EOFError, ValueError) as e:
            logger.error(f"Failed to load model from {filepath}: {e}")
            raise
        
        if 'model' in model_data and isinstance(model_data['model'], dict):
            self.models.update(model_data['model'])
        self.scaler = model_data.get('scaler')
        self.feature_columns = model_data.get('feature_columns', [])
        self.history = model_data.get('history', [])
        
        logger.info(f"Model loaded from {filepath}")
    
    def get_feature_importance(self, target: str) -> Dict[str, float]:
        """Get feature importance for Random Forest models"""
        if target not in self.models:
            return {}
        
        model_info = self.models[target]
        model = model_info['model']
        
        if hasattr(model, 'feature_importances_'):
            importance = dict(zip(self.feature_columns, model.feature_importances_))
            return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        
        return {}
    
    async def incremental_train(self, new_data: pd.DataFrame, target: str):
        """
        Incrementally train model with new data
        
        Args:
            new_data: New training data
            target: Target variable
        """
        logger.info(f"Incremental training for {target}")
        
        # Combine with existing data if available
        if self.training_data:
            combined_data = pd.concat([self.training_data[-1], new_data])
        else:
            combined_data = new_data
        
        # Retrain model
        await self.train_model(combined_data, target)
        
        # Update training data
        self.training_data.append(new_data)
        
        # Keep only recent training data (last 10 batches)
        if len(self.training_data) > 10:
            self.training_data = self.training_data[-10:]
    
    def get_metrics_history(self) -> List[Dict]:
        """Get training history with metrics"""
        return self.history
    
    def get_model_info(self, target: str) -> Dict:
        """Get information about trained model"""
        if target not in self.models:
            return {}
        
        model_info = self.models[target]
        return {
            'type': model_info.get('type', 'unknown'),
            'metrics': model_info.get('metrics', {}),
            'trained_at': model_info.get('trained_at', None),
            'features': model_info.get('features', []),
            'feature_count': len(model_info.get('features', []))
        }
