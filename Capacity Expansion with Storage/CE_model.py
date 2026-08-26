#!/usr/bin/env python
# coding: utf-8

# In[ ]:

import math
import pyomo.environ as pyo
from schemas import ExpansionInput, ExpansionResults


def build_and_solve_expansion(
    inputs: ExpansionInput, solver_name: str = "appsi_highs"
) -> ExpansionResults:
    model = pyo.ConcreteModel(name="Capacity_Expansion_Storage_Exact")

    # Sets
    T = list(range(len(inputs.demand_profile)))
    hours_count = len(T)
    time_scaling_factor = hours_count / 8760.0

    EX_G = [g.name for g in inputs.existing_fleet]
    NEW_G = [g.name for g in inputs.candidate_fleet]
    EX_S = [s.name for s in inputs.existing_storage]
    NEW_S = [s.name for s in inputs.candidate_storage]

    model.T = pyo.Set(initialize=T)
    model.EX_G = pyo.Set(initialize=EX_G)
    model.NEW_G = pyo.Set(initialize=NEW_G)
    model.EX_S = pyo.Set(initialize=EX_S)
    model.NEW_S = pyo.Set(initialize=NEW_S)

    ex_g_dict = {g.name: g for g in inputs.existing_fleet}
    new_g_dict = {g.name: g for g in inputs.candidate_fleet}
    ex_s_dict = {s.name: s for s in inputs.existing_storage}
    new_s_dict = {s.name: s for s in inputs.candidate_storage}

    # Peak demand time index
    peak_t = max(T, key=lambda t: inputs.demand_profile[t])

    # --- VARIABLES ---
    # Generators
    model.vPowerEx = pyo.Var(model.EX_G, model.T, domain=pyo.NonNegativeReals)
    model.vPowerNew = pyo.Var(model.NEW_G, model.T, domain=pyo.NonNegativeReals)

    def vb_domain_rule(m, g):
        return (
            pyo.NonNegativeIntegers
            if new_g_dict[g].is_integer
            else pyo.NonNegativeReals
        )

    model.vb = pyo.Var(model.NEW_G, domain=vb_domain_rule)

    # Storage Decision Variables (Capacity Expansion)
    model.vCapStorageMW = pyo.Var(model.NEW_S, domain=pyo.NonNegativeReals, bounds=lambda m, ns: (0, new_s_dict[ns].max_power_mw))
    model.vCapStorageMWh = pyo.Var(model.NEW_S, domain=pyo.NonNegativeReals,  bounds=lambda m, ns: (0, new_s_dict[ns].max_energy_mwh))

    # Storage Hourly Operation
    model.vDischargeEx = pyo.Var(model.EX_S, model.T, domain=pyo.NonNegativeReals)
    model.vChargeEx = pyo.Var(model.EX_S, model.T, domain=pyo.NonNegativeReals)
    model.vSocEx = pyo.Var(model.EX_S, model.T, domain=pyo.NonNegativeReals)

    model.vDischargeNew = pyo.Var(model.NEW_S, model.T, domain=pyo.NonNegativeReals)
    model.vChargeNew = pyo.Var(model.NEW_S, model.T, domain=pyo.NonNegativeReals)
    model.vSocNew = pyo.Var(model.NEW_S, model.T, domain=pyo.NonNegativeReals)

    # --- CONSTRAINTS ---

    # 1. Supply - Demand Balance (Generation + Discharge = Demand + Charge)
    def sd_rule(m, t):
        gen_tot = (
            sum(m.vPowerEx[g, t] for g in m.EX_G)
            + sum(m.vPowerNew[ng, t] for ng in m.NEW_G)
        )
        dis_tot = (
            sum(m.vDischargeEx[s, t] for s in m.EX_S)
            + sum(m.vDischargeNew[ns, t] for ns in m.NEW_S)
        )
        chg_tot = (
            sum(m.vChargeEx[s, t] for s in m.EX_S)
            + sum(m.vChargeNew[ns, t] for ns in m.NEW_S)
        )
        return (gen_tot + dis_tot) == (inputs.demand_profile[t] + chg_tot)

    model.sd_constr = pyo.Constraint(model.T, rule=sd_rule)

    # 2. Existing Generator Limits
    def ex_cap_rule(m, g, t):
        gen_info = ex_g_dict[g]
        cf_profile = inputs.vre_cfs.get(g)
        if gen_info.is_variable and cf_profile is not None:
            return m.vPowerEx[g, t] <= gen_info.capacity_mw * cf_profile[t]
        return m.vPowerEx[g, t] <= gen_info.capacity_mw

    model.ex_cap_constr = pyo.Constraint(model.EX_G, model.T, rule=ex_cap_rule)

    # 3. New Generator Limits
    def new_cap_rule(m, ng, t):
        gen_info = new_g_dict[ng]
        max_cap = gen_info.unit_capacity_mw * m.vb[ng]
        cf_profile = inputs.vre_cfs.get(ng)
        if gen_info.is_variable and cf_profile is not None:
            return m.vPowerNew[ng, t] <= max_cap * cf_profile[t]
        return m.vPowerNew[ng, t] <= max_cap

    model.new_cap_constr = pyo.Constraint(model.NEW_G, model.T, rule=new_cap_rule)

    # 4. Storage Limits & SOC Tracking (Existing Storage)
    def ex_s_dis_rule(m, s, t):
        return m.vDischargeEx[s, t] <= ex_s_dict[s].power_capacity_mw
    model.ex_s_dis_constr = pyo.Constraint(model.EX_S, model.T, rule=ex_s_dis_rule)

    def ex_s_chg_rule(m, s, t):
        return m.vChargeEx[s, t] <= ex_s_dict[s].power_capacity_mw
    model.ex_s_chg_constr = pyo.Constraint(model.EX_S, model.T, rule=ex_s_chg_rule)

    def ex_s_soc_cap_rule(m, s, t):
        return m.vSocEx[s, t] <= ex_s_dict[s].energy_capacity_mwh
    model.ex_s_soc_cap_constr = pyo.Constraint(model.EX_S, model.T, rule=ex_s_soc_cap_rule)

    def ex_s_soc_track_rule(m, s, t):
        eff = math.sqrt(ex_s_dict[s].round_trip_efficiency)
        prev_soc = ex_s_dict[s].initial_soc_mwh if t == 0 else m.vSocEx[s, t - 1]
        return m.vSocEx[s, t] == prev_soc + (m.vChargeEx[s, t] * eff) - (m.vDischargeEx[s, t] / eff)
    model.ex_s_soc_track_constr = pyo.Constraint(model.EX_S, model.T, rule=ex_s_soc_track_rule)

    # 5. Storage Limits & SOC Tracking (Candidate Storage)
    def new_s_dis_rule(m, ns, t):
        return m.vDischargeNew[ns, t] <= m.vCapStorageMW[ns]
    model.new_s_dis_constr = pyo.Constraint(model.NEW_S, model.T, rule=new_s_dis_rule)

    def new_s_chg_rule(m, ns, t):
        return m.vChargeNew[ns, t] <= m.vCapStorageMW[ns]
    model.new_s_chg_constr = pyo.Constraint(model.NEW_S, model.T, rule=new_s_chg_rule)

    def new_s_soc_cap_rule(m, ns, t):
        return m.vSocNew[ns, t] <= m.vCapStorageMWh[ns]
    model.new_s_soc_cap_constr = pyo.Constraint(model.NEW_S, model.T, rule=new_s_soc_cap_rule)

    def new_s_duration_cap_rule(m, ns):
        if new_s_dict[ns].max_duration_hours is not None:
            return m.vCapStorageMWh[ns] <= m.vCapStorageMW[ns] * new_s_dict[ns].max_duration_hours
        return pyo.Constraint.Skip
    model.new_s_duration_constr = pyo.Constraint(model.NEW_S, rule=new_s_duration_cap_rule)

    def new_s_soc_track_rule(m, ns, t):
        eff = math.sqrt(new_s_dict[ns].round_trip_efficiency)
        prev_soc = 0.0 if t == 0 else m.vSocNew[ns, t - 1]
        return m.vSocNew[ns, t] == prev_soc + (m.vChargeNew[ns, t] * eff) - (m.vDischargeNew[ns, t] / eff)
    model.new_s_soc_track_constr = pyo.Constraint(model.NEW_S, model.T, rule=new_s_soc_track_rule)

    # 6. PRM Constraint at Peak Hour (Gens + Storage Discharge Capability)
    def prm_rule(m, t):
        firm_ex_g = sum(
            ex_g_dict[g].capacity_mw * inputs.vre_cfs[g][t]
            if (ex_g_dict[g].is_variable and g in inputs.vre_cfs)
            else ex_g_dict[g].capacity_mw
            for g in m.EX_G
        )
        firm_new_g = sum(
            new_g_dict[ng].unit_capacity_mw * m.vb[ng] * inputs.vre_cfs[ng][t]
            if (new_g_dict[ng].is_variable and ng in inputs.vre_cfs)
            else new_g_dict[ng].unit_capacity_mw * m.vb[ng]
            for ng in m.NEW_G
        )
        firm_ex_s = sum(ex_s_dict[s].power_capacity_mw for s in m.EX_S)
        firm_new_s = sum(m.vCapStorageMW[ns] for ns in m.NEW_S)

        return (firm_ex_g + firm_new_g + firm_ex_s + firm_new_s) >= (
            inputs.system_params.prm_margin * inputs.demand_profile[t]
        )

    model.prm_constr = pyo.Constraint([peak_t], rule=prm_rule)

    # 7. CO2 Cap Constraint
    if inputs.system_params.co2_cap_tons is not None:
        scaled_co2_cap = inputs.system_params.co2_cap_tons * time_scaling_factor
        def co2_rule(m):
            co2_ex = sum(
                m.vPowerEx[g, t] * ex_g_dict[g].co2_tons_per_mwh
                for g in m.EX_G
                for t in m.T
            )
            co2_new = sum(
                m.vPowerNew[ng, t] * new_g_dict[ng].co2_tons_per_mwh
                for ng in m.NEW_G
                for t in m.T
            )
            return (co2_ex + co2_new) <= scaled_co2_cap

        model.co2_constr = pyo.Constraint(rule=co2_rule)

    #8. Cycle limit constraint
    def max_cycles_rule(m, ns):
        if new_s_dict[ns].max_cycles_per_year is None:
            return pyo.Constraint.Skip
        total_discharge = sum(m.vDischargeNew[ns, t] for t in m.T)
        max_energy_throughput = new_s_dict[ns].max_cycles_per_year * m.vCapStorageMWh[ns] *          time_scaling_factor
        return total_discharge <= max_energy_throughput

    model.max_cycles_constr = pyo.Constraint(model.NEW_S, rule=max_cycles_rule)

    # --- OBJECTIVE FUNCTION ---
    def obj_rule(m):
        # Generator Operational & CAPEX
        cost_ex_op = sum(
            (ex_g_dict[g].heat_rate * ex_g_dict[g].fuel_cost + ex_g_dict[g].vom_cost)
            * m.vPowerEx[g, t]
            for g in m.EX_G
            for t in m.T
        )
        cost_new_op = sum(
            new_g_dict[ng].op_cost_per_mwh * m.vPowerNew[ng, t]
            for ng in m.NEW_G
            for t in m.T
        )
        cost_gen_capex = sum(
            (new_g_dict[ng].annual_capex_per_mw * new_g_dict[ng].unit_capacity_mw * time_scaling_factor)
            * m.vb[ng]
            for ng in m.NEW_G
        )

        # Storage Operational & CAPEX
        cost_s_ex_op = sum(
            ex_s_dict[s].vom_cost_per_mwh * m.vDischargeEx[s, t]
            for s in m.EX_S
            for t in m.T
        )
        cost_s_new_op = sum(
            new_s_dict[ns].vom_cost_per_mwh * m.vDischargeNew[ns, t]
            for ns in m.NEW_S
            for t in m.T
        )
        cost_s_capex = sum(
            (new_s_dict[ns].annual_capex_per_mw * m.vCapStorageMW[ns] +
             new_s_dict[ns].annual_capex_per_mwh * m.vCapStorageMWh[ns])
            * time_scaling_factor
            for ns in m.NEW_S
        )
        cost_s_degradation = sum(
            new_s_dict[ns].degradation_cost_per_mwh * m.vDischargeNew[ns, t]
            for ns in m.NEW_S for t in m.T
        )

        return (
            cost_ex_op
            + cost_new_op
            + cost_gen_capex
            + cost_s_ex_op
            + cost_s_new_op
            + cost_s_capex
            + cost_s_degradation
        )

    model.cost = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    # ---------------------------------------------------------
    # STEP 1: MILP Solve
    # ---------------------------------------------------------
    opt = pyo.SolverFactory(solver_name)
    results = opt.solve(model, tee=False)

    #units_built = {ng: pyo.value(model.vb[ng]) for ng in NEW_G}
    units_built = {}
    for ng in NEW_G:
        raw_val = pyo.value(model.vb[ng])
        if new_g_dict[ng].is_integer:
            units_built[ng] = round(raw_val)
        else:
            units_built[ng] = max(0.0, raw_val)
    new_cap_mw = {ng: units_built[ng] * new_g_dict[ng].unit_capacity_mw for ng in NEW_G}
    
    new_s_mw = {ns: pyo.value(model.vCapStorageMW[ns]) for ns in NEW_S}
    new_s_mwh = {ns: pyo.value(model.vCapStorageMWh[ns]) for ns in NEW_S}

    # ---------------------------------------------------------
    # STEP 2: Fix Integers & Relax Model for Duals / LMPs
    # ---------------------------------------------------------
    for ng in NEW_G:
        model.vb[ng].fix(units_built[ng])

    pyo.TransformationFactory("core.relax_integer_vars").apply_to(model)

    # ---------------------------------------------------------
    # STEP 3: Re-solve LP for Duals
    # ---------------------------------------------------------
    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    opt_lp = pyo.SolverFactory("appsi_highs")
    results_lp = opt_lp.solve(model, tee=False)

    marginal_prices = []
    for t in T:
        constr = model.sd_constr[t]
        if constr in model.dual:
            marginal_prices.append(abs(float(model.dual[constr])))
        else:
            marginal_prices.append(0.0)

    # ---------------------------------------------------------
    # STEP 4: Parse Profiles & Results
    # ---------------------------------------------------------
    gen_tot = {}
    dispatch_profile = {}
    charge_profile = {}
    soc_profile = {}
    curtailment_profile = {}

    for g in EX_G:
        profile = [pyo.value(model.vPowerEx[g, t]) for t in T]
        dispatch_profile[g] = profile
        gen_tot[g] = sum(profile)
        
        if ex_g_dict[g].is_variable and g in inputs.vre_cfs:
            curtailment_profile[g] = [
                max(0.0, ex_g_dict[g].capacity_mw * inputs.vre_cfs[g][t] - profile[t])
                for t in T
            ]

    for ng in NEW_G:
        profile = [pyo.value(model.vPowerNew[ng, t]) for t in T]
        dispatch_profile[ng] = profile
        gen_tot[ng] = sum(profile)
        
        if new_g_dict[ng].is_variable and ng in inputs.vre_cfs:
            available_cap = new_g_dict[ng].unit_capacity_mw * units_built[ng]
            curtailment_profile[ng] = [
                max(0.0, available_cap * inputs.vre_cfs[ng][t] - profile[t])
                for t in T
            ]

    for s in EX_S:
        dispatch_profile[s] = [pyo.value(model.vDischargeEx[s, t]) for t in T]
        charge_profile[s] = [pyo.value(model.vChargeEx[s, t]) for t in T]
        soc_profile[s] = [pyo.value(model.vSocEx[s, t]) for t in T]

    for ns in NEW_S:
        dispatch_profile[ns] = [pyo.value(model.vDischargeNew[ns, t]) for t in T]
        charge_profile[ns] = [pyo.value(model.vChargeNew[ns, t]) for t in T]
        soc_profile[ns] = [pyo.value(model.vSocNew[ns, t]) for t in T]

    total_co2 = sum(
        pyo.value(model.vPowerEx[g, t]) * ex_g_dict[g].co2_tons_per_mwh
        for g in EX_G
        for t in T
    ) + sum(
        pyo.value(model.vPowerNew[ng, t]) * new_g_dict[ng].co2_tons_per_mwh
        for ng in NEW_G
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
        new_storage_mw=new_s_mw,
        new_storage_mwh=new_s_mwh,
        co2_emissions_tons=total_co2,
        generation_mwh=gen_tot,
        dispatch_profile_mw=dispatch_profile,
        charge_profile_mw=charge_profile,
        soc_profile_mwh=soc_profile,
        curtailment_mw=curtailment_profile,
        marginal_prices_per_mwh=marginal_prices,
        average_marginal_price=avg_price,
    )