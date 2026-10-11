"""Public response contracts, shared through the generated OpenAPI schema."""
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field

class PublicModel(BaseModel):
    model_config=ConfigDict(extra='allow')

class OfferOutput(PublicModel):
    id:str
    sku:str
    skus:list[str]
    name:str
    city:Literal['Bengaluru','Mumbai','Delhi']
    mechanism:Literal['markdown','coupon','bundle']
    channel:Literal['internal_sandbox']='internal_sandbox'
    discount_bps:int=Field(ge=0,le=5000)
    fixed_discount_paise:int|None=None
    duration:int=Field(ge=1,le=7)
    start_day:int=Field(ge=0,le=6)
    segment:str
    max_redemptions:int=Field(ge=1)
    price_paise:int=Field(gt=0)
    liability_paise:int=Field(ge=0)
    media_paise:int=Field(ge=0)
    unit_contribution_paise:int
    margin_bps:int
    incremental_contribution_paise:int
    cannibalization_paise:int
    cannibalization:list[dict[str,Any]]
    allocation:dict[str,int]
    source_refs:list[str]
    reason:str

class SimulationWorld(PublicModel):
    contribution_paise:int
    revenue_paise:int
    spend_paise:int
    clearance_units:float
    stockout_rate:float
    units:float

class DistributionPoint(PublicModel):
    value_paise:int
    count:int

class SimulationOutput(PublicModel):
    baseline:SimulationWorld
    optimized:SimulationWorld
    incremental_contribution_paise:int
    p10_paise:int
    p50_paise:int
    p90_paise:int
    downside_probability:float=Field(ge=0,le=1)
    scenarios:int=Field(ge=20,le=1000)
    seed:int
    distribution:list[DistributionPoint]
    assumptions:list[str]
    sensitivity:dict[str,Any]
    evidence_status:Literal['simulated']

class ValidationOutput(PublicModel):
    passed:bool
    errors:list[str]
    liability_paise:int
    allocation:dict[str,int]
    checks:list[str]

class PlanOutput(PublicModel):
    id:str
    run_id:str
    revision:int=Field(ge=1)
    status:Literal['awaiting_approval','approved','active','paused','blocked']
    brief:dict[str,Any]
    offers:list[OfferOutput]
    simulation:SimulationOutput
    validation:ValidationOutput
    snapshot_id:str
    policy_version:int
    mode:Literal['offline','live']
    created_at:str

class RunOutput(PublicModel):
    id:str
    plan_id:str
    revision:int
    state:Literal['received','planning','simulating','validated','needs_input','failed','completed']
    step:int=Field(ge=0,le=7)
    mode:Literal['offline','live']
    events:list[dict[str,Any]]
    snapshot_id:str
    solver_attempts:int=Field(default=0,ge=0,le=3)
    solver_attempt_limit:int=Field(default=3,ge=3,le=3)
