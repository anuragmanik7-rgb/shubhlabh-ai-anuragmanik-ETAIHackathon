from datetime import datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
import hashlib, json, uuid

CITIES = ['Bengaluru', 'Mumbai', 'Delhi']
SEGMENTS = ['Value seekers', 'Family baskets', 'Convenience shoppers', 'Regular buyers']
IST=timezone(timedelta(hours=5,minutes=30))

def business_date(at=None):
    return (at or datetime.now(timezone.utc)).astimezone(IST).date()

def now():
    return datetime.now(timezone.utc).isoformat()

def uid(prefix=''):
    return prefix + uuid.uuid4().hex[:16]

def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()

class AppError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        self.code, self.message, self.status, self.fields = code, message, status, fields or {}

class Brief(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='Seven-day grocery promotion', max_length=120)
    instruction: str = Field(default='', max_length=2500)
    cities: list[Literal['Bengaluru','Mumbai','Delhi']] = Field(default_factory=lambda: CITIES.copy(), min_length=1)
    objective: Literal['profit','clearance','conservative'] = 'profit'
    budget_paise: int = Field(default=3000000, ge=0, le=100000000)
    horizon: Literal[3,5,7] = 7
    mechanisms: list[Literal['markdown','coupon','bundle']] = Field(default_factory=lambda: ['markdown','coupon','bundle'], min_length=1)
    min_margin_bps: int = Field(default=1500, ge=0, le=9000)
    max_discount_bps: int = Field(default=2000, ge=0, le=5000)
    risk_lambda: float = Field(default=.5, ge=0, le=5)
    clearance_target: int = Field(default=0, ge=0, le=5000)
    clearance_hard: bool = False
    scenarios: int = Field(default=200, ge=20, le=1000)
    seed: int = Field(default=42, ge=0, le=1000000)
    mode: Literal['offline','live'] = 'offline'
    parent_id: str | None = Field(default=None,max_length=100)
    start_date: str | None = None
    exclude_skus: list[str] = Field(default_factory=list, max_length=120)
    exclude_categories: list[str] = Field(default_factory=list, max_length=12)
    exclude_city_categories: list[str] = Field(default_factory=list, max_length=18)  # 'Delhi|Home essentials'
    compiled_instruction: str | None = Field(default=None, max_length=2500)  # instruction text already merged into this brief
    window_start: str | None = None  # festival campaign: the date the kit shows as day 0 (display only; solving uses start_date)

    @field_validator('cities','mechanisms')
    @classmethod
    def unique_scope(cls, value):
        if len(value)!=len(set(value)):raise ValueError('Scope entries must be unique')
        return value

class RevisionAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)

class Envelope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_budget_paise: int = Field(default=3000000, ge=0)
    max_discount_bps: int = Field(default=2000, ge=0, le=5000)
    min_margin_bps: int = Field(default=1500, ge=0, le=9000)
    cities: list[str] = Field(default_factory=lambda: CITIES.copy())
    mechanisms: list[str] = Field(default_factory=lambda: ['markdown','coupon','bundle'])
    allow_auto_replan: bool = False
    permitted_skus: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    max_changed_offer_fraction: float = Field(default=1.0,ge=0,le=1)

class EventInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(default_factory=lambda: uid('evt_'), min_length=1,max_length=80)
    kind: Literal['inventory','competitor','budget']
    city: str | None = None
    sku: str | None = None
    value: int = Field(ge=0, le=100000000)
    observed_at: str = Field(default_factory=now)
    replan: bool = True

    @field_validator('observed_at')
    @classmethod
    def valid_time(cls,value):
        stamp=datetime.fromisoformat(value)
        if stamp.tzinfo is None:raise ValueError('Timestamp requires a UTC offset')
        return value

class WebhookEventInput(EventInput):
    """External deliveries must retain the same identity and time on retry."""
    event_id: str = Field(min_length=1,max_length=80)
    observed_at: str

class Redemption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_id: str=Field(min_length=1,max_length=100)
    candidate_id: str=Field(min_length=1,max_length=100)
    order_id: str = Field(min_length=1,max_length=80)
    quantity: int = Field(default=1, ge=1, le=100)
    segment: str
    basket_paise: int = Field(default=100000, ge=0)
    at: str | None = None

class OwnerLogin(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token: str=Field(min_length=1,max_length=512,strict=True)

class SimulationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scenarios: int=Field(default=200,ge=20,le=1000)
    seed: int|None=Field(default=None,ge=0,le=1000000)

class EvidenceCorrection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    fields: dict

class ConnectorPreview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan_id: str=Field(min_length=1,max_length=100)

class FixtureRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode: Literal['offline','live']='offline'
    kind: Literal['inventory','competitor','products','transactions']='inventory'
