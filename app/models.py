from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Decision(str, Enum):
    ALLOW = "ALLOW"
    ASK_HUMAN = "ASK_HUMAN"
    DENY = "DENY"


class TransactionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    authorization_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(default="demo-agent", min_length=1, max_length=128)
    intent: str = Field(min_length=1, max_length=500)
    # Informational only. Spending authority comes exclusively from SQLite.
    intended_amount: Decimal = Field(gt=0)
    amount: Decimal = Field(gt=0)
    recipient: str = Field(min_length=2, max_length=128)
    asset: str = Field(default="NEAR", min_length=1, max_length=32)
    network: str = Field(default="testnet", min_length=1, max_length=32)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("amount", "intended_amount")
    @classmethod
    def finite_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Amount must be finite")
        return value

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value


class GuardrailResult(BaseModel):
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
