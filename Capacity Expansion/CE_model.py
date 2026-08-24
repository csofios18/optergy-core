#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pyomo.environ as pyo
from schemas import ExpansionInput, ExpansionResults

def build_and_solve_expansion(inputs: ExpansionInput, solver_name: str = "glpk") -> ExpansionResults:
    model = pyo.ConcreteModel(name="Capacity_Expansion_Exact")

    # Sets
    T = list(range(len(inputs.demand_profile)))
    hours_count = len(T)
    time_scaling_factor = hours_count / 8760.0  # Αναλογία CAPEX για τις ώρες του simulation

    EX = [g.name for g in inputs.existing_fleet]
    NEW = [g.name for g in inputs.candidate_fleet]
    
    model.T = pyo.Set(initialize=T)
    model.EX = pyo.Set(initialize=EX)
    model.NEW = pyo.Set(initialize=NEW)
    
    ex_dict = {g.name: g for g in inputs.existing_fleet}
    new_dict = {g.name: g for g in inputs.candidate_fleet}

    # Peak demand time index
    peak_t = max(T, key=lambda t: inputs.demand_profile[t])

    # Variables
    model.vPowerEx = pyo.Var(model.EX, model.T, domain=pyo.NonNegativeReals)
    model.vPowerNew = pyo.Var(model.NEW, model.T, domain=pyo.NonNegativeReals)
    
    # Investment decision: Integer/Binary or Continuous depending on config
    def vb_domain_rule(m, g):
        return pyo.NonNegativeIntegers if new_dict[g].is_integer else pyo.NonNegativeReals
    model.vb = pyo.Var(model.NEW, domain=pyo.NonNegativeIntegers)

    # Constraints
    
    # 1. Supply - Demand Balance
    def sd_rule(m, t):
        return (sum(m.vPowerEx[g, t] for g in m.EX) + 
                sum(m.vPowerNew[ng, t] for ng in m.NEW)) == inputs.demand_profile[t]
    model.sd_constr = pyo.Constraint(model.T, rule=sd_rule)

    # 2. Existing Capacity & CF Limits
    def ex_cap_rule(m, g, t):
        gen_info = ex_dict[g]
        if gen_info.is_variable and g in inputs.solar_cfs:
            return m.vPowerEx[g, t] <= gen_info.capacity_mw * inputs.solar_cfs[g][t]
        return m.vPowerEx[g, t] <= gen_info.capacity_mw
    model.ex_cap_constr = pyo.Constraint(model.EX, model.T, rule=ex_cap_rule)

    # 3. New Capacity & CF Limits
    def new_cap_rule(m, ng, t):
        gen_info = new_dict[ng]
        max_cap = gen_info.unit_capacity_mw * m.vb[ng]
        if gen_info.is_variable and ng in inputs.wind_cfs:
            return m.vPowerNew[ng, t] <= max_cap * inputs.wind_cfs[ng][t]
        return m.vPowerNew[ng, t] <= max_cap
    model.new_cap_constr = pyo.Constraint(model.NEW, model.T, rule=new_cap_rule)

    # 4. PRM Constraint at Peak Hour
    def prm_rule(m, t):
        firm_ex = sum(
            ex_dict[g].capacity_mw * (inputs.solar_cfs[g][t] if ex_dict[g].is_variable else 1.0)
            for g in m.EX
        )
        firm_new = sum(
            new_dict[ng].unit_capacity_mw * m.vb[ng] * (inputs.wind_cfs[ng][t] if new_dict[ng].is_variable else 1.0)
            for ng in m.NEW
        )
        return (firm_ex + firm_new) >= inputs.system_params.prm_margin * inputs.demand_profile[t]
    model.prm_constr = pyo.Constraint([peak_t], rule=prm_rule)

    # 5. CO2 Cap Constraint (if defined)
    if inputs.system_params.co2_cap_tons is not None:
        def co2_rule(m):
            co2_ex = sum(m.vPowerEx[g, t] * ex_dict[g].co2_tons_per_mwh for g in m.EX for t in m.T)
            co2_new = sum(m.vPowerNew[ng, t] * new_dict[ng].co2_tons_per_mwh for ng in m.NEW for t in m.T)
            return (co2_ex + co2_new) <= inputs.system_params.co2_cap_tons
        model.co2_constr = pyo.Constraint(rule=co2_rule)

    # Objective Function
    def obj_rule(m):
        # Existing Fleet OpCost
        cost_ex = sum(
            (ex_dict[g].heat_rate * ex_dict[g].fuel_cost + ex_dict[g].vom_cost) * m.vPowerEx[g, t]
            for g in m.EX for t in m.T
        )
        # New Fleet OpCost
        cost_new_op = sum(
            new_dict[ng].op_cost_per_mwh * m.vPowerNew[ng, t]
            for ng in m.NEW for t in m.T
        )
        # New Fleet Investment Cost (Scaled to simulation horizon)
        cost_new_capex = sum(
            (new_dict[ng].annual_capex_per_mw * new_dict[ng].unit_capacity_mw * time_scaling_factor) * m.vb[ng]
            for ng in m.NEW
        )
        return cost_ex + cost_new_op + cost_new_capex

    model.cost = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    # Solve
    opt = pyo.SolverFactory(solver_name)
    results = opt.solve(model, tee=False)

    # Parse Outputs
    units_built = {ng: pyo.value(model.vb[ng]) for ng in NEW}
    new_cap_mw = {ng: units_built[ng] * new_dict[ng].unit_capacity_mw for ng in NEW}
    
    gen_tot = {}
    for g in EX:
        gen_tot[g] = sum(pyo.value(model.vPowerEx[g, t]) for t in T)
    for ng in NEW:
        gen_tot[ng] = sum(pyo.value(model.vPowerNew[ng, t]) for t in T)

    total_co2 = sum(
        pyo.value(model.vPowerEx[g, t]) * ex_dict[g].co2_tons_per_mwh for g in EX for t in T
    ) + sum(
        pyo.value(model.vPowerNew[ng, t]) * new_dict[ng].co2_tons_per_mwh for ng in NEW for t in T
    )

    return ExpansionResults(
        status=str(results.solver.status),
        total_cost=pyo.value(model.cost),
        units_built=units_built,
        new_capacity_mw=new_cap_mw,
        co2_emissions_tons=total_co2,
        generation_mwh=gen_tot
    )