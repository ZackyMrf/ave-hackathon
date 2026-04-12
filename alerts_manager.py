#!/usr/bin/env python3
"""
Advanced Monitoring Alert Manager
Handles alert creation, evaluation, and execution for Telegram + Web integration
"""
import json
import os
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import requests

# Alert Types
ALERT_TYPE_PRICE = "price"
ALERT_TYPE_RISK = "risk"
ALERT_TYPE_VOLUME = "volume"
ALERT_TYPE_WHALE = "whale"
ALERT_TYPE_TREND = "trend"

# Alert Conditions
CONDITION_ABOVE = "above"
CONDITION_BELOW = "below"
CONDITION_CHANGE = "change"


@dataclass
class Alert:
    """Alert configuration"""
    id: str
    user_id: int
    token: str
    chain: str
    alert_type: str  # price, risk, volume, whale, trend
    condition: str  # above, below, change
    threshold: float
    enabled: bool
    created_at: str
    last_triggered: Optional[str] = None
    notify_telegram: bool = True
    notify_web: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AlertsManager:
    """Manages alert configuration, evaluation, and execution"""

    def __init__(self, alerts_file: str = "alerts.json", telegram_token: str = ""):
        self.alerts_file = alerts_file
        self.telegram_token = ""
        self.telegram_base_url = ""
        self.alerts: Dict[str, Alert] = {}
        self.monitored_prices: Dict[str, float] = {}  # token-chain -> last_price
        self.monitored_risks: Dict[str, float] = {}   # token-chain -> last_risk_score
        self.lock = threading.Lock()

        self.set_telegram_token(telegram_token)

        self._load_alerts()

    @staticmethod
    def _normalize_token(raw: str) -> str:
        token = str(raw or "").strip()
        if len(token) >= 2 and ((token[0] == '"' and token[-1] == '"') or (token[0] == "'" and token[-1] == "'")):
            token = token[1:-1].strip()
        return token

    def set_telegram_token(self, telegram_token: str):
        """Update Telegram token and derived API base URL."""
        token = self._normalize_token(telegram_token)
        self.telegram_token = token
        self.telegram_base_url = f"https://api.telegram.org/bot{token}" if token else ""

    def _load_alerts(self):
        """Load alerts from persistent storage"""
        loaded_alerts: Dict[str, Alert] = {}
        try:
            if os.path.exists(self.alerts_file):
                with open(self.alerts_file, "r") as f:
                    data = json.load(f)
                    for alert_data in data:
                        alert = Alert(**alert_data)
                        loaded_alerts[alert.id] = alert
        except Exception as e:
            print(f"[AlertsManager] Error loading alerts: {e}")

        # Replace in-memory alerts so deletions/updates from other processes are reflected.
        self.alerts = loaded_alerts

    def reload_alerts(self):
        """Reload alerts from disk to keep multiple processes synchronized."""
        with self.lock:
            self._load_alerts()

    def _save_alerts(self):
        """Persist alerts to storage"""
        try:
            with open(self.alerts_file, "w") as f:
                data = [alert.to_dict() for alert in self.alerts.values()]
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[AlertsManager] Error saving alerts: {e}")

    def create_alert(
        self,
        user_id: int,
        token: str,
        chain: str,
        alert_type: str,
        condition: str,
        threshold: float,
        notify_telegram: bool = True,
        notify_web: bool = True,
    ) -> Alert:
        """Create new alert"""
        alert_id = f"{user_id}_{token}_{chain}_{alert_type}_{int(time.time())}"
        alert = Alert(
            id=alert_id,
            user_id=user_id,
            token=token,
            chain=chain,
            alert_type=alert_type,
            condition=condition,
            threshold=threshold,
            enabled=True,
            created_at=datetime.now().isoformat(),
            notify_telegram=notify_telegram,
            notify_web=notify_web,
        )

        with self.lock:
            self.alerts[alert_id] = alert
            self._save_alerts()

        return alert

    def delete_alert(self, alert_id: str) -> bool:
        """Delete alert by ID"""
        with self.lock:
            if alert_id in self.alerts:
                del self.alerts[alert_id]
                self._save_alerts()
                return True
        return False

    def update_alert_enabled(self, alert_id: str, enabled: bool) -> bool:
        """Toggle alert enabled status"""
        with self.lock:
            if alert_id in self.alerts:
                self.alerts[alert_id].enabled = enabled
                self._save_alerts()
                return True
        return False

    def get_user_alerts(self, user_id: int) -> List[Alert]:
        """Get all alerts for a user"""
        return [a for a in self.alerts.values() if a.user_id == user_id]

    def get_alerts_for_token(self, token: str, chain: str) -> List[Alert]:
        """Get all alerts for a token"""
        return [
            a for a in self.alerts.values()
            if a.token.lower() == token.lower() and a.chain.lower() == chain.lower()
        ]

    def evaluate_price_alert(
        self, token: str, chain: str, current_price: float
    ) -> List[Dict[str, Any]]:
        """
        Evaluate price alerts for a token
        Returns list of triggered alerts
        """
        triggered = []
        key = f"{token}-{chain}"

        for alert in self.alerts.values():
            if (
                not alert.enabled
                or alert.token.lower() != token.lower()
                or alert.chain.lower() != chain.lower()
                or alert.alert_type != ALERT_TYPE_PRICE
            ):
                continue

            should_trigger = False

            if alert.condition == CONDITION_ABOVE and current_price >= alert.threshold:
                should_trigger = True
            elif (
                alert.condition == CONDITION_BELOW and current_price <= alert.threshold
            ):
                should_trigger = True
            elif alert.condition == CONDITION_CHANGE:
                # 'threshold' is percentage change
                last_price = self.monitored_prices.get(key)
                if (
                    last_price
                    and abs((current_price - last_price) / last_price * 100)
                    >= alert.threshold
                ):
                    should_trigger = True

            if should_trigger:
                triggered.append({
                    "alert": alert,
                    "current_value": current_price,
                    "trigger_type": "price",
                })
                alert.last_triggered = datetime.now().isoformat()

        self.monitored_prices[key] = current_price
        if triggered:
            self._save_alerts()

        return triggered

    def evaluate_risk_alert(
        self, token: str, chain: str, risk_score: float
    ) -> List[Dict[str, Any]]:
        """
        Evaluate risk score alerts
        Returns list of triggered alerts
        """
        triggered = []
        key = f"{token}-{chain}"

        for alert in self.alerts.values():
            if (
                not alert.enabled
                or alert.token.lower() != token.lower()
                or alert.chain.lower() != chain.lower()
                or alert.alert_type != ALERT_TYPE_RISK
            ):
                continue

            should_trigger = False

            if alert.condition == CONDITION_ABOVE and risk_score >= alert.threshold:
                should_trigger = True
            elif alert.condition == CONDITION_BELOW and risk_score <= alert.threshold:
                should_trigger = True

            if should_trigger:
                triggered.append({
                    "alert": alert,
                    "current_value": risk_score,
                    "trigger_type": "risk",
                })
                alert.last_triggered = datetime.now().isoformat()

        self.monitored_risks[key] = risk_score
        if triggered:
            self._save_alerts()

        return triggered

    def evaluate_volume_alert(
        self, token: str, chain: str, volume_24h: float, avg_volume: float
    ) -> List[Dict[str, Any]]:
        """
        Evaluate volume spike alerts
        threshold = volume multiplier (e.g., 3.0 = 3x normal)
        """
        triggered = []

        for alert in self.alerts.values():
            if (
                not alert.enabled
                or alert.token.lower() != token.lower()
                or alert.chain.lower() != chain.lower()
                or alert.alert_type != ALERT_TYPE_VOLUME
            ):
                continue

            if alert.condition == CONDITION_ABOVE:
                # Volume spike detected
                multiplier = volume_24h / avg_volume if avg_volume > 0 else 0
                if multiplier >= alert.threshold:
                    triggered.append({
                        "alert": alert,
                        "current_value": multiplier,
                        "trigger_type": "volume",
                        "details": f"{multiplier:.2f}x normal volume",
                    })
                    alert.last_triggered = datetime.now().isoformat()

        if triggered:
            self._save_alerts()

        return triggered

    def send_telegram_alert(self, user_id: int, alert: Alert, details: str) -> bool:
        """Send alert via Telegram"""
        try:
            message = self._format_alert_message(alert, details)
            requests.post(
                f"{self.telegram_base_url}/sendMessage",
                json={"chat_id": user_id, "text": message, "parse_mode": "Markdown"},
                timeout=5,
            )
            return True
        except Exception as e:
            print(f"[AlertsManager] Error sending Telegram alert: {e}")
            return False

    def _format_alert_message(self, alert: Alert, details: str) -> str:
        """Format alert message for Telegram"""
        emoji_map = {
            ALERT_TYPE_PRICE: "💰",
            ALERT_TYPE_RISK: "⚠️",
            ALERT_TYPE_VOLUME: "📊",
            ALERT_TYPE_WHALE: "🐋",
            ALERT_TYPE_TREND: "📈",
        }
        emoji = emoji_map.get(alert.alert_type, "🔔")

        lines = [
            f"{emoji} *ALERT TRIGGERED*",
            f"Token: `{alert.token.upper()}`",
            f"Chain: {alert.chain}",
            f"Type: {alert.alert_type.upper()}",
            f"Condition: {alert.condition} {alert.threshold}",
            f"",
            f"Details: {details}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]

        return "\n".join(lines)


# Global instance (initialized by api_server)
alerts_manager: Optional[AlertsManager] = None


def init_alerts_manager(telegram_token: str = "") -> AlertsManager:
    """Initialize global alerts manager"""
    global alerts_manager
    alerts_manager = AlertsManager(
        alerts_file="alerts.json",
        telegram_token=telegram_token or os.getenv("TELEGRAM_BOT_TOKEN", ""),
    )
    return alerts_manager


def get_alerts_manager() -> Optional[AlertsManager]:
    """Get global alerts manager instance"""
    return alerts_manager
