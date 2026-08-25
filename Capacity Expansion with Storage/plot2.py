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
    Παράγει τα γραφήματα σύγκρισης με απόλυτη ασφάλεια στα μήκη των δεδομένων.
    """
    plt.style.use(
        'seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default'
    )

    hours = hours_to_plot

    # ---------------------------------------------------------
    # GRAPH 1 & 2: Cost & CO2 Emissions Comparison
    # ---------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    scenarios = ['Without CO2 Cap', 'With CO2 Cap']
    costs = [results_no_cap.total_cost, results_cap.total_cost]
    emissions = [results_no_cap.co2_emissions_tons, results_cap.co2_emissions_tons]

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
    # GRAPH 4: Hourly Dispatch Stacked Area Plot (First N hours)
    # ---------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    def build_dispatch_plot(ax, results: ExpansionResults, title_text: str):
        disp_data = {}
        if results.dispatch_profile_mw:
            for k, v in results.dispatch_profile_mw.items():
                vals = [max(0.0, float(val)) for val in v[:hours]]
                if len(vals) < hours:
                    vals.extend([0.0] * (hours - len(vals)))
                disp_data[k] = vals
        
        actual_len = len(next(iter(disp_data.values()))) if disp_data else hours
        df_disp = pd.DataFrame(disp_data, index=range(actual_len)) if disp_data else pd.DataFrame(index=range(hours))
        
        stack_list = [df_disp] if not df_disp.empty else []
        if hasattr(results, 'discharge_profile_mw') and results.discharge_profile_mw:
            dis_data = {}
            for k, v in results.discharge_profile_mw.items():
                vals = [max(0.0, float(val)) for val in v[:hours]]
                if len(vals) < hours:
                    vals.extend([0.0] * (hours - len(vals)))
                dis_data[f"{k} (Discharge)"] = vals
            df_dis = pd.DataFrame(dis_data, index=range(actual_len)) if dis_data else pd.DataFrame(index=range(hours))
            if not df_dis.empty:
                stack_list.append(df_dis)
                
        df_stack = pd.concat(stack_list, axis=1) if stack_list else pd.DataFrame(index=range(hours))

        charge_data = {}
        if hasattr(results, 'charge_profile_mw') and results.charge_profile_mw:
            for k, v in results.charge_profile_mw.items():
                vals = [max(0.0, float(val)) for val in v[:hours]]
                if len(vals) < hours:
                    vals.extend([0.0] * (hours - len(vals)))
                charge_data[k] = vals
        df_charge = pd.DataFrame(charge_data, index=range(actual_len)) if charge_data else pd.DataFrame(index=range(hours))
        
        total_charging = df_charge.sum(axis=1) if not df_charge.empty else pd.Series(0.0, index=range(actual_len))
        demand_sub = pd.Series(demand_profile[:actual_len])
        gross_demand = demand_sub + total_charging

        if not df_stack.empty:
            df_stack.plot(kind='area', stacked=True, ax=ax, alpha=0.85, colormap='tab10')

        ax.plot(demand_sub.values, color='black', linewidth=2, linestyle='--', label='Net Demand')
        if not df_charge.empty and (total_charging > 0).any():
            ax.plot(gross_demand.values, color='darkred', linewidth=1.5, linestyle=':', label='Gross Demand (+Charging)')

        ax.set_title(title_text)
        ax.set_ylabel('Power (MW)')
        ax.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=9)

    build_dispatch_plot(ax1, results_no_cap, f"Hourly Dispatch Profile - Unconstrained Scenario (First {hours} Hours)")
    build_dispatch_plot(ax2, results_cap, f"Hourly Dispatch Profile - CO2 Cap Scenario (First {hours} Hours)")
    ax2.set_xlabel('Hour (t)')

    plt.tight_layout()
    plt.show()

    # ---------------------------------------------------------
    # GRAPH 5: Storage State of Charge (SOC - MWh)
    # ---------------------------------------------------------
    if results_no_cap.soc_profile_mwh or results_cap.soc_profile_mwh:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)

        def make_soc_df(soc_dict):
            if not soc_dict:
                return pd.DataFrame()
            soc_data = {}
            for k, v in soc_dict.items():
                vals = [max(0.0, float(val)) for val in v[:hours]]
                if len(vals) < hours:
                    vals.extend([0.0] * (hours - len(vals)))
                soc_data[k] = vals
            return pd.DataFrame(soc_data, index=range(hours))

        df_soc_nocap = make_soc_df(results_no_cap.soc_profile_mwh)
        df_soc_cap = make_soc_df(results_cap.soc_profile_mwh)

        if not df_soc_nocap.empty:
            df_soc_nocap.plot(ax=ax1, linewidth=1.8)
            ax1.set_title(f'Storage State of Charge (SOC) - Unconstrained Scenario (First {hours} Hours)')
            ax1.set_ylabel('Stored Energy (MWh)')
            ax1.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=9)

        if not df_soc_cap.empty:
            df_soc_cap.plot(ax=ax2, linewidth=1.8)
            ax2.set_title(f'Storage State of Charge (SOC) - CO2 Cap Scenario (First {hours} Hours)')
            ax2.set_xlabel('Hour (t)')
            ax2.set_ylabel('Stored Energy (MWh)')
            ax2.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=9)

        plt.tight_layout()
        plt.show()

    # ---------------------------------------------------------
    # GRAPH 6: Hourly Marginal Prices / LMPs (€/MWh)
    # ---------------------------------------------------------
    if results_no_cap.marginal_prices_per_mwh and results_cap.marginal_prices_per_mwh:
        fig, ax = plt.subplots(figsize=(14, 5))

        lmp_no_cap = results_no_cap.marginal_prices_per_mwh[:hours]
        lmp_cap = results_cap.marginal_prices_per_mwh[:hours]

        ax.plot(lmp_no_cap, label=f'Without CO2 Cap (Avg: €{results_no_cap.average_marginal_price:.1f}/MWh)', color='#3498db', linewidth=1.8)
        ax.plot(lmp_cap, label=f'With CO2 Cap (Avg: €{results_cap.average_marginal_price:.1f}/MWh)', color='#e74c3c', linewidth=1.8, linestyle='--')

        ax.set_title(f'Hourly Electricity Marginal Price / Shadow Price (First {hours} Hours)')
        ax.set_xlabel('Hour (t)')
        ax.set_ylabel('Marginal Price (€/MWh)')
        ax.legend(loc='upper right')

        plt.tight_layout()
        plt.show()

