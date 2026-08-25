#!/usr/bin/env python
# coding: utf-8

# In[ ]:

import pyomo.environ as pyo
from schemas import ExpansionInput, ExpansionResults

def build_and_solve_expansion(
    inputs: ExpansionInput, solver_name: str = "appsi_highs"
) -> ExpansionResults:
    model = pyo.ConcreteModel(name="Capacity_Expansion_Exact")

    # Sets
    T = list(range(len(inputs.demand_profile)))
    hours_count = len(T)
    time_scaling_factor = hours_count / 8760.0

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

    def vb_domain_rule(m, g):
        return (
            pyo.NonNegativeIntegers
            if new_dict[g].is_integer
            else pyo.NonNegativeReals
        )

    model.vb = pyo.Var(model.NEW, domain=vb_domain_rule)

    # Constraints

    # 1. Supply - Demand Balance
    def sd_rule(m, t):
        return (
            sum(m.vPowerEx[g, t] for g in m.EX)
            + sum(m.vPowerNew[ng, t] for ng in m.NEW)
        ) == inputs.demand_profile[t]

    model.sd_constr = pyo.Constraint(model.T, rule=sd_rule)

    # 2. Existing Capacity & CF Limits
    def ex_cap_rule(m, g, t):
        gen_info = ex_dict[g]
        cf_profile = inputs.vre_cfs.get(g)
        if gen_info.is_variable and cf_profile is not None:
            return (
                m.vPowerEx[g, t]
                <= gen_info.capacity_mw * cf_profile[t]
            )
        return m.vPowerEx[g, t] <= gen_info.capacity_mw

    model.ex_cap_constr = pyo.Constraint(model.EX, model.T, rule=ex_cap_rule)

    # 3. New Capacity & CF Limits
    def new_cap_rule(m, ng, t):
        gen_info = new_dict[ng]
        max_cap = gen_info.unit_capacity_mw * m.vb[ng]
        cf_profile = inputs.vre_cfs.get(ng)
        if gen_info.is_variable and cf_profile is not None:
            return (
                m.vPowerNew[ng, t] <= max_cap * cf_profile[t]
            )
        return m.vPowerNew[ng, t] <= max_cap

    model.new_cap_constr = pyo.Constraint(model.NEW, model.T, rule=new_cap_rule)

    # 4. PRM Constraint at Peak Hour
    def prm_rule(m, t):
        firm_ex = sum(
            ex_dict[g].capacity_mw * inputs.vre_cfs[g][t]
            if (ex_dict[g].is_variable and g in inputs.vre_cfs)
            else ex_dict[g].capacity_mw
            for g in m.EX
        )
        firm_new = sum(
            new_dict[ng].unit_capacity_mw * m.vb[ng] * inputs.vre_cfs[ng][t]
            if (new_dict[ng].is_variable and ng in inputs.vre_cfs)
            else new_dict[ng].unit_capacity_mw * m.vb[ng]
            for ng in m.NEW
        )
        return (firm_ex + firm_new) >= (
            inputs.system_params.prm_margin * inputs.demand_profile[t]
        )

    model.prm_constr = pyo.Constraint([peak_t], rule=prm_rule)

    # 5. CO2 Cap Constraint (if defined)
    if inputs.system_params.co2_cap_tons is not None:

        def co2_rule(m):
            co2_ex = sum(
                m.vPowerEx[g, t] * ex_dict[g].co2_tons_per_mwh
                for g in m.EX
                for t in m.T
            )
            co2_new = sum(
                m.vPowerNew[ng, t] * new_dict[ng].co2_tons_per_mwh
                for ng in m.NEW
                for t in m.T
            )
            return (co2_ex + co2_new) <= inputs.system_params.co2_cap_tons

        model.co2_constr = pyo.Constraint(rule=co2_rule)

    # Objective Function
    def obj_rule(m):
        cost_ex = sum(
            (
                ex_dict[g].heat_rate * ex_dict[g].fuel_cost
                + ex_dict[g].vom_cost
            )
            * m.vPowerEx[g, t]
            for g in m.EX
            for t in m.T
        )
        cost_new_op = sum(
            new_dict[ng].op_cost_per_mwh * m.vPowerNew[ng, t]
            for ng in m.NEW
            for t in m.T
        )
        cost_new_capex = sum(
            (
                new_dict[ng].annual_capex_per_mw
                * new_dict[ng].unit_capacity_mw
                * time_scaling_factor
            )
            * m.vb[ng]
            for ng in m.NEW
        )
        return cost_ex + cost_new_op + cost_new_capex

    model.cost = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    # ---------------------------------------------------------
    # STEP 1: Επίλυση MILP (με APPSI ή Standard Solver)
    # ---------------------------------------------------------
    opt = pyo.SolverFactory(solver_name)
    results = opt.solve(model, tee=False)

    units_built = {ng: pyo.value(model.vb[ng]) for ng in NEW}
    new_cap_mw = {
        ng: units_built[ng] * new_dict[ng].unit_capacity_mw for ng in NEW
    }

    # ---------------------------------------------------------
    # STEP 2: Fixing Integers & Conversion to Pure Continuous LP
    # ---------------------------------------------------------
    for ng in NEW:
        model.vb[ng].fix(units_built[ng])

    pyo.TransformationFactory("core.relax_integer_vars").apply_to(model)

    # ---------------------------------------------------------
    # STEP 3: Επανεπίλυση με Standard Highs Interface για DUALS
    # ---------------------------------------------------------
    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    
    # Χρησιμοποιούμε το standard 'highs' interface που υποστηρίζει πλήρως το Suffix
    opt_lp = pyo.SolverFactory("appsi_highs")
    results_lp = opt_lp.solve(model, tee=False)

    marginal_prices = []
    for t in T:
        constr = model.sd_constr[t]
        if constr in model.dual:
            marginal_prices.append(abs(float(model.dual[constr])))
        else:
            marginal_prices.append(0.0)
    print("LP termination:", results_lp.solver.termination_condition)
    print("Dual suffix entries:", len(model.dual))

    co2_shadow_price = 0.0#new
    if inputs.system_params.co2_cap_tons is not None and hasattr(model, "co2_constr"):
        if model.co2_constr in model.dual:
            co2_shadow_price = abs(float(model.dual[model.co2_constr]))#new

    # ---------------------------------------------------------
    # STEP 4: Parsing Αποτελεσμάτων
    # ---------------------------------------------------------
    gen_tot = {}
    dispatch_profile = {}

    for g in EX:
        profile = [pyo.value(model.vPowerEx[g, t]) for t in T]
        dispatch_profile[g] = profile
        gen_tot[g] = sum(profile)

    for ng in NEW:
        profile = [pyo.value(model.vPowerNew[ng, t]) for t in T]
        dispatch_profile[ng] = profile
        gen_tot[ng] = sum(profile)

    total_co2 = sum(
        pyo.value(model.vPowerEx[g, t]) * ex_dict[g].co2_tons_per_mwh
        for g in EX
        for t in T
    ) + sum(
        pyo.value(model.vPowerNew[ng, t]) * new_dict[ng].co2_tons_per_mwh
        for ng in NEW
        for t in T
    )

    avg_price = (
        sum(marginal_prices) / len(marginal_prices) if marginal_prices else 0.0
    )

    return ExpansionResults(
        status=str(results.solver.status),
        total_cost=pyo.value(model.cost),
        units_built=units_built,
        new_capacity_mw=new_cap_mw,
        co2_emissions_tons=total_co2,
        generation_mwh=gen_tot,
        dispatch_profile_mw=dispatch_profile,
        marginal_prices_per_mwh=marginal_prices,
        average_marginal_price=avg_price,
    )