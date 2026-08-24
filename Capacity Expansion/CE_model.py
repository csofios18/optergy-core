#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pyomo.environ as pyo
from schemas import ExpansionInput, ExpansionResults, GenerationDetail

def build_and_solve_expansion(inputs: ExpansionInput, solver_name: str = "highs") -> ExpansionResults:
    # 1. Δημιουργία Concrete Model
    model = pyo.ConcreteModel(name="Capacity_Expansion")

    # 2. Sets
    T = list(range(len(inputs.demand_profile)))
    G = [tech.name for tech in inputs.technologies]
    
    model.T = pyo.Set(initialize=T)
    model.G = pyo.Set(initialize=G)
    
    # Quick lookup dictionaries
    tech_dict = {t.name: t for t in inputs.technologies}

    # 3. Decision Variables
    model.Cap = pyo.Var(model.G, domain=pyo.NonNegativeReals)
    model.Gen = pyo.Var(model.G, model.T, domain=pyo.NonNegativeReals)
    model.UnservedEnergy = pyo.Var(model.T, domain=pyo.NonNegativeReals)

    # 4. Constraints
    
    # A. Max Capacity Limit (Existing + New)
    def cap_limit_rule(m, g):
        return m.Cap[g] <= tech_dict[g].existing_capacity_mw + tech_dict[g].max_new_capacity_mw
    model.CapLimitConstr = pyo.Constraint(model.G, rule=cap_limit_rule)

    # B. Generation Limit (Dispatch vs Availability)
    def gen_limit_rule(m, g, t):
        if tech_dict[g].is_variable:
            cf = inputs.capacity_factors.get(g, [1.0] * len(T))[t]
            return m.Gen[g, t] <= m.Cap[g] * cf
        return m.Gen[g, t] <= m.Cap[g]
    model.GenLimitConstr = pyo.Constraint(model.G, model.T, rule=gen_limit_rule)

    # C. Supply-Demand Balance
    def demand_rule(m, t):
        return sum(m.Gen[g, t] for g in m.G) + m.UnservedEnergy[t] == inputs.demand_profile[t]
    model.DemandConstr = pyo.Constraint(model.T, rule=demand_rule)

    # D. Planning Reserve Margin (PRM)
    peak_demand = max(inputs.demand_profile)
    def prm_rule(m):
        # Απλοποιημένο: 100% derating για θερμικές, Derated χωρητικότητα για ΑΠΕ
        firm_capacity = sum(
            m.Cap[g] * (0.2 if tech_dict[g].is_variable else 1.0) for g in m.G
        )
        return firm_capacity >= peak_demand * (1 + inputs.system_params.prm_margin)
    model.PRMConstr = pyo.Constraint(rule=prm_rule)

    # E. CO2 Cap Constraint
    def co2_cap_rule(m):
        total_co2 = sum(
            m.Gen[g, t] * tech_dict[g].co2_tons_per_mwh 
            for g in m.G for t in m.T
        )
        return total_co2 <= inputs.system_params.co2_cap_tons
    model.CO2CapConstr = pyo.Constraint(rule=co2_cap_rule)

    # 5. Objective Function (Minimizing Total Annual System Cost)
    def obj_rule(m):
        inv_cost = sum(
            m.Cap[g] * (tech_dict[g].capex_per_mw + tech_dict[g].om_fixed_per_mw)
            for g in m.G
        )
        var_cost = sum(
            m.Gen[g, t] * tech_dict[g].var_cost_per_mwh
            for g in m.G for t in m.T
        )
        unserved_cost = sum(
            m.UnservedEnergy[t] * inputs.system_params.voLL 
            for t in m.T
        )
        return inv_cost + var_cost + unserved_cost

    model.Obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    # 6. Solve Model
    opt = pyo.SolverFactory(solver_name)
    results = opt.solve(model, tee=False)

    # 7. Parse & Structuring Results
    built_caps = {g: pyo.value(model.Cap[g]) for g in G}
    total_unserved = sum(pyo.value(model.UnservedEnergy[t]) for t in T)
    total_co2 = sum(
        pyo.value(model.Gen[g, t]) * tech_dict[g].co2_tons_per_mwh 
        for g in G for t in T
    )

    details = []
    for g in G:
        gen_tot = sum(pyo.value(model.Gen[g, t]) for t in T)
        annual_cost = built_caps[g] * (tech_dict[g].capex_per_mw + tech_dict[g].om_fixed_per_mw) + \
                      gen_tot * tech_dict[g].var_cost_per_mwh
        details.append(GenerationDetail(
            tech_name=g,
            capacity_mw=built_caps[g],
            total_generation_mwh=gen_tot,
            annual_cost=annual_cost
        ))

    return ExpansionResults(
        status=str(results.solver.status),
        total_cost=pyo.value(model.Obj),
        unserved_energy_mwh=total_unserved,
        co2_emissions_tons=total_co2,
        built_capacities=built_caps,
        details=details
    )

