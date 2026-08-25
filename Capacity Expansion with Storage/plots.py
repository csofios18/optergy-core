#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from schemas import ExpansionResults


def plot_expansion_results(
    results_no_cap: ExpansionResults,
    results_cap: ExpansionResults,
    demand_profile: list,
    co2_cap_limit: float,
    hours_to_plot: int = 168
):
    """
    Παράγει τα γραφήματα σύγκρισης (Cost, CO2, Investments, Storage Capacity, Dispatch & Charging, SOC, LMPs).
    """
    plt.style.use(
        'seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default'
    )

    # ---------------------------------------------------------
    # GRAPH 1 & 2: Cost & CO2 Emissions Comparison
    # ---------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    scenarios = ['Without CO2 Cap', 'With CO2 Cap']
    costs = [results_no_cap.total_cost, results_cap.total_cost]
    emissions = [results_no_cap.co2_emissions_tons, results_cap.co2_emissions_tons]

    # Bar 1: Total Cost
    bars1 = axes[0].bar(scenarios, costs, color=['#3498db', '#2ecc71'], width=0.5)
    axes[0].set_ylabel('Total Cost (€)')
    axes[0].set_title('Total System Cost Comparison')
    for bar in bars1:
        yval = bar.get_height()
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            yval * 1.01,
            f"€{yval:,.0f}",
            ha='center',
            va='bottom',
            fontweight='bold'
        )

    # Bar 2: CO2 Emissions
    bars2 = axes[1].bar(scenarios, emissions, color=['#e74c3c', '#2ecc71'], width=0.5)
    axes[1].axhline(
        y=co2_cap_limit,
        color='red',
        linestyle='--',
        label=f'CO2 Cap ({co2_cap_limit:,.0f} t)'
    )
    axes[1].set_ylabel('CO2 Emissions (Tons)')
    axes[1].set_title('Total CO2 Emissions Comparison')
    axes[1].legend()
    for bar in bars2:
        yval = bar.get_height()
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            yval * 1.01,
            f"{yval:,.0f} t",
            ha='center',
            va='bottom',
            fontweight='bold'
        )

    plt.tight_layout()
    plt.show()

    # ---------------------------------------------------------
    # GRAPH 3: New Installed Capacity Built (Generators & Storage)
    # ---------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 3a. Generators & Storage Power (MW)
    all_mw_keys = sorted(
        list(
            set(
                list(results_no_cap.new_capacity_mw.keys()) + list(results_cap.new_capacity_mw.keys()) +
                list(results_no_cap.new_storage_mw.keys()) + list(results_cap.new_storage_mw.keys())
            )
        )
    )
    if all_mw_keys:
        mw_no_cap = [results_no_cap.new_capacity_mw.get(k, 0.0) + results_no_cap.new_storage_mw.get(k, 0.0) for k in all_mw_keys]
        mw_cap = [results_cap.new_capacity_mw.get(k, 0.0) + results_cap.new_storage_mw.get(k, 0.0) for k in all_mw_keys]

        x = np.arange(len(all_mw_keys))
        width = 0.35
        ax1.bar(x - width / 2, mw_no_cap, width, label='Without CO2 Cap', color='#3498db')
        ax1.bar(x + width / 2, mw_cap, width, label='With CO2 Cap', color='#2ecc71')
        ax1.set_ylabel('New Installed Power (MW)')
        ax1.set_title('New Capacity Built (MW)')
        ax1.set_xticks(x)
        ax1.set_xticklabels(all_mw_keys, rotation=15)
        ax1.legend()

    # 3b. Storage Energy Capacity (MWh)
    all_mwh_keys = sorted(
        list(set(list(results_no_cap.new_storage_mwh.keys()) + list(results_cap.new_storage_mwh.keys())))
    )
    if all_mwh_keys:
        mwh_no_cap = [results_no_cap.new_storage_mwh.get(k, 0.0) for k in all_mwh_keys]
        mwh_cap = [results_cap.new_storage_mwh.get(k, 0.0) for k in all_mwh_keys]

        x_mwh = np.arange(len(all_mwh_keys))
        ax2.bar(x_mwh - width / 2, mwh_no_cap, width, label='Without CO2 Cap', color='#9b59b6')
        ax2.bar(x_mwh + width / 2, mwh_cap, width, label='With CO2 Cap', color='#f1c40f')
        ax2.set_ylabel('New Energy Capacity (MWh)')
        ax2.set_title('New Storage Energy Built (MWh)')
        ax2.set_xticks(x_mwh)
        ax2.set_xticklabels(all_mwh_keys, rotation=15)
        ax2.legend()

    plt.tight_layout()
    plt.show()

    # ---------------------------------------------------------
    # GRAPH 4: Hourly Dispatch & Charging Profile Stack (First N hours)
    # ---------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    def prepare_dispatch_data(res: ExpansionResults):
        df_gen = pd.DataFrame(res.dispatch_profile_mw).clip(lower=0).iloc[:hours_to_plot]
        df_charge = pd.DataFrame(res.charge_profile_mw).clip(lower=0).iloc[:hours_to_plot]
        # Rename charge columns to avoid legend collision and make charging negative for stack plot
        df_charge = df_charge.rename(columns=lambda c: f"{c}_charge")
        return df_gen, df_charge

    # Scenario 1: Unconstrained
    df_gen_nocap, df_charge_nocap = prepare_dispatch_data(results_no_cap)
    demand_sub = pd.Series(demand_profile[:hours_to_plot])
    
    # Calculate Gross Demand (Demand + Charging)
    gross_demand_nocap = demand_sub + (df_charge_nocap.sum(axis=1).values if not df_charge_nocap.empty else 0)

    if not df_gen_nocap.empty:
        df_gen_nocap.plot(kind='area', stacked=True, ax=ax1, alpha=0.85, colormap='tab10')
    if not df_charge_nocap.empty:
        (-df_charge_nocap).plot(kind='area', stacked=True, ax=ax1, alpha=0.4, colormap='Set2')

    ax1.plot(demand_sub.values, color='black', linewidth=2, linestyle='--', label='Net Demand')
    ax1.plot(gross_demand_nocap.values, color='darkred', linewidth=1.5, linestyle=':', label='Gross Demand (+Charging)')
    ax1.axhline(0, color='gray', linewidth=0.8)
    ax1.set_title(f'Hourly Dispatch & Storage Profile - Unconstrained Scenario (First {hours_to_plot} Hours)')
    ax1.set_ylabel('Power (MW)')
    ax1.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))

    # Scenario 2: Constrained
    df_gen_cap, df_charge_cap = prepare_dispatch_data(results_cap)
    gross_demand_cap = demand_sub + (df_charge_cap.sum(axis=1).values if not df_charge_cap.empty else 0)

    if not df_gen_cap.empty:
        df_gen_cap.plot(kind='area', stacked=True, ax=ax2, alpha=0.85, colormap='tab10')
    if not df_charge_cap.empty:
        (-df_charge_cap).plot(kind='area', stacked=True, ax=ax2, alpha=0.4, colormap='Set2')

    ax2.plot(demand_sub.values, color='black', linewidth=2, linestyle='--', label='Net Demand')
    ax2.plot(gross_demand_cap.values, color='darkred', linewidth=1.5, linestyle=':', label='Gross Demand (+Charging)')
    ax2.axhline(0, color='gray', linewidth=0.8)
    ax2.set_title(f'Hourly Dispatch & Storage Profile - CO2 Cap Scenario (First {hours_to_plot} Hours)')
    ax2.set_xlabel('Hour (t)')
    ax2.set_ylabel('Power (MW)')
    ax2.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))

    plt.tight_layout()
    plt.show()

    # ---------------------------------------------------------
    # GRAPH 5: Storage State of Charge (SOC - MWh)
    # ---------------------------------------------------------
    if results_no_cap.soc_profile_mwh or results_cap.soc_profile_mwh:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)

        df_soc_nocap = pd.DataFrame(results_no_cap.soc_profile_mwh).iloc[:hours_to_plot]
        df_soc_cap = pd.DataFrame(results_cap.soc_profile_mwh).iloc[:hours_to_plot]

        if not df_soc_nocap.empty:
            df_soc_nocap.plot(ax=ax1, linewidth=1.8)
            ax1.set_title(f'Storage State of Charge (SOC) - Unconstrained Scenario (First {hours_to_plot} Hours)')
            ax1.set_ylabel('Stored Energy (MWh)')
            ax1.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))

        if not df_soc_cap.empty:
            df_soc_cap.plot(ax=ax2, linewidth=1.8)
            ax2.set_title(f'Storage State of Charge (SOC) - CO2 Cap Scenario (First {hours_to_plot} Hours)')
            ax2.set_xlabel('Hour (t)')
            ax2.set_ylabel('Stored Energy (MWh)')
            ax2.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))

        plt.tight_layout()
        plt.show()

    # ---------------------------------------------------------
    # GRAPH 6: Hourly Marginal Prices / LMPs (€/MWh)
    # ---------------------------------------------------------
    if results_no_cap.marginal_prices_per_mwh and results_cap.marginal_prices_per_mwh:
        fig, ax = plt.subplots(figsize=(14, 5))

        lmp_no_cap = results_no_cap.marginal_prices_per_mwh[:hours_to_plot]
        lmp_cap = results_cap.marginal_prices_per_mwh[:hours_to_plot]

        ax.plot(
            lmp_no_cap,
            label=f'Without CO2 Cap (Avg: €{results_no_cap.average_marginal_price:.1f}/MWh)',
            color='#3498db',
            linewidth=1.8
        )
        ax.plot(
            lmp_cap,
            label=f'With CO2 Cap (Avg: €{results_cap.average_marginal_price:.1f}/MWh)',
            color='#e74c3c',
            linewidth=1.8,
            linestyle='--'
        )

        ax.set_title(f'Hourly Electricity Marginal Price / Shadow Price (First {hours_to_plot} Hours)')
        ax.set_xlabel('Hour (t)')
        ax2_y_label = ax.set_ylabel('Marginal Price (€/MWh)')
        ax.legend(loc='upper right')

        plt.tight_layout()
        plt.show()