#!/usr/bin/env python
# coding: utf-8

# In[1]:


#c
from pyomo.environ import *
import pandas as pd

# Load and process demand data
D = pd.read_csv('demand.csv', header=None, index_col=0, names=['Demand(MWh)'])

# Create a mapping from current index to integer indices if needed
index_map = {label: i+1 for i, label in enumerate(D.index)}
D.index = D.index.map(index_map)

# Create model
model = ConcreteModel()

# Sets
model.IDX_g = Set(initialize=['CC1', 'CC2', 'CC3', 'CT1', 'Coal1', 'Nuc1'])
model.IDX_t = RangeSet(1, len(D))  # Ensure this range matches the integer indices

# Parameters
model.max_capacity = Param(model.IDX_g, initialize={'CC1': 150, 'CC2': 200, 'CC3': 250, 'CT1': 50, 'Coal1': 500, 'Nuc1': 500})
model.HR = Param(model.IDX_g, initialize={'CC1': 7, 'CC2': 8, 'CC3': 9, 'CT1': 15, 'Coal1': 12, 'Nuc1': 10})
model.FP = Param(model.IDX_g, initialize={'CC1': 4, 'CC2': 4, 'CC3': 4, 'CT1': 4, 'Coal1': 3, 'Nuc1': 1})
model.VOM = Param(model.IDX_g, initialize={'CC1': 5, 'CC2': 5, 'CC3': 5, 'CT1': 10, 'Coal1': 10, 'Nuc1': 5})

# Initialize demand parameter
model.D = Param(model.IDX_t, initialize=D['Demand(MWh)'].to_dict(), within=NonNegativeReals)

# Variables
model.P = Var(model.IDX_g, model.IDX_t, within=NonNegativeReals)

# Objective function
def objFunc(model):
    return sum(model.P[g, t] * (model.HR[g] * model.FP[g] + model.VOM[g]) for g in model.IDX_g for t in model.IDX_t)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
# Demand constraint: total generation must meet the demand
def demand_constraint(model, t):
    return sum(model.P[g, t] for g in model.IDX_g) >= model.D[t]
model.demandcon = Constraint(model.IDX_t, rule=demand_constraint)

# Capacity constraint: generation must not exceed capacity
def capacity_constraint(model, g, t):
    return model.P[g, t] <= model.max_capacity[g]
model.capacitycon = Constraint(model.IDX_g, model.IDX_t, rule=capacity_constraint)

# Solve
solver = SolverFactory('glpk')
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print results
model.pprint()


# In[2]:


#d
import matplotlib.pyplot as plt
import pandas as pd

# Extract the dispatch data for each generator and time period
dispatch = pd.DataFrame({g: [model.P[g, t].value for t in model.IDX_t] for g in model.IDX_g}, index=D.index)

# Plot the economic dispatch using a stacked bar chart
dispatch.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Economic Dispatch for the Day')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MW)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()


# In[3]:


#f
import matplotlib.pyplot as plt
import pandas as pd

# Ensure dual values are available
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Check if the solver ran correctly and if duals are available
if (results.solver.status == 'ok') and (results.solver.termination_condition == 'optimal'):
    print("Optimal solution found")
    print(f"Total Cost: ${model.cost():.2f}")
    
    # Retrieve and print MCP values
    mcp_values = []
    for t in model.IDX_t:
        if model.dual.get(model.demandcon[t], None) is not None:
            mcp_values.append(model.dual[model.demandcon[t]])
        else:
            mcp_values.append(None)
            print(f"Hour {t}: No dual value available")
    
    # Plot MCP values
    plt.figure(figsize=(12, 6))
    plt.plot(D.index, mcp_values, marker='o', linestyle='-', color='b')
    plt.title('Marginal Clearing Price (MCP) for Each Hour of the Day')
    plt.xlabel('Time (Hour)')
    plt.ylabel('MCP ($/MWh)')
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    
    # Calculate daily total consumer cost
    total_generation = sum(model.P[g, t].value for g in model.IDX_g for t in model.IDX_t)
    consumer_costs = sum(model.P[g, t].value * mcp_values[t-1] for g in model.IDX_g for t in model.IDX_t)
    
    # Calculate daily total producer cost
    producer_costs = sum(model.P[g, t].value * (model.VOM[g]+model.HR[g]*model.FP[g]) for g in model.IDX_g for t in model.IDX_t)
    
    print(f"Total Consumer Costs: ${consumer_costs:.2f}")
    print(f"Total Producer Costs: ${producer_costs:.2f}")
    
    # Print MCP values for each hour
    print("Electricity prices (MCP) for each time period:")
    for t, mcp in zip(model.IDX_t, mcp_values):
        print(f"Hour {t}: {mcp:.2f} $/MWh" if mcp is not None else f"Hour {t}: No dual value available")
    
    
else:
    print("Solver did not find an optimal solution.")


# In[5]:


#g_(with_CO2 emissions)
from pyomo.environ import *
import pandas as pd
import matplotlib.pyplot as plt

# Load and process demand data
D = pd.read_csv('demand.csv', header=None, index_col=0, names=['Demand(MWh)'])

# Create a mapping from current index to integer indices if needed
index_map = {label: i+1 for i, label in enumerate(D.index)}
D.index = D.index.map(index_map)

# Create model
model = ConcreteModel()

# Sets
model.IDX_g = Set(initialize=['CC1', 'CC2', 'CC3', 'CT1', 'Coal1', 'Nuc1'])
model.IDX_t = RangeSet(1, len(D))  # Ensure this range matches the integer indices

# Parameters
model.max_capacity = Param(model.IDX_g, initialize={'CC1': 150, 'CC2': 200, 'CC3': 250, 'CT1': 50, 'Coal1': 500, 'Nuc1': 500})
model.HR = Param(model.IDX_g, initialize={'CC1': 7, 'CC2': 8, 'CC3': 9, 'CT1': 15, 'Coal1': 12, 'Nuc1': 10})
model.FP = Param(model.IDX_g, initialize={'CC1': 4, 'CC2': 4, 'CC3': 4, 'CT1': 4, 'Coal1': 3, 'Nuc1': 1})
model.VOM = Param(model.IDX_g, initialize={'CC1': 5, 'CC2': 5, 'CC3': 5, 'CT1': 10, 'Coal1': 10, 'Nuc1': 5})

# CO2 Emissions (tons/MWh)
model.CO2_emissions = Param(model.IDX_g, initialize={'CC1': 0.05, 'CC2': 0.05, 'CC3': 0.05, 'CT1': 0.05, 'Coal1': 0.1, 'Nuc1': 0.0})

# CO2 Price
CO2_price = 25 #$/ton

# Initialize demand parameter
model.D = Param(model.IDX_t, initialize=D['Demand(MWh)'].to_dict(), within=NonNegativeReals)

# Variables
model.P = Var(model.IDX_g, model.IDX_t, within=NonNegativeReals)

# Objective function with CO2 price
def objFunc_CO2(model):
    return sum(model.P[g, t] * (model.HR[g] * model.FP[g] + model.VOM[g]) for g in model.IDX_g for t in model.IDX_t) \
           + CO2_price * sum(model.P[g, t] * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
model.cost = Objective(rule=objFunc_CO2, sense=minimize)

# Constraints
# Demand constraint: total generation must meet the demand
def demand_constraint(model, t):
    return sum(model.P[g, t] for g in model.IDX_g) >= model.D[t]
model.demandcon = Constraint(model.IDX_t, rule=demand_constraint)

# Capacity constraint: generation must not exceed capacity
def capacity_constraint(model, g, t):
    return model.P[g, t] <= model.max_capacity[g]
model.capacitycon = Constraint(model.IDX_g, model.IDX_t, rule=capacity_constraint)

# Solve
solver = SolverFactory('glpk')
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print results
model.pprint()

# Extract the dispatch data for each generator and time period
dispatch = pd.DataFrame({g: [model.P[g, t].value for t in model.IDX_t] for g in model.IDX_g}, index=D.index)

# Plot the economic dispatch using a stacked bar chart
dispatch.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Economic Dispatch for the Day with CO2 Pricing')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MW)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Check if the solver ran correctly and if duals are available
if (results.solver.status == 'ok') and (results.solver.termination_condition == 'optimal'):
    print(f"Total Cost with CO2 Pricing: ${model.cost():.2f}")
    
    # Retrieve and print MCP values
    mcp_values = []
    for t in model.IDX_t:
        if model.dual.get(model.demandcon[t], None) is not None:
            mcp_values.append(model.dual[model.demandcon[t]])
        else:
            mcp_values.append(None)
            print(f"Hour {t}: No dual value available")
    
    # Print MCP values for each hour
    print("Electricity prices (MCP) for each time period:")
    for t, mcp in zip(model.IDX_t, mcp_values):
        print(f"Hour {t}: {mcp:.2f} $/MWh" if mcp is not None else f"Hour {t}: No dual value available")
    
    # Plot MCP values
    plt.figure(figsize=(12, 6))
    plt.plot(D.index, mcp_values, marker='o', linestyle='-', color='b')
    plt.title('Marginal Clearing Price (MCP) for Each Hour of the Day with CO2 Pricing')
    plt.xlabel('Time (Hour)')
    plt.ylabel('MCP ($/MWh)')
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    
    # Calculate daily total consumer cost
    total_generation = sum(model.P[g, t].value for g in model.IDX_g for t in model.IDX_t)
    consumer_costs = sum(model.P[g, t].value * mcp_values[t-1] for g in model.IDX_g for t in model.IDX_t if mcp_values[t-1] is not None)
    
    # Calculate daily total producer cost
    producer_costs = sum(model.P[g, t].value *(model.VOM[g]+model.HR[g]*model.FP[g]+CO2_price * model.CO2_emissions[g]*model.HR[g]) for g in model.IDX_g for t in model.IDX_t)
    
    # Calculate total CO2 emissions
    total_CO2_emissions = sum(model.P[g, t].value * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
    
    print(f"Total Consumer Costs: ${consumer_costs:.2f}")
    print(f"Total Producer Costs: ${producer_costs:.2f}")
    print(f"Total CO2 Emissions: {total_CO2_emissions:.2f} tons")
    
else:
    print("Solver did not find an optimal solution.")


# In[2]:


#2a
from pyomo.environ import *
import pandas as pd

# Load and process demand data
D = pd.read_csv('demand.csv', header=None, index_col=0, names=['Demand(MWh)'])
S = pd.read_csv('solarCfs.csv', header=None, names=['Time', 'CF'])  # Load solar capacity factors

# Map time indices in both datasets
index_map = {label: i+1 for i, label in enumerate(D.index)}
S.set_index('Time', inplace=True)  # Set the 'Time' column as the index

# Convert time indices to match
D.index = D.index.map(index_map)
S.index = S.index.map(index_map)  # Ensure matching indices

# Create model
model = ConcreteModel()

# Sets
model.IDX_g = Set(initialize=['CC1', 'CC2', 'CC3', 'CT1', 'Coal1', 'Nuc1', 'Solar'])
model.IDX_t = RangeSet(1, len(D))  # Ensure this range matches the integer indices

# Parameters
model.max_capacity = Param(model.IDX_g, initialize={'CC1': 150, 'CC2': 200, 'CC3': 250, 'CT1': 50, 'Coal1': 500, 'Nuc1': 500, 'Solar': 100})
model.HR = Param(model.IDX_g, initialize={'CC1': 7, 'CC2': 8, 'CC3': 9, 'CT1': 15, 'Coal1': 12, 'Nuc1': 10, 'Solar': 0})
model.FP = Param(model.IDX_g, initialize={'CC1': 4, 'CC2': 4, 'CC3': 4, 'CT1': 4, 'Coal1': 3, 'Nuc1': 1, 'Solar': 0})
model.VOM = Param(model.IDX_g, initialize={'CC1': 5, 'CC2': 5, 'CC3': 5, 'CT1': 10, 'Coal1': 10, 'Nuc1': 5, 'Solar': 0})

# Initialize demand parameter
model.D = Param(model.IDX_t, initialize=D['Demand(MWh)'].to_dict(), within=NonNegativeReals)

# Variables
model.P = Var(model.IDX_g, model.IDX_t, within=NonNegativeReals)

# Objective function 
def objFunc(model):
    return sum(model.P[g, t] * (model.HR[g] * model.FP[g] + model.VOM[g]) for g in model.IDX_g for t in model.IDX_t)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
# Demand constraint: total generation must meet the demand
def demand_constraint(model, t):
    return sum(model.P[g, t] for g in model.IDX_g) >= model.D[t]
model.demandcon = Constraint(model.IDX_t, rule=demand_constraint)

# Capacity constraint: generation must not exceed capacity
def capacity_constraint(model, g, t):
    return model.P[g, t] <= model.max_capacity[g]
model.capacitycon = Constraint(model.IDX_g, model.IDX_t, rule=capacity_constraint)

# Capacity factor constraint for the solar generator
def solar_capacity_constraint(model, t):
    return model.P['Solar', t] <= model.max_capacity['Solar'] * S.loc[t, 'CF']
model.solar_capacitycon = Constraint(model.IDX_t, rule=solar_capacity_constraint)

# Solve
solver = SolverFactory('glpk')
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print results
model.pprint()


# In[3]:


#2b
import matplotlib.pyplot as plt
import pandas as pd

# Extract the dispatch data for each generator and time period
dispatch = pd.DataFrame({g: [model.P[g, t].value for t in model.IDX_t] for g in model.IDX_g}, index=D.index)

# Plot the economic dispatch using a stacked bar chart
dispatch.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Economic Dispatch for the Day')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MW)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()


# In[36]:


#2c 100MW
from pyomo.environ import *
import matplotlib.pyplot as plt
import pandas as pd

# Load and process demand data
D = pd.read_csv('demand.csv', header=None, index_col=0, names=['Demand(MWh)'])
S = pd.read_csv('solarCfs.csv', header=None, names=['Time', 'CF'])  # Load solar capacity factors

# Map time indices in both datasets
index_map = {label: i+1 for i, label in enumerate(D.index)}
S.set_index('Time', inplace=True)  # Set the 'Time' column as the index

# Convert time indices to match
D.index = D.index.map(index_map)
S.index = S.index.map(index_map)  # Ensure matching indices

# Create model
model = ConcreteModel()

# Sets
model.IDX_g = Set(initialize=['CC1', 'CC2', 'CC3', 'CT1', 'Coal1', 'Nuc1', 'Solar'])
model.IDX_t = RangeSet(1, len(D))  # Ensure this range matches the integer indices

# Parameters
model.max_capacity = Param(model.IDX_g, initialize={'CC1': 150, 'CC2': 200, 'CC3': 250, 'CT1': 50, 'Coal1': 500, 'Nuc1': 500, 'Solar': 100})
model.HR = Param(model.IDX_g, initialize={'CC1': 7, 'CC2': 8, 'CC3': 9, 'CT1': 15, 'Coal1': 12, 'Nuc1': 10, 'Solar': 0})
model.FP = Param(model.IDX_g, initialize={'CC1': 4, 'CC2': 4, 'CC3': 4, 'CT1': 4, 'Coal1': 3, 'Nuc1': 1, 'Solar': 0})
model.VOM = Param(model.IDX_g, initialize={'CC1': 5, 'CC2': 5, 'CC3': 5, 'CT1': 10, 'Coal1': 10, 'Nuc1': 5, 'Solar': 0})

# CO2 Emissions (tons/MWh)
model.CO2_emissions = Param(model.IDX_g, initialize={'CC1': 0.05, 'CC2': 0.05, 'CC3': 0.05, 'CT1': 0.05, 'Coal1': 0.1, 'Nuc1': 0.0,'Solar':0.0})

# CO2 Price
CO2_price = 25 #$/ton

# Initialize demand parameter
model.D = Param(model.IDX_t, initialize=D['Demand(MWh)'].to_dict(), within=NonNegativeReals)

# Variables
model.P = Var(model.IDX_g, model.IDX_t, within=NonNegativeReals)

# Objective function with CO2 price
def objFunc_CO2(model):
    return sum(model.P[g, t] * (model.HR[g] * model.FP[g] + model.VOM[g]) for g in model.IDX_g for t in model.IDX_t) \
           + CO2_price * sum(model.P[g, t] * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
model.cost = Objective(rule=objFunc_CO2, sense=minimize)

# Constraints
# Demand constraint: total generation must meet the demand
def demand_constraint(model, t):
    return sum(model.P[g, t] for g in model.IDX_g) >= model.D[t]
model.demandcon = Constraint(model.IDX_t, rule=demand_constraint)

# Capacity constraint: generation must not exceed capacity
def capacity_constraint(model, g, t):
    return model.P[g, t] <= model.max_capacity[g]
model.capacitycon = Constraint(model.IDX_g, model.IDX_t, rule=capacity_constraint)

# Capacity factor constraint for the solar generator
def solar_capacity_constraint(model, t):
    return model.P['Solar', t] <= model.max_capacity['Solar'] * S.loc[t, 'CF']
model.solar_capacitycon = Constraint(model.IDX_t, rule=solar_capacity_constraint)

# Solve
solver = SolverFactory('glpk')
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print results
model.pprint()

# Extract the dispatch data for each generator and time period
dispatch = pd.DataFrame({g: [model.P[g, t].value for t in model.IDX_t] for g in model.IDX_g}, index=D.index)

# Plot the economic dispatch using a stacked bar chart
dispatch.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Economic Dispatch for the Day with CO2 Pricing')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MW)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Check if the solver ran correctly and if duals are available
if (results.solver.status == 'ok') and (results.solver.termination_condition == 'optimal'):
    print(f"Total Cost with CO2 Pricing: ${model.cost():.2f}")
    
    # Retrieve and print MCP values
    mcp_values = []
    for t in model.IDX_t:
        if model.dual.get(model.demandcon[t], None) is not None:
            mcp_values.append(model.dual[model.demandcon[t]])
        else:
            mcp_values.append(None)
            print(f"Hour {t}: No dual value available")
    
    # Print MCP values for each hour
    print("Electricity prices (MCP) for each time period:")
    for t, mcp in zip(model.IDX_t, mcp_values):
        print(f"Hour {t}: {mcp:.2f} $/MWh" if mcp is not None else f"Hour {t}: No dual value available")
    
    
    # Calculate daily ratepayers
    ratepayers = sum(model.P[g, t].value * mcp_values[t-1] for g in model.IDX_g for t in model.IDX_t if mcp_values[t-1] is not None)
    
    # Calculate total CO2 emissions
    total_CO2_emissions = sum(model.P[g, t].value * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
    
    print(f"Ratepayers: ${ratepayers:.2f}")
    print(f"Total CO2 Emissions: {total_CO2_emissions:.2f} tons")
    
else:
    print("Solver did not find an optimal solution.")


# In[4]:


#2c 500 MW
from pyomo.environ import *
import matplotlib.pyplot as plt
import pandas as pd

# Load and process demand data
D = pd.read_csv('demand.csv', header=None, index_col=0, names=['Demand(MWh)'])
S = pd.read_csv('solarCfs.csv', header=None, names=['Time', 'CF'])  # Load solar capacity factors

# Map time indices in both datasets
index_map = {label: i+1 for i, label in enumerate(D.index)}
S.set_index('Time', inplace=True)  # Set the 'Time' column as the index

# Convert time indices to match
D.index = D.index.map(index_map)
S.index = S.index.map(index_map)  # Ensure matching indices

# Create model
model = ConcreteModel()

# Sets
model.IDX_g = Set(initialize=['CC1', 'CC2', 'CC3', 'CT1', 'Coal1', 'Nuc1', 'Solar'])
model.IDX_t = RangeSet(1, len(D))  # Ensure this range matches the integer indices

# Parameters
model.max_capacity = Param(model.IDX_g, initialize={'CC1': 150, 'CC2': 200, 'CC3': 250, 'CT1': 50, 'Coal1': 500, 'Nuc1': 500, 'Solar': 500})
model.HR = Param(model.IDX_g, initialize={'CC1': 7, 'CC2': 8, 'CC3': 9, 'CT1': 15, 'Coal1': 12, 'Nuc1': 10, 'Solar': 0})
model.FP = Param(model.IDX_g, initialize={'CC1': 4, 'CC2': 4, 'CC3': 4, 'CT1': 4, 'Coal1': 3, 'Nuc1': 1, 'Solar': 0})
model.VOM = Param(model.IDX_g, initialize={'CC1': 5, 'CC2': 5, 'CC3': 5, 'CT1': 10, 'Coal1': 10, 'Nuc1': 5, 'Solar': 0})

# CO2 Emissions (tons/MWh)
model.CO2_emissions = Param(model.IDX_g, initialize={'CC1': 0.05, 'CC2': 0.05, 'CC3': 0.05, 'CT1': 0.05, 'Coal1': 0.1, 'Nuc1': 0.0,'Solar':0.0})

# CO2 Price
CO2_price = 25 #$/ton

# Initialize demand parameter
model.D = Param(model.IDX_t, initialize=D['Demand(MWh)'].to_dict(), within=NonNegativeReals)

# Variables
model.P = Var(model.IDX_g, model.IDX_t, within=NonNegativeReals)

# Objective function with CO2 price
def objFunc_CO2(model):
    return sum(model.P[g, t] * (model.HR[g] * model.FP[g] + model.VOM[g]) for g in model.IDX_g for t in model.IDX_t) \
           + CO2_price * sum(model.P[g, t] * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
model.cost = Objective(rule=objFunc_CO2, sense=minimize)

# Constraints
# Demand constraint: total generation must meet the demand
def demand_constraint(model, t):
    return sum(model.P[g, t] for g in model.IDX_g) >= model.D[t]
model.demandcon = Constraint(model.IDX_t, rule=demand_constraint)

# Capacity constraint: generation must not exceed capacity
def capacity_constraint(model, g, t):
    return model.P[g, t] <= model.max_capacity[g]
model.capacitycon = Constraint(model.IDX_g, model.IDX_t, rule=capacity_constraint)

# Capacity factor constraint for the solar generator
def solar_capacity_constraint(model, t):
    return model.P['Solar', t] <= model.max_capacity['Solar'] * S.loc[t, 'CF']
model.solar_capacitycon = Constraint(model.IDX_t, rule=solar_capacity_constraint)

# Solve
solver = SolverFactory('glpk')
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print results
model.pprint()

# Extract the dispatch data for each generator and time period
dispatch = pd.DataFrame({g: [model.P[g, t].value for t in model.IDX_t] for g in model.IDX_g}, index=D.index)

# Plot the economic dispatch using a stacked bar chart
dispatch.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Economic Dispatch for the Day with CO2 Pricing')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MW)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Check if the solver ran correctly and if duals are available
if (results.solver.status == 'ok') and (results.solver.termination_condition == 'optimal'):
    print(f"Total Cost with CO2 Pricing: ${model.cost():.2f}")
    
    # Retrieve and print MCP values
    mcp_values = []
    for t in model.IDX_t:
        if model.dual.get(model.demandcon[t], None) is not None:
            mcp_values.append(model.dual[model.demandcon[t]])
        else:
            mcp_values.append(None)
            print(f"Hour {t}: No dual value available")
    
    # Print MCP values for each hour
    print("Electricity prices (MCP) for each time period:")
    for t, mcp in zip(model.IDX_t, mcp_values):
        print(f"Hour {t}: {mcp:.2f} $/MWh" if mcp is not None else f"Hour {t}: No dual value available")
    
    
    # Calculate daily ratepayers
    ratepayers = sum(model.P[g, t].value * mcp_values[t-1] for g in model.IDX_g for t in model.IDX_t if mcp_values[t-1] is not None)
    
    # Calculate total CO2 emissions
    total_CO2_emissions = sum(model.P[g, t].value * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
    
    print(f"Ratepayers: ${ratepayers:.2f}")
    print(f"Total CO2 Emissions: {total_CO2_emissions:.2f} tons")
    
else:
    print("Solver did not find an optimal solution.")


# In[38]:


#2c 1000 MW
from pyomo.environ import *
import matplotlib.pyplot as plt
import pandas as pd

# Load and process demand data
D = pd.read_csv('demand.csv', header=None, index_col=0, names=['Demand(MWh)'])
S = pd.read_csv('solarCfs.csv', header=None, names=['Time', 'CF'])  # Load solar capacity factors

# Map time indices in both datasets
index_map = {label: i+1 for i, label in enumerate(D.index)}
S.set_index('Time', inplace=True)  # Set the 'Time' column as the index

# Convert time indices to match
D.index = D.index.map(index_map)
S.index = S.index.map(index_map)  # Ensure matching indices

# Create model
model = ConcreteModel()

# Sets
model.IDX_g = Set(initialize=['CC1', 'CC2', 'CC3', 'CT1', 'Coal1', 'Nuc1', 'Solar'])
model.IDX_t = RangeSet(1, len(D))  # Ensure this range matches the integer indices

# Parameters
model.max_capacity = Param(model.IDX_g, initialize={'CC1': 150, 'CC2': 200, 'CC3': 250, 'CT1': 50, 'Coal1': 500, 'Nuc1': 500, 'Solar': 1000})
model.HR = Param(model.IDX_g, initialize={'CC1': 7, 'CC2': 8, 'CC3': 9, 'CT1': 15, 'Coal1': 12, 'Nuc1': 10, 'Solar': 0})
model.FP = Param(model.IDX_g, initialize={'CC1': 4, 'CC2': 4, 'CC3': 4, 'CT1': 4, 'Coal1': 3, 'Nuc1': 1, 'Solar': 0})
model.VOM = Param(model.IDX_g, initialize={'CC1': 5, 'CC2': 5, 'CC3': 5, 'CT1': 10, 'Coal1': 10, 'Nuc1': 5, 'Solar': 0})

# CO2 Emissions (tons/MWh)
model.CO2_emissions = Param(model.IDX_g, initialize={'CC1': 0.05, 'CC2': 0.05, 'CC3': 0.05, 'CT1': 0.05, 'Coal1': 0.1, 'Nuc1': 0.0,'Solar':0.0})

# CO2 Price
CO2_price = 25 #$/ton

# Initialize demand parameter
model.D = Param(model.IDX_t, initialize=D['Demand(MWh)'].to_dict(), within=NonNegativeReals)

# Variables
model.P = Var(model.IDX_g, model.IDX_t, within=NonNegativeReals)

# Objective function with CO2 price
def objFunc_CO2(model):
    return sum(model.P[g, t] * (model.HR[g] * model.FP[g] + model.VOM[g]) for g in model.IDX_g for t in model.IDX_t) \
           + CO2_price * sum(model.P[g, t] * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
model.cost = Objective(rule=objFunc_CO2, sense=minimize)

# Constraints
# Demand constraint: total generation must meet the demand
def demand_constraint(model, t):
    return sum(model.P[g, t] for g in model.IDX_g) >= model.D[t]
model.demandcon = Constraint(model.IDX_t, rule=demand_constraint)

# Capacity constraint: generation must not exceed capacity
def capacity_constraint(model, g, t):
    return model.P[g, t] <= model.max_capacity[g]
model.capacitycon = Constraint(model.IDX_g, model.IDX_t, rule=capacity_constraint)

# Capacity factor constraint for the solar generator
def solar_capacity_constraint(model, t):
    return model.P['Solar', t] <= model.max_capacity['Solar'] * S.loc[t, 'CF']
model.solar_capacitycon = Constraint(model.IDX_t, rule=solar_capacity_constraint)

# Solve
solver = SolverFactory('glpk')
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print results
model.pprint()

# Extract the dispatch data for each generator and time period
dispatch = pd.DataFrame({g: [model.P[g, t].value for t in model.IDX_t] for g in model.IDX_g}, index=D.index)

# Plot the economic dispatch using a stacked bar chart
dispatch.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Economic Dispatch for the Day with CO2 Pricing')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MW)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Check if the solver ran correctly and if duals are available
if (results.solver.status == 'ok') and (results.solver.termination_condition == 'optimal'):
    print(f"Total Cost with CO2 Pricing: ${model.cost():.2f}")
    
    # Retrieve and print MCP values
    mcp_values = []
    for t in model.IDX_t:
        if model.dual.get(model.demandcon[t], None) is not None:
            mcp_values.append(model.dual[model.demandcon[t]])
        else:
            mcp_values.append(None)
            print(f"Hour {t}: No dual value available")
    
    # Print MCP values for each hour
    print("Electricity prices (MCP) for each time period:")
    for t, mcp in zip(model.IDX_t, mcp_values):
        print(f"Hour {t}: {mcp:.2f} $/MWh" if mcp is not None else f"Hour {t}: No dual value available")
    
    
    # Calculate daily ratepayers
    ratepayers = sum(model.P[g, t].value * mcp_values[t-1] for g in model.IDX_g for t in model.IDX_t if mcp_values[t-1] is not None)
    
    # Calculate total CO2 emissions
    total_CO2_emissions = sum(model.P[g, t].value * model.CO2_emissions[g]*model.HR[g] for g in model.IDX_g for t in model.IDX_t)
    
    print(f"Ratepayers: ${ratepayers:.2f}")
    print(f"Total CO2 Emissions: {total_CO2_emissions:.2f} tons")
    
else:
    print("Solver did not find an optimal solution.")

