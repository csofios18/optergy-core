#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .schemas import ExpansionResults


def plot_expansion_results(
    results_no_cap: ExpansionResults,
    results_cap: ExpansionResults,
    demand_profile: list,
    co2_cap_limit: float,
    hours_to_plot: int = 168
):
    """
    Παράγει τα 4 κλασικά γραφήματα σύγκρισης (Cost, CO2, Investments, Dispatch).
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
    # GRAPH 3: New Installed Capacity Built (MW)
    # ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))

    all_candidates = sorted(
        list(
            set(
                list(results_no_cap.new_capacity_mw.keys())
                + list(results_cap.new_capacity_mw.keys())
            )
        )
    )
    mw_no_cap = [results_no_cap.new_capacity_mw.get(c, 0.0) for c in all_candidates]
    mw_cap = [results_cap.new_capacity_mw.get(c, 0.0) for c in all_candidates]

    x = np.arange(len(all_candidates))
    width = 0.35

    ax.bar(x - width / 2, mw_no_cap, width, label='Without CO2 Cap', color='#3498db')
    ax.bar(x + width / 2, mw_cap, width, label='With CO2 Cap', color='#2ecc71')
    ax.set_ylabel('New Built Capacity (MW)')
    ax.set_title('Investment Decisions in Candidate Units')
    ax.set_xticks(x)
    ax.set_xticklabels(all_candidates)
    ax.legend()

    plt.tight_layout()
    plt.show()

    # ---------------------------------------------------------
    # GRAPH 4: Hourly Dispatch Stacked Area Plot (First N hours)
    # ---------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    # 1. Μετατροπή σε DataFrame
    # 2. .clip(lower=0) για να μηδενιστούν οι απειροελάχιστες αρνητικές τιμές του solver (π.χ. -1e-15)
    # 3. .iloc[:hours_to_plot] για να κόψουμε ακριβώς τις ίδιες ώρες με το demand
    df_no_cap_sub = pd.DataFrame(results_no_cap.dispatch_profile_mw).clip(lower=0).iloc[:hours_to_plot]
    df_cap_sub = pd.DataFrame(results_cap.dispatch_profile_mw).clip(lower=0).iloc[:hours_to_plot]
    demand_sub = demand_profile[:hours_to_plot]

    # Plot Unconstrained
    df_no_cap_sub.plot(kind='area', stacked=True, ax=ax1, alpha=0.85, colormap='tab10')
    ax1.plot(demand_sub, color='black', linewidth=2, linestyle='--', label='System Demand')
    ax1.set_title(
        f'Hourly Dispatch Profile - Unconstrained Scenario (First {hours_to_plot} Hours)'
    )
    ax1.set_ylabel('Power Generation (MW)')
    ax1.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))

    # Plot Constrained
    df_cap_sub.plot(kind='area', stacked=True, ax=ax2, alpha=0.85, colormap='tab10')
    ax2.plot(demand_sub, color='black', linewidth=2, linestyle='--', label='System Demand')
    ax2.set_title(
        f'Hourly Dispatch Profile - CO2 Cap Scenario (First {hours_to_plot} Hours)'
    )
    ax2.set_xlabel('Hour (t)')
    ax2.set_ylabel('Power Generation (MW)')
    ax2.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))

    plt.tight_layout()
    plt.show()
    
    # GRAPH 5: Hourly Marginal Prices / LMPs (€/MWh)
    # ---------------------------------------------------------
    if results_no_cap.marginal_prices_per_mwh and results_cap.marginal_prices_per_mwh:
        fig, ax = plt.subplots(figsize=(14, 5))
        
        lmp_no_cap = results_no_cap.marginal_prices_per_mwh[:hours_to_plot]
        lmp_cap = results_cap.marginal_prices_per_mwh[:hours_to_plot]
        
        ax.plot(lmp_no_cap, label=f'Without CO2 Cap (Avg: €{results_no_cap.average_marginal_price:.1f}/MWh)', color='#3498db', linewidth=1.8)
        ax.plot(lmp_cap, label=f'With CO2 Cap (Avg: €{results_cap.average_marginal_price:.1f}/MWh)', color='#e74c3c', linewidth=1.8, linestyle='--')
        
        ax.set_title(f'Hourly Electricity Marginal Price / Shadow Price (First {hours_to_plot} Hours)')
        ax.set_xlabel('Hour (t)')
        ax.set_ylabel('Marginal Price (€/MWh)')
        ax.legend(loc='upper right')
        
        plt.tight_layout()
        plt.show()

