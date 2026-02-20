"""
iMessage Alert System for CFD Trading Bot
Sends trading signal alerts via iMessage through OpenClaw
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from openclaw_integration import send_imessage_via_openclaw
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AlertConfig(BaseModel):
    """Alert configuration for CFD trading bot"""

    enabled: bool = False
    recipient_phone: str = "+48793203605"  # Default recipient
    min_score_threshold: float = 0.3  # Only alert on significant buy signals
    max_score_threshold: float = -0.3  # Only alert on significant sell signals
    notify_on_reversal: bool = True
    notify_on_major_moves: bool = True
    major_move_threshold_pct: float = 5.0
    alert_history_limit: int = 50


class iMessageAlertDispatcher:
    """Dispatch CFD trading alerts via iMessage"""

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self.alert_history: List[Dict] = []

    def update_config(self, new_config: AlertConfig):
        """Update alert configuration"""
        self.config = new_config
        logger.info(f"CFD Alert config updated: enabled={self.config.enabled}")

    def format_signal_alert(
        self,
        symbol: str,
        direction: str,
        score: float,
        confidence: float,
        current_price: float,
        entry_point: float,
        take_profit: float,
        stop_loss: float,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Format CFD signal alert message for iMessage"""
        if timestamp is None:
            timestamp = datetime.utcnow()

        time_str = timestamp.strftime("%H:%M UTC")

        # Convert direction to action
        action = "BUY" if direction.lower() in ["buy", "long"] else "SELL"

        # Create emoji indicator
        emoji = "🟢" if action == "BUY" else "🔴"

        # Format risk/reward ratio
        risk = abs(entry_point - stop_loss)
        reward = abs(take_profit - entry_point)
        rr_ratio = reward / risk if risk > 0 else 0

        message = f"""{emoji} CFD SIGNAL: {symbol} | {action}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Score: {score:.2f}/1.0 | Confidence: {confidence:.0%}
💰 Current: ${current_price:,.2f}
📍 Entry: ${entry_point:,.2f}
🎯 Take Profit: ${take_profit:,.2f}
🛑 Stop Loss: ${stop_loss:,.2f}
⚖️ Risk/Reward: {rr_ratio:.1f}:1
⏰ Time: {time_str}"""

        return message

    def should_send_alert(self, symbol: str, direction: str, score: float, confidence: float) -> bool:
        """Determine if alert should be sent based on configuration"""
        if not self.config.enabled:
            return False

        # Check score thresholds
        if direction.lower() in ["buy", "long"] and score < self.config.min_score_threshold:
            return False
        if direction.lower() in ["sell", "short"] and score > self.config.max_score_threshold:
            return False

        # Check confidence minimum
        if confidence < 0.3:  # Minimum 30% confidence
            return False

        return True

    def send_alert(
        self,
        symbol: str,
        direction: str,
        score: float,
        confidence: float,
        current_price: float,
        entry_point: float,
        take_profit: float,
        stop_loss: float,
        timestamp: Optional[datetime] = None,
    ) -> Dict:
        """Send alert via iMessage if conditions are met"""
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Check if we should send this alert
        if not self.should_send_alert(symbol, direction, score, confidence):
            return {"status": "filtered", "reason": "Below thresholds"}

        # Format the message
        message = self.format_signal_alert(
            symbol, direction, score, confidence, current_price, entry_point, take_profit, stop_loss, timestamp
        )

        alert_record = {
            "id": f"{symbol}_{timestamp.timestamp()}",
            "symbol": symbol,
            "direction": direction,
            "score": score,
            "confidence": confidence,
            "timestamp": timestamp.isoformat(),
            "message": message,
            "status": "pending",
            "recipient": self.config.recipient_phone,
            "current_price": current_price,
            "entry_point": entry_point,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
        }

        try:
            # Send via OpenClaw message tool
            result = self._send_via_openclaw(message)
            alert_record["status"] = result.get("status", "sent")
            alert_record["message_id"] = result.get("message_id")
            alert_record["sent_at"] = datetime.utcnow().isoformat()
            logger.info(f"CFD Alert sent via iMessage: {symbol} {direction} (score: {score:.3f})")

        except Exception as e:
            logger.error(f"Failed to send CFD alert: {e}")
            alert_record["status"] = "failed"
            alert_record["error"] = str(e)

        # Store in history
        self.alert_history.append(alert_record)
        if len(self.alert_history) > self.config.alert_history_limit:
            self.alert_history.pop(0)

        return {
            "status": alert_record["status"],
            "message_id": alert_record.get("message_id"),
            "message": message,
            "recipient": self.config.recipient_phone,
            "symbol": symbol,
            "score": score,
            "confidence": confidence,
        }

    def _send_via_openclaw(self, message: str) -> Dict:
        """Send message via OpenClaw's message tool"""
        return send_imessage_via_openclaw(self.config.recipient_phone, message)

    def get_alert_history(self, symbol: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Get CFD alert history"""
        history = self.alert_history

        if symbol:
            history = [a for a in history if a.get("symbol") == symbol]

        return sorted(history, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def clear_history(self):
        """Clear alert history"""
        self.alert_history = []
        logger.info("CFD Alert history cleared")


# Global dispatcher instance
_dispatcher: Optional[iMessageAlertDispatcher] = None


def get_dispatcher() -> iMessageAlertDispatcher:
    """Get or create the global CFD alert dispatcher"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = iMessageAlertDispatcher()
    return _dispatcher


def set_dispatcher_config(config: AlertConfig):
    """Update global dispatcher configuration"""
    dispatcher = get_dispatcher()
    dispatcher.update_config(config)
