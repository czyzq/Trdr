"""
OpenClaw Integration for CFD Trading Bot iMessage Alerts
Handles actual message sending through OpenClaw's message tool
"""

import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Global reference to OpenClaw's message function
_openclaw_message_func = None


def set_openclaw_message_function(message_func):
    """Set the OpenClaw message function for sending iMessages"""
    global _openclaw_message_func
    _openclaw_message_func = message_func
    logger.info("OpenClaw message function set for CFD alerts")


def send_imessage_via_openclaw(recipient: str, message: str) -> Dict:
    """
    Send iMessage using OpenClaw's message tool
    This function will be called from the main.py context where message tool is available
    """
    global _openclaw_message_func

    if _openclaw_message_func is None:
        logger.error("OpenClaw message function not set - cannot send iMessage")
        return {"status": "error", "error": "OpenClaw message function not initialized"}

    try:
        # Call the OpenClaw message function
        result = _openclaw_message_func(
            action="send", channel="imessage", target=recipient, message=message, asVoice=False
        )

        logger.info(f"iMessage sent via OpenClaw to {recipient}")
        return {"status": "sent", "message_id": f"cfd_{datetime.utcnow().timestamp()}", "result": result}

    except Exception as e:
        logger.error(f"Failed to send iMessage via OpenClaw: {e}")
        return {"status": "error", "error": str(e)}


def format_imessage_for_cfd_alert(
    symbol: str,
    direction: str,
    score: float,
    confidence: float,
    current_price: float,
    entry_point: float,
    take_profit: float,
    stop_loss: float,
) -> str:
    """Format a CFD trading signal as an iMessage"""

    # Convert direction to action
    action = "BUY" if direction.lower() in ["buy", "long", "strong_buy"] else "SELL"

    # Create emoji indicator
    emoji = "🟢" if action == "BUY" else "🔴"

    # Calculate risk/reward ratio
    risk = abs(entry_point - stop_loss)
    reward = abs(take_profit - entry_point)
    rr_ratio = reward / risk if risk > 0 else 0

    # Format the message
    message = f"""{emoji} CFD TRADING SIGNAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Symbol: {symbol}
📊 Action: {action}
🎯 Score: {score:.3f}/1.0
💯 Confidence: {confidence:.0%}

💰 Current Price: ${current_price:,.2f}
📍 Entry Point: ${entry_point:,.2f}
🎯 Take Profit: ${take_profit:,.2f}
🛑 Stop Loss: ${stop_loss:,.2f}

⚖️ Risk/Reward: {rr_ratio:.1f}:1
⏰ Time: {datetime.utcnow().strftime("%H:%M UTC")}

💡 This is an automated trading signal. Always do your own research."""

    return message
