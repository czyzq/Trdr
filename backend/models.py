"""
Pydantic models for CFD trading signals
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class SignalDirection(str, Enum):
    """Trading signal direction"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

class ComponentType(str, Enum):
    """Types of analysis components"""
    TECHNICAL = "technical"
    PRICE_ACTION = "price_action"
    NEWS = "news"

class Component(BaseModel):
    """Individual analysis component"""
    type: ComponentType
    name: str
    value: float  # -1 to +1 scale
    description: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    indicators: Optional[Dict[str, Any]] = None

class Signal(BaseModel):
    """CFD Trading Signal"""
    symbol: str
    direction: SignalDirection
    score: float = Field(-1.0, ge=-1.0, le=1.0)  # -1 to +1
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    # Components breakdown
    technical_score: float = Field(0.0, ge=-1.0, le=1.0)
    price_action_score: float = Field(0.0, ge=-1.0, le=1.0)
    news_score: float = Field(0.0, ge=-1.0, le=1.0)
    
    components: List[Component] = []
    
    # Price info
    current_price: float
    time_horizon: str  # e.g., "1h", "4h", "1d"
    
    # Recommendations
    entry_point: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    
    risk_reward_ratio: Optional[float] = None
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Trade(BaseModel):
    """Executed trade record"""
    signal_id: str
    symbol: str
    direction: SignalDirection
    entry_price: float
    entry_time: datetime
    
    take_profit: float
    stop_loss: float
    
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    
    status: str  # "open", "closed", "cancelled"
    pnl: Optional[float] = None  # Profit/Loss
    pnl_percent: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class HistoricalSignal(BaseModel):
    """Historical signal record for backtesting/analysis"""
    id: str
    symbol: str
    direction: SignalDirection
    score: float
    confidence: float
    
    entry_price: float
    entry_time: datetime
    
    # If we have exit data
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    
    result: Optional[str] = None  # "win", "loss", "pending"
    pnl_percent: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SignalRequest(BaseModel):
    """Request to generate signals for specific symbols"""
    symbols: List[str] = ["GC=F", "SI=F", "NQ=F"]
    time_horizon: str = "1h"  # 1h, 4h, 1d
    include_news: bool = True

class SignalResponse(BaseModel):
    """Response with trading signals"""
    signals: List[Signal]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class HistoryRequest(BaseModel):
    """Request for historical signals/trades"""
    symbol: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100

class HistoryResponse(BaseModel):
    """Response with historical data"""
    symbol: str
    signals: List[HistoricalSignal]
    win_rate: Optional[float] = None
    total_signals: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
