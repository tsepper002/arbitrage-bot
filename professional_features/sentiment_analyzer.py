"""
Sentiment Analyzer for Crypto Markets
Analyzes social media sentiment, news, and Fear & Greed index
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes market sentiment from multiple sources"""
    
    def __init__(self):
        self.sentiment_history = []
        self.keywords = {
            'bullish': ['moon', 'bullish', 'buy', 'pump', 'rally', 'green', 'up'],
            'bearish': ['dump', 'crash', 'bear', 'sell', 'down', 'red', 'drop']
        }
        self.fear_greed_history = []
        
    async def analyze_social_sentiment(self, symbol: str, timeframe: str = '1h') -> Dict:
        """
        Analyze social media sentiment for a symbol
        
        Args:
            symbol: Trading symbol
            timeframe: Time window for analysis
            
        Returns:
            Sentiment analysis results
        """
        try:
            # Simulated social media analysis
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            
            # In production, would scrape Twitter, Reddit, etc.
            # For now, using mock data
            sample_posts = self._get_sample_posts(symbol)
            
            for post in sample_posts:
                sentiment = self._classify_sentiment(post)
                if sentiment > 0.3:
                    bullish_count += 1
                elif sentiment < -0.3:
                    bearish_count += 1
                else:
                    neutral_count += 1
            
            total = bullish_count + bearish_count + neutral_count
            if total == 0:
                return self._create_neutral_sentiment()
            
            sentiment_score = (bullish_count - bearish_count) / total
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': datetime.now().isoformat(),
                'sentiment_score': sentiment_score,
                'bullish_percentage': (bullish_count / total) * 100,
                'bearish_percentage': (bearish_count / total) * 100,
                'neutral_percentage': (neutral_count / total) * 100,
                'total_posts': total,
                'signal': self._generate_sentiment_signal(sentiment_score)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return self._create_neutral_sentiment()
    
    def _get_sample_posts(self, symbol: str) -> List[str]:
        """Get sample social media posts (mock data)"""
        # In production, would fetch real social media data
        return [
            f"{symbol} looking bullish today",
            f"Bearish on {symbol} short term",
            f"{symbol} consolidating",
            f"Moon mission for {symbol}",
            f"{symbol} might dump soon"
        ]
    
    def _classify_sentiment(self, text: str) -> float:
        """
        Classify text sentiment
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score (-1 to 1)
        """
        text_lower = text.lower()
        
        bullish_score = sum(1 for word in self.keywords['bullish'] if word in text_lower)
        bearish_score = sum(1 for word in self.keywords['bearish'] if word in text_lower)
        
        if bullish_score + bearish_score == 0:
            return 0.0
        
        return (bullish_score - bearish_score) / (bullish_score + bearish_score)
    
    def _generate_sentiment_signal(self, score: float) -> str:
        """Generate trading signal from sentiment score"""
        if score > 0.5:
            return 'STRONG_BUY'
        elif score > 0.2:
            return 'BUY'
        elif score < -0.5:
            return 'STRONG_SELL'
        elif score < -0.2:
            return 'SELL'
        else:
            return 'NEUTRAL'
    
    def _create_neutral_sentiment(self) -> Dict:
        """Create neutral sentiment response"""
        return {
            'sentiment_score': 0.0,
            'signal': 'NEUTRAL',
            'timestamp': datetime.now().isoformat()
        }
    
    async def calculate_fear_greed_index(self) -> Dict:
        """
        Calculate crypto Fear & Greed index
        
        Returns:
            Fear & Greed index data
        """
        try:
            # Components: volatility, market momentum, social media, surveys, dominance
            volatility_score = self._calculate_volatility_score()
            momentum_score = self._calculate_momentum_score()
            social_score = self._calculate_social_score()
            dominance_score = self._calculate_dominance_score()
            
            # Weighted average
            weights = {
                'volatility': 0.25,
                'momentum': 0.25,
                'social': 0.25,
                'dominance': 0.25
            }
            
            total_score = (
                volatility_score * weights['volatility'] +
                momentum_score * weights['momentum'] +
                social_score * weights['social'] +
                dominance_score * weights['dominance']
            )
            
            classification = self._classify_fear_greed(total_score)
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'index_value': total_score,
                'classification': classification,
                'components': {
                    'volatility': volatility_score,
                    'momentum': momentum_score,
                    'social': social_score,
                    'dominance': dominance_score
                }
            }
            
            self.fear_greed_history.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Error calculating Fear & Greed index: {e}")
            return {'index_value': 50, 'classification': 'NEUTRAL'}
    
    def _calculate_volatility_score(self) -> float:
        """Calculate volatility component (mock)"""
        # In production, would calculate from actual market data
        return 60.0
    
    def _calculate_momentum_score(self) -> float:
        """Calculate momentum component (mock)"""
        return 55.0
    
    def _calculate_social_score(self) -> float:
        """Calculate social media component (mock)"""
        return 50.0
    
    def _calculate_dominance_score(self) -> float:
        """Calculate BTC dominance component (mock)"""
        return 45.0
    
    def _classify_fear_greed(self, score: float) -> str:
        """Classify Fear & Greed index score"""
        if score >= 75:
            return 'EXTREME_GREED'
        elif score >= 55:
            return 'GREED'
        elif score >= 45:
            return 'NEUTRAL'
        elif score >= 25:
            return 'FEAR'
        else:
            return 'EXTREME_FEAR'
    
    def get_sentiment_stats(self) -> Dict:
        """Get sentiment statistics"""
        return {
            'history_length': len(self.sentiment_history),
            'fear_greed_history': len(self.fear_greed_history),
            'last_update': datetime.now().isoformat()
        }
