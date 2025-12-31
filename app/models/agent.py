from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AgentFramework(str, enum.Enum):
    LANGCHAIN = "langchain"
    CREWAI = "crewai"
    AUTOGEN = "autogen"
    CUSTOM = "custom"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agents: Mapped[list["Agent"]] = relationship(back_populates="team")
    budget_limits: Mapped[list["BudgetLimit"]] = relationship(back_populates="team")
    usage_aggregations: Mapped[list["UsageAggregation"]] = relationship(back_populates="team")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    framework: Mapped[AgentFramework] = mapped_column(
        Enum(AgentFramework, name="agent_framework", native_enum=True),
        nullable=False,
        default=AgentFramework.CUSTOM,
    )
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team: Mapped[Team | None] = relationship(back_populates="agents")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    llm_calls: Mapped[list["LLMCall"]] = relationship(back_populates="agent")
    tool_invocations: Mapped[list["ToolInvocation"]] = relationship(back_populates="agent")
    budget_limits: Mapped[list["BudgetLimit"]] = relationship(back_populates="agent")
    usage_aggregations: Mapped[list["UsageAggregation"]] = relationship(back_populates="agent")


