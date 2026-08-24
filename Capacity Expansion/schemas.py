#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from pydantic import BaseModel, Field
from typing import List, Dict

class GeneratorTech(BaseModel):
    name: str
    is_variable: bool = False  # True για ΑΠΕ (Φ/Β, Αιολικά)
    capex_per_mw: float = Field(..., ge=0, description="Ετήσιο ισοδύναμο CAPEX ($/MW/year)")
    om_fixed_per_mw: float = Field(..., ge=0, description="Σταθερό O&M ($/MW/year)")
    var_cost_per_mwh: float = Field(..., ge=0, description="Μεταβλητό κόστος / Καύσιμο ($/MWh)")
    co2_tons_per_mwh: float = Field(default=0.0, ge=0, description="Εκπομπές CO2 (tons/MWh)")
    existing_capacity_mw: float = Field(default=0.0, ge=0)
    max_new_capacity_mw: float = Field(default=10000.0, ge=0)

class SystemParameters(BaseModel):
    prm_margin: float = Field(default=0.15, ge=0, description="Planning Reserve Margin (π.χ. 15%)")
    co2_cap_tons: float = Field(default=1e9, ge=0, description="Ετήσιο ανώτατο όριο CO2")
    voLL: float = Field(default=3000.0, ge=0, description="Value of Lost Load ($/MWh)")

class ExpansionInput(BaseModel):
    system_params: SystemParameters
    technologies: List[GeneratorTech]
    demand_profile: List[float]  # 8760 ώρες (ή συντομότερη χρονοσειρά)
    # capacity_factors: Dict[TechName, List[float]] για ΑΠΕ
    capacity_factors: Dict[str, List[float]] = Field(default_factory=dict)

class GenerationDetail(BaseModel):
    tech_name: str
    capacity_mw: float
    total_generation_mwh: float
    annual_cost: float

class ExpansionResults(BaseModel):
    status: str
    total_cost: float
    unserved_energy_mwh: float
    co2_emissions_tons: float
    built_capacities: Dict[str, float]  # Tech -> Total MW
    details: List[GenerationDetail]

