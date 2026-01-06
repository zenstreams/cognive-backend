"""
LLM Call Tasks for Cognive Control Plane.

These tasks handle asynchronous processing of LLM call events
for cost tracking and analytics.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.celery_app import app

logger = logging.getLogger(__name__)


# LLM Pricing (per 1K tokens) - can be cached from database
LLM_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
}


@app.task(
    bind=True,
    name="app.tasks.llm_tasks.process_llm_call",
    queue="agent.llm.calls",
    max_retries=3,
    default_retry_delay=30,
)
def process_llm_call(
    self,
    run_id: str,
    call_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Process an LLM call event and calculate costs.
    
    Args:
        run_id: The run identifier.
        call_id: Unique call identifier.
        model: LLM model name.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        latency_ms: Call latency in milliseconds.
        metadata: Optional call metadata.
    
    Returns:
        Processing result with calculated cost.
    """
    logger.info(f"Processing LLM call: call_id={call_id}, model={model}")
    
    try:
        # Calculate cost
        cost = _calculate_cost(model, input_tokens, output_tokens)
        
        # Create cost record (placeholder - integrate with database)
        cost_record = {
            "run_id": run_id,
            "call_id": call_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": float(cost),
            "latency_ms": latency_ms,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # TODO: Save to database
        # await save_llm_call_record(cost_record)
        
        # TODO: Update run aggregates
        # await update_run_cost_aggregates(run_id, cost)
        
        return {
            "status": "processed",
            "call_id": call_id,
            "cost_usd": float(cost),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as exc:
        logger.error(f"Failed to process LLM call: {exc}")
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@app.task(
    bind=True,
    name="app.tasks.llm_tasks.calculate_run_costs",
    queue="agent.llm.calls",
    max_retries=2,
)
def calculate_run_costs(
    self,
    run_id: str,
    organization_id: str,
) -> dict[str, Any]:
    """
    Calculate total costs for a completed run.
    
    Args:
        run_id: The run identifier.
        organization_id: The organization identifier.
    
    Returns:
        Cost summary for the run.
    """
    logger.info(f"Calculating run costs: run_id={run_id}")
    
    try:
        # TODO: Query all LLM calls for this run from database
        # llm_calls = await get_llm_calls_for_run(run_id)
        
        # Placeholder calculation
        cost_summary = {
            "run_id": run_id,
            "organization_id": organization_id,
            "total_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "by_model": {},
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # TODO: Save summary and check budget thresholds
        # await save_run_cost_summary(cost_summary)
        # await check_budget_thresholds(organization_id, cost_summary["total_cost_usd"])
        
        return cost_summary
        
    except Exception as exc:
        logger.error(f"Failed to calculate run costs: {exc}")
        raise self.retry(exc=exc, countdown=60)


# =============================================================================
# Internal Helpers
# =============================================================================

def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """
    Calculate the cost of an LLM call.
    
    Args:
        model: The model name.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
    
    Returns:
        Total cost in USD as Decimal.
    """
    # Normalize model name (handle variants like gpt-4-0613)
    base_model = _normalize_model_name(model)
    
    pricing = LLM_PRICING.get(base_model)
    if not pricing:
        logger.warning(f"Unknown model pricing: {model}, using default")
        pricing = {"input": 0.01, "output": 0.03}  # Conservative default
    
    input_cost = Decimal(str(pricing["input"])) * Decimal(input_tokens) / 1000
    output_cost = Decimal(str(pricing["output"])) * Decimal(output_tokens) / 1000
    
    return input_cost + output_cost


def _normalize_model_name(model: str) -> str:
    """Normalize model name to match pricing keys."""
    model_lower = model.lower()
    
    # GPT-4 variants
    if "gpt-4o-mini" in model_lower:
        return "gpt-4o-mini"
    if "gpt-4o" in model_lower:
        return "gpt-4o"
    if "gpt-4-turbo" in model_lower or "gpt-4-1106" in model_lower:
        return "gpt-4-turbo"
    if "gpt-4" in model_lower:
        return "gpt-4"
    if "gpt-3.5" in model_lower:
        return "gpt-3.5-turbo"
    
    # Claude variants
    if "claude-3-opus" in model_lower:
        return "claude-3-opus"
    if "claude-3.5-sonnet" in model_lower or "claude-3-5-sonnet" in model_lower:
        return "claude-3.5-sonnet"
    if "claude-3-sonnet" in model_lower:
        return "claude-3-sonnet"
    if "claude-3-haiku" in model_lower:
        return "claude-3-haiku"
    
    return model_lower

