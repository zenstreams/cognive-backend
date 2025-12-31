"""Implement database indexing strategy for query optimization.

Revision ID: 003_database_indexing_strategy
Revises: 002_fix_llm_calls_pk
Create Date: 2025-12-29

This migration implements the indexing strategy from SCRUM-57:
- Composite indexes for common multi-column query patterns
- Partial indexes for specific conditions (e.g., failed runs)
- Indexes optimized for dashboard, analytics, and core API queries
- pg_stat_statements extension for slow query monitoring
"""

from __future__ import annotations

from alembic import op


revision = "003_database_indexing_strategy"
down_revision = "002_fix_llm_calls_pk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # Enable pg_stat_statements for slow query monitoring
    # ==========================================================================
    # Note: pg_stat_statements requires shared_preload_libraries configuration
    # in postgresql.conf. The extension creation may fail if not pre-configured.
    # In Docker/TimescaleDB, this is often pre-configured.
    op.execute(
        """
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'pg_stat_statements extension not available. Configure shared_preload_libraries in postgresql.conf.';
        END
        $$;
        """
    )

    # ==========================================================================
    # Composite Indexes for agent_runs table
    # ==========================================================================
    # For queries filtering by agent and status (e.g., "show failed runs for agent X")
    op.create_index(
        "idx_agent_runs_agent_status",
        "agent_runs",
        ["agent_id", "status"],
        unique=False,
    )

    # For timeline queries (e.g., "show runs for agent X ordered by start time")
    op.create_index(
        "idx_agent_runs_agent_started_at",
        "agent_runs",
        ["agent_id", "started_at"],
        unique=False,
    )

    # ==========================================================================
    # Partial Index for failed runs (optimized lookup for error analysis)
    # ==========================================================================
    op.execute(
        """
        CREATE INDEX idx_agent_runs_failed
        ON agent_runs(agent_id, created_at DESC)
        WHERE status = 'failed';
        """
    )

    # ==========================================================================
    # Composite Indexes for llm_calls table
    # ==========================================================================
    # For queries by agent with time ordering (e.g., "recent calls for agent X")
    op.execute(
        """
        CREATE INDEX idx_llm_calls_agent_timestamp
        ON llm_calls(agent_id, timestamp DESC);
        """
    )

    # For call tracking within a run
    op.create_index(
        "idx_llm_calls_run_timestamp",
        "llm_calls",
        ["run_id", "timestamp"],
        unique=False,
    )

    # For cost analysis queries by provider and model
    op.create_index(
        "idx_llm_calls_provider_model",
        "llm_calls",
        ["provider", "model"],
        unique=False,
    )

    # ==========================================================================
    # Composite Indexes for tool_invocations table
    # ==========================================================================
    # For queries by agent with time ordering
    op.create_index(
        "idx_tool_invocations_agent_timestamp",
        "tool_invocations",
        ["agent_id", "timestamp"],
        unique=False,
    )

    # For tracking tool calls within a run
    op.create_index(
        "idx_tool_invocations_run_timestamp",
        "tool_invocations",
        ["run_id", "timestamp"],
        unique=False,
    )

    # For tool success/failure analysis
    op.create_index(
        "idx_tool_invocations_tool_success",
        "tool_invocations",
        ["tool_name", "success"],
        unique=False,
    )

    # ==========================================================================
    # Composite Indexes for audit_logs table
    # ==========================================================================
    # For audit queries by user (e.g., "show actions by user X")
    op.create_index(
        "idx_audit_logs_user_timestamp",
        "audit_logs",
        ["actor_user_id", "timestamp"],
        unique=False,
    )

    # For filtering by action type
    op.create_index(
        "idx_audit_logs_action_timestamp",
        "audit_logs",
        ["action", "timestamp"],
        unique=False,
    )

    # For resource-specific audit trails
    op.create_index(
        "idx_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
        unique=False,
    )

    # ==========================================================================
    # Composite Indexes for budget_limits table
    # ==========================================================================
    # For budget checks (looking up limits by agent or team)
    op.create_index(
        "idx_budget_limits_agent_team",
        "budget_limits",
        ["agent_id", "team_id"],
        unique=False,
    )

    # ==========================================================================
    # Composite Indexes for usage_aggregations table
    # ==========================================================================
    # For agent usage reports over time
    op.create_index(
        "idx_usage_aggregations_agent_day",
        "usage_aggregations",
        ["agent_id", "day"],
        unique=False,
    )

    # For team usage reports over time
    op.create_index(
        "idx_usage_aggregations_team_day",
        "usage_aggregations",
        ["team_id", "day"],
        unique=False,
    )

    # ==========================================================================
    # Composite Indexes for llm_pricing table
    # ==========================================================================
    # For pricing lookups (provider + model combination)
    op.create_index(
        "idx_llm_pricing_provider_model",
        "llm_pricing",
        ["provider", "model"],
        unique=False,
    )

    # ==========================================================================
    # Composite Indexes for execution_steps table
    # ==========================================================================
    # For step type analysis within runs
    op.create_index(
        "idx_execution_steps_run_step_type",
        "execution_steps",
        ["run_id", "step_type"],
        unique=False,
    )

    # For ordered step retrieval
    op.create_index(
        "idx_execution_steps_run_step_index",
        "execution_steps",
        ["run_id", "step_index"],
        unique=False,
    )

    # ==========================================================================
    # Composite Index for user_roles table
    # ==========================================================================
    # For checking user-role assignments efficiently
    op.create_index(
        "idx_user_roles_user_role",
        "user_roles",
        ["user_id", "role_id"],
        unique=True,  # Prevent duplicate assignments
    )


def downgrade() -> None:
    # user_roles
    op.drop_index("idx_user_roles_user_role", table_name="user_roles")

    # execution_steps
    op.drop_index("idx_execution_steps_run_step_index", table_name="execution_steps")
    op.drop_index("idx_execution_steps_run_step_type", table_name="execution_steps")

    # llm_pricing
    op.drop_index("idx_llm_pricing_provider_model", table_name="llm_pricing")

    # usage_aggregations
    op.drop_index("idx_usage_aggregations_team_day", table_name="usage_aggregations")
    op.drop_index("idx_usage_aggregations_agent_day", table_name="usage_aggregations")

    # budget_limits
    op.drop_index("idx_budget_limits_agent_team", table_name="budget_limits")

    # audit_logs
    op.drop_index("idx_audit_logs_resource", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_timestamp", table_name="audit_logs")

    # tool_invocations
    op.drop_index("idx_tool_invocations_tool_success", table_name="tool_invocations")
    op.drop_index("idx_tool_invocations_run_timestamp", table_name="tool_invocations")
    op.drop_index("idx_tool_invocations_agent_timestamp", table_name="tool_invocations")

    # llm_calls
    op.drop_index("idx_llm_calls_provider_model", table_name="llm_calls")
    op.drop_index("idx_llm_calls_run_timestamp", table_name="llm_calls")
    op.drop_index("idx_llm_calls_agent_timestamp", table_name="llm_calls")

    # agent_runs
    op.drop_index("idx_agent_runs_failed", table_name="agent_runs")
    op.drop_index("idx_agent_runs_agent_started_at", table_name="agent_runs")
    op.drop_index("idx_agent_runs_agent_status", table_name="agent_runs")

    # Drop pg_stat_statements extension
    op.execute("DROP EXTENSION IF EXISTS pg_stat_statements;")


