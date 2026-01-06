"""
Budget Monitoring Tasks for Cognive Control Plane.

These tasks handle budget threshold monitoring and alert notifications.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.celery_app import app

logger = logging.getLogger(__name__)


# Budget alert thresholds (percentage of limit)
ALERT_THRESHOLDS = {
    "warning": 0.75,    # 75% of budget
    "critical": 0.90,   # 90% of budget
    "exceeded": 1.0,    # 100% of budget
}


@app.task(
    bind=True,
    name="app.tasks.budget_tasks.check_budget_threshold",
    queue="budget.alerts",
    max_retries=3,
    default_retry_delay=60,
)
def check_budget_threshold(
    self,
    organization_id: str,
    current_spend: float,
    budget_limit: float,
    agent_id: str | None = None,
    period: str = "monthly",
) -> dict[str, Any]:
    """
    Check if spending has crossed any budget thresholds.
    
    Args:
        organization_id: The organization identifier.
        current_spend: Current spending amount in USD.
        budget_limit: Budget limit in USD.
        agent_id: Optional agent ID for agent-specific budgets.
        period: Budget period (daily, weekly, monthly).
    
    Returns:
        Threshold check result.
    """
    logger.info(
        f"Checking budget threshold: org={organization_id}, "
        f"spend=${current_spend:.2f}, limit=${budget_limit:.2f}"
    )
    
    try:
        if budget_limit <= 0:
            return {"status": "skipped", "reason": "no_budget_limit"}
        
        usage_ratio = current_spend / budget_limit
        alert_type = None
        
        # Check thresholds in order of severity
        if usage_ratio >= ALERT_THRESHOLDS["exceeded"]:
            alert_type = "exceeded"
        elif usage_ratio >= ALERT_THRESHOLDS["critical"]:
            alert_type = "critical"
        elif usage_ratio >= ALERT_THRESHOLDS["warning"]:
            alert_type = "warning"
        
        result = {
            "organization_id": organization_id,
            "agent_id": agent_id,
            "current_spend": current_spend,
            "budget_limit": budget_limit,
            "usage_ratio": usage_ratio,
            "usage_percent": round(usage_ratio * 100, 2),
            "period": period,
            "alert_triggered": alert_type is not None,
            "alert_type": alert_type,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Trigger alert if threshold crossed
        if alert_type:
            send_budget_alert.delay(
                organization_id=organization_id,
                agent_id=agent_id,
                alert_type=alert_type,
                current_spend=current_spend,
                budget_limit=budget_limit,
                usage_percent=result["usage_percent"],
                period=period,
            )
        
        return result
        
    except Exception as exc:
        logger.error(f"Failed to check budget threshold: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(
    bind=True,
    name="app.tasks.budget_tasks.send_budget_alert",
    queue="budget.alerts",
    max_retries=5,
    default_retry_delay=120,
)
def send_budget_alert(
    self,
    organization_id: str,
    alert_type: str,
    current_spend: float,
    budget_limit: float,
    usage_percent: float,
    period: str,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """
    Send a budget alert notification.
    
    Args:
        organization_id: The organization identifier.
        alert_type: Type of alert (warning, critical, exceeded).
        current_spend: Current spending amount.
        budget_limit: Budget limit amount.
        usage_percent: Usage percentage.
        period: Budget period.
        agent_id: Optional agent ID.
    
    Returns:
        Alert sending result.
    """
    scope = f"agent {agent_id}" if agent_id else "organization"
    
    logger.warning(
        f"BUDGET ALERT [{alert_type.upper()}]: {scope} {organization_id} "
        f"has used {usage_percent}% of {period} budget "
        f"(${current_spend:.2f} / ${budget_limit:.2f})"
    )
    
    try:
        # Build alert message
        message = _build_alert_message(
            alert_type=alert_type,
            organization_id=organization_id,
            agent_id=agent_id,
            current_spend=current_spend,
            budget_limit=budget_limit,
            usage_percent=usage_percent,
            period=period,
        )
        
        # TODO: Send notifications via configured channels
        # - Email notifications
        # - Slack/Teams webhooks
        # - In-app notifications
        # - PagerDuty for critical/exceeded
        
        # Placeholder: Log the alert
        # await send_email_notification(organization_id, message)
        # await send_slack_notification(organization_id, message)
        
        # Record alert in database
        alert_record = {
            "organization_id": organization_id,
            "agent_id": agent_id,
            "alert_type": alert_type,
            "message": message,
            "current_spend": current_spend,
            "budget_limit": budget_limit,
            "usage_percent": usage_percent,
            "period": period,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # TODO: Save to database
        # await save_alert_record(alert_record)
        
        return {
            "status": "sent",
            "alert_type": alert_type,
            "organization_id": organization_id,
            "agent_id": agent_id,
            "message": message,
            "sent_at": alert_record["sent_at"],
        }
        
    except Exception as exc:
        logger.error(f"Failed to send budget alert: {exc}")
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))


@app.task(
    name="app.tasks.budget_tasks.check_all_budgets",
    queue="budget.alerts",
)
def check_all_budgets() -> dict[str, Any]:
    """
    Periodic task to check all organization budgets.
    
    This task should be scheduled to run periodically (e.g., every hour)
    via Celery Beat.
    
    Returns:
        Summary of budget checks performed.
    """
    logger.info("Starting periodic budget check for all organizations")
    
    # TODO: Query all organizations with budget limits
    # organizations = await get_organizations_with_budgets()
    
    checks_performed = 0
    alerts_triggered = 0
    
    # Placeholder: In production, iterate through organizations
    # for org in organizations:
    #     result = check_budget_threshold.delay(
    #         organization_id=org.id,
    #         current_spend=org.current_month_spend,
    #         budget_limit=org.monthly_budget_limit,
    #     )
    #     checks_performed += 1
    
    return {
        "status": "completed",
        "checks_performed": checks_performed,
        "alerts_triggered": alerts_triggered,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Internal Helpers
# =============================================================================

def _build_alert_message(
    alert_type: str,
    organization_id: str,
    agent_id: str | None,
    current_spend: float,
    budget_limit: float,
    usage_percent: float,
    period: str,
) -> str:
    """Build a human-readable alert message."""
    scope = f"Agent {agent_id}" if agent_id else "Your organization"
    
    if alert_type == "exceeded":
        severity = "🚨 BUDGET EXCEEDED"
        action = "All agent operations have been paused. Please increase your budget limit or wait for the next billing period."
    elif alert_type == "critical":
        severity = "⚠️ CRITICAL BUDGET WARNING"
        action = "Consider increasing your budget limit to avoid service interruption."
    else:
        severity = "📊 Budget Warning"
        action = "Monitor your usage to stay within budget."
    
    return (
        f"{severity}\n\n"
        f"{scope} has used {usage_percent}% of the {period} budget.\n\n"
        f"Current Spend: ${current_spend:,.2f}\n"
        f"Budget Limit: ${budget_limit:,.2f}\n"
        f"Remaining: ${max(0, budget_limit - current_spend):,.2f}\n\n"
        f"{action}"
    )

