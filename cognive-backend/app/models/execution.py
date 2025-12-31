from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, and_, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, enum.Enum):
    LLM = "llm"
    TOOL = "tool"
    SYSTEM = "system"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), index=True, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", native_enum=True), index=True, nullable=False, default=RunStatus.QUEUED
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())

    agent: Mapped["Agent"] = relationship(back_populates="runs")
    steps: Mapped[list["ExecutionStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    llm_calls: Mapped[list["LLMCall"]] = relationship(back_populates="run")
    tool_invocations: Mapped[list["ToolInvocation"]] = relationship(back_populates="run")


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    # TimescaleDB hypertable compatibility: partitioning column must be part of PK/unique indexes.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    run_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, server_default=func.now())
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[StepType] = mapped_column(Enum(StepType, name="step_type", native_enum=True), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())

    run: Mapped[AgentRun] = relationship(
        primaryjoin=lambda: and_(ExecutionStep.run_id == AgentRun.id, ExecutionStep.run_created_at == AgentRun.created_at),
        foreign_keys=lambda: (ExecutionStep.run_id, ExecutionStep.run_created_at),
        back_populates="steps",
    )


