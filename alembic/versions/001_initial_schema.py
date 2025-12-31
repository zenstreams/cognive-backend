"""Initial schema for Cognive control plane (PostgreSQL + TimescaleDB).

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-12-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TimescaleDB extension (requires Timescale image; see docker-compose.yml)
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    agent_framework = sa.Enum("langchain", "crewai", "autogen", "custom", name="agent_framework")
    run_status = sa.Enum("queued", "running", "succeeded", "failed", "cancelled", name="run_status")
    step_type = sa.Enum("llm", "tool", "system", name="step_type")
    llm_provider = sa.Enum("openai", "anthropic", "google", "azure_openai", "other", name="llm_provider")
    audit_action = sa.Enum(
        "user_login",
        "user_logout",
        "api_key_created",
        "api_key_revoked",
        "config_changed",
        "budget_alert_sent",
        name="audit_action",
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=True)

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("framework", agent_framework, nullable=False),
        sa.Column("team_id", sa.String(length=36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=False)
    op.create_index("ix_agents_team_id", "agents", ["team_id"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), primary_key=True),
    )
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)

    # Convert agent_runs to hypertable before dependent FKs are created.
    op.execute("SELECT create_hypertable('agent_runs', 'created_at', if_not_exists => TRUE);")

    op.create_table(
        "execution_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("run_created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", step_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_execution_steps_run_id", "execution_steps", ["run_id"], unique=False)
    op.create_index("ix_execution_steps_run_created_at", "execution_steps", ["run_created_at"], unique=False)

    # Ensure created_at participates in PK before hypertable conversion.
    op.execute("UPDATE execution_steps SET created_at = now() WHERE created_at IS NULL;")
    op.execute("ALTER TABLE execution_steps ALTER COLUMN created_at SET NOT NULL;")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'execution_steps_pkey') THEN
            ALTER TABLE execution_steps DROP CONSTRAINT execution_steps_pkey;
          END IF;
        END
        $$;
        """
    )
    op.execute("ALTER TABLE execution_steps ADD PRIMARY KEY (id, created_at);")

    op.create_table(
        "llm_calls",
        # TimescaleDB requires the partition column to be part of unique indexes / PKs.
        # Use a composite primary key (id, timestamp) to allow hypertable conversion.
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("run_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("provider", llm_provider, nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("metadata", sa.Text(), nullable=True),
    )
    op.create_index("ix_llm_calls_timestamp", "llm_calls", ["timestamp"], unique=False)
    op.create_index("ix_llm_calls_agent_id", "llm_calls", ["agent_id"], unique=False)
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"], unique=False)

    # Hypertables
    op.execute("SELECT create_hypertable('llm_calls', 'timestamp', if_not_exists => TRUE);")
    op.execute("SELECT create_hypertable('execution_steps', 'created_at', if_not_exists => TRUE);")

    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("run_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
    )
    op.create_index("ix_tool_invocations_timestamp", "tool_invocations", ["timestamp"], unique=False)
    op.create_index("ix_tool_invocations_tool_name", "tool_invocations", ["tool_name"], unique=False)

    op.create_table(
        "llm_pricing",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider", llm_provider, nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_cost_per_1k", sa.Float(), nullable=False, server_default="0"),
        sa.Column("completion_cost_per_1k", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_llm_pricing_model", "llm_pricing", ["model"], unique=False)

    op.create_table(
        "budget_limits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("team_id", sa.String(length=36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("daily_limit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("monthly_limit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hard_stop_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_budget_limits_team_id", "budget_limits", ["team_id"], unique=False)
    op.create_index("ix_budget_limits_agent_id", "budget_limits", ["agent_id"], unique=False)

    op.create_table(
        "usage_aggregations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("day", sa.DateTime(timezone=True), nullable=False),
        sa.Column("team_id", sa.String(length=36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_usage_aggregations_day", "usage_aggregations", ["day"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.String(length=36), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"], unique=False)
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("resource_type", sa.String(length=255), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)

    # Hypertables
    op.execute("SELECT create_hypertable('llm_calls', 'timestamp', if_not_exists => TRUE);")
    op.execute("SELECT create_hypertable('agent_runs', 'created_at', if_not_exists => TRUE);")
    op.execute("SELECT create_hypertable('execution_steps', 'created_at', if_not_exists => TRUE);")

    # Retention policies (keep 90 days)
    op.execute("SELECT add_retention_policy('llm_calls', INTERVAL '90 days', if_not_exists => TRUE);")
    op.execute("SELECT add_retention_policy('agent_runs', INTERVAL '90 days', if_not_exists => TRUE);")
    op.execute("SELECT add_retention_policy('execution_steps', INTERVAL '90 days', if_not_exists => TRUE);")

    # Compression policies (compress chunks older than 7 days)
    op.execute(
        """
        ALTER TABLE llm_calls SET (
          timescaledb.compress,
          timescaledb.compress_segmentby = 'agent_id'
        );
        """
    )
    op.execute(
        """
        ALTER TABLE agent_runs SET (
          timescaledb.compress,
          timescaledb.compress_segmentby = 'agent_id'
        );
        """
    )
    op.execute(
        """
        ALTER TABLE execution_steps SET (
          timescaledb.compress,
          timescaledb.compress_segmentby = 'run_id'
        );
        """
    )
    op.execute("SELECT add_compression_policy('llm_calls', INTERVAL '7 days', if_not_exists => TRUE);")
    op.execute("SELECT add_compression_policy('agent_runs', INTERVAL '7 days', if_not_exists => TRUE);")
    op.execute("SELECT add_compression_policy('execution_steps', INTERVAL '7 days', if_not_exists => TRUE);")

    # Continuous aggregate for llm_calls (hourly)
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $$
            BEGIN
              IF to_regclass('public.llm_calls_hourly') IS NULL THEN
                EXECUTE $SQL$
                  CREATE MATERIALIZED VIEW llm_calls_hourly
                  WITH (timescaledb.continuous) AS
                  SELECT
                    time_bucket(INTERVAL '1 hour', timestamp) AS hour,
                    agent_id,
                    COUNT(*) AS call_count,
                    SUM(prompt_tokens + completion_tokens) AS total_tokens,
                    SUM(cost) AS total_cost
                  FROM llm_calls
                  GROUP BY hour, agent_id
                  WITH NO DATA
                $SQL$;
              END IF;
            END
            $$;
            """
        )

        op.execute(
            """
            DO $$
            BEGIN
              PERFORM add_continuous_aggregate_policy(
                'llm_calls_hourly',
                start_offset => INTERVAL '7 days',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour'
              );
            EXCEPTION
              WHEN duplicate_object THEN NULL;
              WHEN invalid_parameter_value THEN NULL;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_usage_aggregations_day", table_name="usage_aggregations")
    op.drop_table("usage_aggregations")

    op.drop_index("ix_budget_limits_agent_id", table_name="budget_limits")
    op.drop_index("ix_budget_limits_team_id", table_name="budget_limits")
    op.drop_table("budget_limits")

    op.drop_index("ix_llm_pricing_model", table_name="llm_pricing")
    op.drop_table("llm_pricing")

    op.drop_index("ix_tool_invocations_tool_name", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_timestamp", table_name="tool_invocations")
    op.drop_table("tool_invocations")

    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_agent_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_timestamp", table_name="llm_calls")
    op.drop_table("llm_calls")

    op.drop_index("ix_execution_steps_run_id", table_name="execution_steps")
    op.drop_table("execution_steps")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("ix_agents_team_id", table_name="agents")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")

    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_table("teams")

    # Drop enum types (must be dropped after tables)
    op.execute("DROP TYPE IF EXISTS audit_action;")
    op.execute("DROP TYPE IF EXISTS llm_provider;")
    op.execute("DROP TYPE IF EXISTS step_type;")
    op.execute("DROP TYPE IF EXISTS run_status;")
    op.execute("DROP TYPE IF EXISTS agent_framework;")

    op.execute("DROP EXTENSION IF EXISTS timescaledb;")


