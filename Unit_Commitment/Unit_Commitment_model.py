#!/usr/bin/env python
# coding: utf-8

# In[6]:


from pyomo.environ import *
import pandas as pd

#Import demand
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

fleet['Startup Costs ($/startup)'] = pd.to_numeric(fleet['Startup Costs ($/startup)'].str.replace(',', '')) #UPDATE

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) #manual entry: ['cc1','cc2','cc3','ct1','coal1','nuc1']

# Ensure time indices are integers
demand.index = range(1, len(demand) + 1)  # Create a range of integers from 1 to len(demand)
model.times = Set(initialize=demand.index.values)

# Parameters
# Via pandas CSV import
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pDemand = Param(model.times,initialize=demand.to_dict())
model.pSCs = Param(model.generators,initialize=fleet['Startup Costs ($/startup)'].to_dict())#UPDATE start up costs in $/startup
model.pRRs = Param(model.generators,initialize=fleet['Ramp Rate (MW/hr)'].to_dict())#UPDATE ramp rates in MW/hr
model.pLds = Param(model.generators,initialize=fleet['Minimum Stable Load (MW)'].to_dict())#UPDATE minimum stable loads in MW
model.vu_initial = Param(model.generators, initialize=0)#UPDATE

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vu = Var(model.generators, model.times, within=Binary)# UPDATE (ON/OFF)
model.vv = Var(model.generators, model.times, within=Binary)#UPDATE (ON)
model.vw = Var(model.generators, model.times, within=Binary)#UPDATE (OFF)

# Objective function
def objFunc(model):#UPDATE
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t]
               +model.pSCs[gen]*model.vv[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t): #UPDATE
    return model.vPower[gen,t] <= model.pCaps[gen]*model.vu[gen,t]
model.maxcap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model, gen, t): #UPDATE
    return model.pLds[gen]*model.vu[gen,t]<= model.vPower[gen,t]
model.mincap = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genCommitment(model, gen, t): #UPDATE
    if t == model.times.first():  
        return model.vu[gen, t] == model.vu_initial[gen] + model.vv[gen, t] - model.vw[gen, t]
    else:
        return model.vu[gen,t] == model.vu[gen,t-1] + model.vv[gen,t] - model.vw[gen,t]
model.com = Constraint(model.generators, model.times, rule=genCommitment)

# Solve the model
solver = SolverFactory('glpk')  
results = solver.solve(model)

# Print model
model.pprint()

# Display results
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    print(f"Total Cost: ${model.cost():.2f}")

    print('Generation decisions:')
    for gen in model.generators:
        for t in model.times:
            print(f"{gen}, {t}: {model.vPower[gen, t].value:.2f} MWh")
            # Safeguard binary variable outputs in case they return None
            vv_value = model.vv[gen, t].value
            vu_value = model.vu[gen, t].value 
            vw_value = model.vw[gen, t].value
            print(f"{gen}, {t} ON: {vv_value:.2f}")
            print(f"{gen}, {t} Running: {vu_value:.2f}")
            print(f"{gen}, {t} OFF: {vw_value:.2f}")


# In[7]:


import matplotlib.pyplot as plt

# Convert generation decisions to a pandas DataFrame for easier plotting
generation_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        generation_data.at[t, gen] = model.vPower[gen, t].value

# Convert all values to float (in case they are None or other types)
generation_data = generation_data.astype(float)

# Plot the stacked bar chart
generation_data.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Unit Commitment for the day')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MWh)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Convert commitment decisions to a pandas DataFrame
commitment_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        commitment_data.at[t, gen] = model.vu[gen, t].value

# Display the commitment decisions table
print("Commitment Decisions (1 = On, 0 = Off):")
print(commitment_data)


# In[10]:


#d
from pyomo.environ import *
import pandas as pd

#Import demand
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

fleet['Startup Costs ($/startup)'] = pd.to_numeric(fleet['Startup Costs ($/startup)'].str.replace(',', '')) #UPDATE

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) #manual entry: ['cc1','cc2','cc3','ct1','coal1','nuc1']

# Ensure time indices are integers
demand.index = range(1, len(demand) + 1)  # Create a range of integers from 1 to len(demand)
model.times = Set(initialize=demand.index.values)

# Parameters
# Via pandas CSV import
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pDemand = Param(model.times,initialize=demand.to_dict())
model.pSCs = Param(model.generators,initialize=fleet['Startup Costs ($/startup)'].to_dict())#UPDATE start up costs in $/startup
model.pRRs = Param(model.generators,initialize=fleet['Ramp Rate (MW/hr)'].to_dict())#UPDATE ramp rates in MW/hr
model.pLds = Param(model.generators,initialize=fleet['Minimum Stable Load (MW)'].to_dict())#UPDATE minimum stable loads in MW
model.pSU = Param(model.generators, initialize={gen: 1.1 * model.pLds[gen] for gen in model.generators})#UPDATE#UPDATE
model.pSD = Param(model.generators, initialize={gen: 1.1 * model.pLds[gen] for gen in model.generators})#UPDATE#UPDATE
model.vu_initial = Param(model.generators, initialize=0)#UPDATE

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vu = Var(model.generators, model.times, within=Binary)# UPDATE (ON/OFF)
model.vv = Var(model.generators, model.times, within=Binary)#UPDATE (ON)
model.vw = Var(model.generators, model.times, within=Binary)#UPDATE (OFF)
model.vq = Var(model.generators,model.times, within=NonNegativeReals) #UPDATE#UPDATE

# Objective function
def objFunc(model):#UPDATE
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t]
               +model.pSCs[gen]*model.vv[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t): #UPDATE
    return model.vPower[gen,t] <= model.pCaps[gen]*model.vu[gen,t]
model.maxcap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model, gen, t): #UPDATE
    return model.pLds[gen]*model.vu[gen,t]<= model.vPower[gen,t]
model.mincap = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genCommitment(model, gen, t): #UPDATE
    if t == model.times.first():
        return model.vu[gen, t] == model.vu_initial[gen] + model.vv[gen, t] - model.vw[gen, t]
    else:
        return model.vu[gen,t] == model.vu[gen,t-1] + model.vv[gen,t] - model.vw[gen,t]
model.com = Constraint(model.generators, model.times, rule=genCommitment)

def genRR1(model, gen, t): #UPDATE#UPDATE
    return model.vPower[gen,t] == model.pLds[gen]*model.vu[gen,t] + model.vq[gen,t]
model.RR1 = Constraint(model.generators, model.times, rule=genRR1)

def genRR2(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():  # Skip the first time step to avoid t-1
        return Constraint.Skip
     else:
        return model.vq[gen,t]- model.vq[gen,t-1] <= model.pRRs[gen]
model.RR2 = Constraint(model.generators, model.times, rule=genRR2)

def genRR3(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():  # Skip the first time step to avoid t-1
        return Constraint.Skip
     else:
        return model.vq[gen,t-1]- model.vq[gen,t] <= model.pRRs[gen]
model.RR3 = Constraint(model.generators, model.times, rule=genRR3)

def genRR4(model, gen, t): #UPDATE#UPDATE
    return model.vq[gen,t]<= (model.pCaps[gen]-model.pLds[gen])*model.vu[gen,t]-(model.pCaps[gen]-model.pSU[gen])*model.vv[gen,t]
model.RR4 = Constraint(model.generators, model.times, rule=genRR4)

def genRR5(model, gen, t): #UPDATE#UPDATE
    if t == model.times.last():  # Skip the last time step to avoid t+1
        return Constraint.Skip
    else:
        return model.vq[gen,t]<= (model.pCaps[gen]-model.pLds[gen])*model.vu[gen,t]-(model.pCaps[gen]-model.pSD[gen])*model.vw[gen,t+1]
model.RR5 = Constraint(model.generators, model.times, rule=genRR5)

# Solve the model
solver = SolverFactory('glpk')  
results = solver.solve(model)

# Print model
model.pprint()

# Display results
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    print(f"Total Cost: ${model.cost():.2f}")

    print('Generation decisions:')
    for gen in model.generators:
        for t in model.times:
            print(f"{gen}, {t}: {model.vPower[gen, t].value:.2f} MWh")
            # Safeguard binary variable outputs in case they return None
            vv_value = model.vv[gen, t].value
            vu_value = model.vu[gen, t].value 
            vw_value = model.vw[gen, t].value
            print(f"{gen}, {t} ON: {vv_value:.2f}")
            print(f"{gen}, {t} Running: {vu_value:.2f}")
            print(f"{gen}, {t} OFF: {vw_value:.2f}")


# In[9]:


import matplotlib.pyplot as plt

# Convert generation decisions to a pandas DataFrame for easier plotting
generation_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        generation_data.at[t, gen] = model.vPower[gen, t].value

# Convert all values to float (in case they are None or other types)
generation_data = generation_data.astype(float)

# Plot the stacked bar chart
generation_data.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Unit Commitment for the day with RR')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MWh)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Convert commitment decisions to a pandas DataFrame
commitment_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        commitment_data.at[t, gen] = model.vu[gen, t].value

# Display the commitment decisions table
print("Commitment Decisions (1 = On, 0 = Off):")
print(commitment_data)


# In[24]:


#f1 (50% increase in MSL of CC3)
from pyomo.environ import *
import pandas as pd
import matplotlib.pyplot as plt

#Import demand
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
fleet = pd.read_csv('GeneratorFleet_f1.csv',header=0,index_col=0)

fleet['Startup Costs ($/startup)'] = pd.to_numeric(fleet['Startup Costs ($/startup)'].str.replace(',', '')) #UPDATE

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) #manual entry: ['cc1','cc2','cc3','ct1','coal1','nuc1']

# Ensure time indices are integers
demand.index = range(1, len(demand) + 1)  # Create a range of integers from 1 to len(demand)
model.times = Set(initialize=demand.index.values)

# Parameters
# Via pandas CSV import
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pDemand = Param(model.times,initialize=demand.to_dict())
model.pSCs = Param(model.generators,initialize=fleet['Startup Costs ($/startup)'].to_dict())#UPDATE start up costs in $/startup
model.pRRs = Param(model.generators,initialize=fleet['Ramp Rate (MW/hr)'].to_dict())#UPDATE ramp rates in MW/hr
model.pLds = Param(model.generators,initialize=fleet['Minimum Stable Load (MW)'].to_dict())#UPDATE minimum stable loads in MW
model.pSU = Param(model.generators, initialize={gen: 1.1 * model.pLds[gen] for gen in model.generators})#UPDATE#UPDATE
model.pSD = Param(model.generators, initialize={gen: 1.1 * model.pLds[gen] for gen in model.generators})#UPDATE#UPDATE
model.vu_initial = Param(model.generators, initialize=0)#UPDATE

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vu = Var(model.generators, model.times, within=Binary)# UPDATE (ON/OFF)
model.vv = Var(model.generators, model.times, within=Binary)#UPDATE (ON)
model.vw = Var(model.generators, model.times, within=Binary)#UPDATE (OFF)
model.vq = Var(model.generators,model.times, within=NonNegativeReals) #UPDATE#UPDATE

# Objective function
def objFunc(model):#UPDATE
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t]+model.pSCs[gen]*model.vv[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t): #UPDATE
    return model.vPower[gen,t] <= model.pCaps[gen]*model.vu[gen,t]
model.maxcap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model, gen, t): #UPDATE
    return model.pLds[gen]*model.vu[gen,t]<= model.vPower[gen,t]
model.mincap = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genCommitment(model, gen, t): #UPDATE
    if t == model.times.first():
        return model.vu[gen, t] == model.vu_initial[gen] + model.vv[gen, t] - model.vw[gen, t]
    else:
        return model.vu[gen,t] == model.vu[gen,t-1] + model.vv[gen,t] - model.vw[gen,t]
model.com = Constraint(model.generators, model.times, rule=genCommitment)

def genRR1(model, gen, t): #UPDATE#UPDATE
    return model.vPower[gen,t] == model.pLds[gen]*model.vu[gen,t] + model.vq[gen,t]
model.RR1 = Constraint(model.generators, model.times, rule=genRR1)

def genRR2(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():  # Skip the first time step to avoid t-1
        return Constraint.Skip
     else:
        return model.vq[gen,t]- model.vq[gen,t-1] <= model.pRRs[gen]
model.RR2 = Constraint(model.generators, model.times, rule=genRR2)

def genRR3(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():  # Skip the first time step to avoid t-1
        return Constraint.Skip
     else:
        return model.vq[gen,t-1]- model.vq[gen,t] <= model.pRRs[gen]
model.RR3 = Constraint(model.generators, model.times, rule=genRR3)

def genRR4(model, gen, t): #UPDATE#UPDATE
    return model.vq[gen,t]<= (model.pCaps[gen]-model.pLds[gen])*model.vu[gen,t]-(model.pCaps[gen]-model.pSU[gen])*model.vv[gen,t]
model.RR4 = Constraint(model.generators, model.times, rule=genRR4)

def genRR5(model, gen, t): #UPDATE#UPDATE
    if t == model.times.last():  # Skip the last time step to avoid t+1
        return Constraint.Skip
    else:
        return model.vq[gen,t]<= (model.pCaps[gen]-model.pLds[gen])*model.vu[gen,t]-(model.pCaps[gen]-model.pSD[gen])*model.vw[gen,t+1]
model.RR5 = Constraint(model.generators, model.times, rule=genRR5)

# Solve the model
solver = SolverFactory('glpk')  
#model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    print(f"Total Cost: ${model.cost():.2f}")

# Convert generation decisions to a pandas DataFrame for easier plotting
generation_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        generation_data.at[t, gen] = model.vPower[gen, t].value

# Convert all values to float (in case they are None or other types)
generation_data = generation_data.astype(float)

# Plot the stacked bar chart
generation_data.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Unit Commitment for the day with RR')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MWh)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Convert commitment decisions to a pandas DataFrame
commitment_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        commitment_data.at[t, gen] = model.vu[gen, t].value

# Display the commitment decisions table
print("Commitment Decisions (1 = On, 0 = Off):")
print(commitment_data)


# In[26]:


#f2 (100% decrease in RR of Coal1)
from pyomo.environ import *
import pandas as pd
import matplotlib.pyplot as plt

#Import demand
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
fleet = pd.read_csv('GeneratorFleet_f2.csv',header=0,index_col=0)

fleet['Startup Costs ($/startup)'] = pd.to_numeric(fleet['Startup Costs ($/startup)'].str.replace(',', '')) #UPDATE

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) #manual entry: ['cc1','cc2','cc3','ct1','coal1','nuc1']

# Ensure time indices are integers
demand.index = range(1, len(demand) + 1)  # Create a range of integers from 1 to len(demand)
model.times = Set(initialize=demand.index.values)

# Parameters
# Via pandas CSV import
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pDemand = Param(model.times,initialize=demand.to_dict())
model.pSCs = Param(model.generators,initialize=fleet['Startup Costs ($/startup)'].to_dict())#UPDATE start up costs in $/startup
model.pRRs = Param(model.generators,initialize=fleet['Ramp Rate (MW/hr)'].to_dict())#UPDATE ramp rates in MW/hr
model.pLds = Param(model.generators,initialize=fleet['Minimum Stable Load (MW)'].to_dict())#UPDATE minimum stable loads in MW
model.pSU = Param(model.generators, initialize={gen: 1.1 * model.pLds[gen] for gen in model.generators})#UPDATE#UPDATE
model.pSD = Param(model.generators, initialize={gen: 1.1 * model.pLds[gen] for gen in model.generators})#UPDATE#UPDATE
model.vu_initial = Param(model.generators, initialize=0)#UPDATE

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vu = Var(model.generators, model.times, within=Binary)# UPDATE (ON/OFF)
model.vv = Var(model.generators, model.times, within=Binary)#UPDATE (ON)
model.vw = Var(model.generators, model.times, within=Binary)#UPDATE (OFF)
model.vq = Var(model.generators,model.times, within=NonNegativeReals) #UPDATE#UPDATE

# Objective function
def objFunc(model):#UPDATE
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t]+model.pSCs[gen]*model.vv[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t): #UPDATE
    return model.vPower[gen,t] <= model.pCaps[gen]*model.vu[gen,t]
model.maxcap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model, gen, t): #UPDATE
    return model.pLds[gen]*model.vu[gen,t]<= model.vPower[gen,t]
model.mincap = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genCommitment(model, gen, t): #UPDATE
    if t == model.times.first():
        return model.vu[gen, t] == model.vu_initial[gen] + model.vv[gen, t] - model.vw[gen, t]
    else:
        return model.vu[gen,t] == model.vu[gen,t-1] + model.vv[gen,t] - model.vw[gen,t]
model.com = Constraint(model.generators, model.times, rule=genCommitment)

def genRR1(model, gen, t): #UPDATE#UPDATE
    return model.vPower[gen,t] == model.pLds[gen]*model.vu[gen,t] + model.vq[gen,t]
model.RR1 = Constraint(model.generators, model.times, rule=genRR1)

def genRR2(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():  # Skip the first time step to avoid t-1
        return Constraint.Skip
     else:
        return model.vq[gen,t]- model.vq[gen,t-1] <= model.pRRs[gen]
model.RR2 = Constraint(model.generators, model.times, rule=genRR2)

def genRR3(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():  # Skip the first time step to avoid t-1
        return Constraint.Skip
     else:
        return model.vq[gen,t-1]- model.vq[gen,t] <= model.pRRs[gen]
model.RR3 = Constraint(model.generators, model.times, rule=genRR3)

def genRR4(model, gen, t): #UPDATE#UPDATE
    return model.vq[gen,t]<= (model.pCaps[gen]-model.pLds[gen])*model.vu[gen,t]-(model.pCaps[gen]-model.pSU[gen])*model.vv[gen,t]
model.RR4 = Constraint(model.generators, model.times, rule=genRR4)

def genRR5(model, gen, t): #UPDATE#UPDATE
    if t == model.times.last():  # Skip the last time step to avoid t+1
        return Constraint.Skip
    else:
        return model.vq[gen,t]<= (model.pCaps[gen]-model.pLds[gen])*model.vu[gen,t]-(model.pCaps[gen]-model.pSD[gen])*model.vw[gen,t+1]
model.RR5 = Constraint(model.generators, model.times, rule=genRR5)

# Solve the model
solver = SolverFactory('glpk')  
#model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    print(f"Total Cost: ${model.cost():.2f}")

# Convert generation decisions to a pandas DataFrame for easier plotting
generation_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        generation_data.at[t, gen] = model.vPower[gen, t].value

# Convert all values to float (in case they are None or other types)
generation_data = generation_data.astype(float)

# Plot the stacked bar chart
generation_data.plot(kind='bar', stacked=True, figsize=(12, 8), colormap='tab20')
plt.title('Unit Commitment for the day with RR')
plt.xlabel('Time (Hour)')
plt.ylabel('Power Generation (MWh)')
plt.legend(title='Generators', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, axis='y')
plt.tight_layout()
plt.show()

# Convert commitment decisions to a pandas DataFrame
commitment_data = pd.DataFrame(index=model.times, columns=model.generators)

for gen in model.generators:
    for t in model.times:
        commitment_data.at[t, gen] = model.vu[gen, t].value

# Display the commitment decisions table
print("Commitment Decisions (1 = On, 0 = Off):")
print(commitment_data)


# In[ ]:




