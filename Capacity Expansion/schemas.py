#!/usr/bin/env python
# coding: utf-8

# In[4]:


#1
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ExistingGenerator(BaseModel):
    name: str
    fuel_type: str
    capacity_mw: float = Field(..., ge=0)
    heat_rate: float = Field(default=0.0, ge=0)  # MMBtu/MWh
    fuel_cost: float = Field(default=0.0, ge=0)  # $/MMBtu
    vom_cost: float = Field(default=0.0, ge=0)   # $/MWh
    co2_tons_per_mwh: float = Field(default=0.0, ge=0)
    is_variable: bool = False


class CandidateGenerator(BaseModel):
    name: str
    fuel_type: str
    unit_capacity_mw: float = Field(..., ge=0)   # Ισχύς ανά block (MW)
    annual_capex_per_mw: float = Field(..., ge=0)  # $/MW/year
    op_cost_per_mwh: float = Field(..., ge=0)     # $/MWh
    co2_tons_per_mwh: float = Field(default=0.0, ge=0)
    is_variable: bool = False
    is_integer: bool = True  # True για διακριτές μονάδες, False για συνεχές sizing


class SystemParameters(BaseModel):
    prm_margin: float = Field(default=1.15, ge=1.0)  # 1.15 = 115% της αιχμής
    co2_cap_tons: Optional[float] = None             # Συνολικό όριο CO2


class ExpansionInput(BaseModel):
    system_params: SystemParameters
    existing_fleet: List[ExistingGenerator]
    candidate_fleet: List[CandidateGenerator]
    demand_profile: List[float]  # MWh ανά ώρα
    vre_cfs: Dict[str, List[float]] = {}
    
class ExpansionResults(BaseModel):
    status: str
    total_cost: float
    units_built: Dict[str, float]        # Αριθμός μονάδων/blocks
    new_capacity_mw: Dict[str, float]    # Νέα ισχύς (MW)
    co2_emissions_tons: float
    generation_mwh: Dict[str, float]
    dispatch_profile_mw: Dict[str, List[float]] = Field(default_factory=dict)  # Required for plots.py
    marginal_prices_per_mwh: List[float] = Field(default_factory=list)
    average_marginal_price: float = 0.0

# Alias to ensure backwards compatibility with plot imports
OptimizationResult = ExpansionResults