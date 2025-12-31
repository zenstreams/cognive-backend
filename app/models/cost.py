from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, and_, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LLMProvider(str, enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    OTHER = "other"


class LLMCall(Base):
    """Time-series table (TimescaleDB hypertable recommended)."""

    __tablename__ = "llm_calls"
    # TimescaleDB requires the partition column to be part of unique indexes / PKs.
    # We use a composite primary key (id, timestamp) and keep a non-unique index on timestamp.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    provider: Mapped[LLMProvider] = mapped_column(Enum(LLMProvider, name="llm_provider", native_enum=True), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    # NOTE: `metadata` is a reserved attribute in SQLAlchemy declarative models.
    metadata_: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)

    run: Mapped[Optional["AgentRun"]] = relationship(
        primaryjoin=lambda: and_(LLMCall.run_id == AgentRun.id, LLMCall.run_created_at == AgentRun.created_at),
        foreign_keys=lambda: (LLMCall.run_id, LLMCall.run_created_at),
        back_populates="llm_calls",
    )
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="llm_calls")


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NOTE: `metadata` is a reserved attribute in SQLAlchemy declarative models.
    metadata_: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)

    run: Mapped[Optional["AgentRun"]] = relationship(
        primaryjoin=lambda: and_(ToolInvocation.run_id == AgentRun.id, ToolInvocation.run_created_at == AgentRun.created_at),
        foreign_keys=lambda: (ToolInvocation.run_id, ToolInvocation.run_created_at),
        back_populates="tool_invocations",
    )
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="tool_invocations")


class LLMPricing(Base):
    __tablename__ = "llm_pricing"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[LLMProvider] = mapped_column(Enum(LLMProvider, name="llm_provider", native_enum=True), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    prompt_cost_per_1k: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completion_cost_per_1k: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BudgetLimit(Base):
    __tablename__ = "budget_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    daily_limit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monthly_limit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hard_stop_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped[Optional["Team"]] = relationship(back_populates="budget_limits")
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="budget_limits")


class UsageAggregation(Base):
    __tablename__ = "usage_aggregations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped[Optional["Team"]] = relationship(back_populates="usage_aggregations")
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="usage_aggregations")


