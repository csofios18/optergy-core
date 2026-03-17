#!/usr/bin/env python
# coding: utf-8

# In[64]:


from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

prices = pd.read_csv('Prices.csv',header=0,index_col=0)
prices.index = list(range(1,len(prices.index.values)+1))

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

storage = pd.read_csv('StorageUnit.csv',header=0,index_col=0) 
fleet = pd.concat([fleet,storage]) 

cfs = pd.read_csv('CFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],prices.index.values]) 

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=prices.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.storageunits =Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Storage'].index.values)

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pMCRs= Param(model.storageunits,initialize=storage['Maximum Capacity (MW)'].to_dict()) 
model.pUXs= Param(model.storageunits,initialize=storage['Maximum Energy Capacity (MWh)'].to_dict()) 
model.pe= Param(model.storageunits,initialize=storage['RTE'].to_dict())
model.pISOC=Param(model.storageunits,initialize=storage['Initial SOC (MWh)'].to_dict())
model.pPrices=Param(model.times,initialize=prices['Electricity Price ($/MWh)'].to_dict())

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vCR = Var(model.storageunits, model.times, within=NonNegativeReals) 
model.vX = Var(model.storageunits, model.times, within=NonNegativeReals) 

# Objective function
def objFunc(model):
    return sum(model.vPower[stu,t]*(model.pPrices[t]-(model.pHRs[stu] * model.pFCs[stu] + model.pVOMs[stu]))
               -model.vCR[stu,t]*(model.pPrices[t]+(model.pHRs[stu] * model.pFCs[stu] + model.pVOMs[stu]))
                for stu in model.storageunits for t in model.times)  
model.revenues = Objective(rule=objFunc, sense=maximize)

# Constraints
def genMaxCapConstraint(model, stu, t):
    return model.vPower[stu,t] <= model.pCaps[stu]
model.cap1 = Constraint(model.storageunits,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model,stu, t):#UPDATE
    return model.vPower[stu,t] >= 0
model.cap2 = Constraint(model.storageunits,model.times,rule=genMinCapConstraint)

def genMaxCRConstraint(model, stu, t):
    return model.vCR[stu,t] <= model.pMCRs[stu]
model.CR1 = Constraint(model.storageunits,model.times,rule=genMaxCRConstraint)

def genMinCRConstraint(model,stu, t):
    return model.vCR[stu,t] >= 0
model.CR2 = Constraint(model.storageunits,model.times,rule=genMinCRConstraint)

def genMaxXConstraint(model, stu, t):
    return model.vX[stu,t] <= model.pUXs[stu]
model.X1 = Constraint(model.storageunits,model.times,rule=genMaxXConstraint)

def genMinXConstraint(model,stu, t):
    return model.vX[stu,t] >= 0
model.X2 = Constraint(model.storageunits,model.times,rule=genMinXConstraint)

def genStorageConstraint(model,stu, t):
    if t == model.times.first():  
        return model.vX[stu,t] == model.pISOC[stu]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
    else:
        return model.vX[stu,t] == model.vX[stu,t-1]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
model.Stor = Constraint(model.storageunits,model.times,rule=genStorageConstraint)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Calculate total charging and discharging
total_charging = sum(model.vCR[stu, t].value for stu in model.storageunits for t in model.times)
total_discharging = sum(model.vPower[stu, t].value for stu in model.storageunits for t in model.times)

if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total Revenues: ${model.revenues():.2f}")
    print(f"Total Charging: {total_charging:.2f} MWh")
    print(f"Total Discharging: {total_discharging:.2f} MWh")
    
else:
    print("Solver did not find an optimal solution.")


# In[65]:


# Initialize DataFrames to store results
charging = pd.DataFrame(index=prices.index.values, columns=storage.index.values)
discharging = pd.DataFrame(index=prices.index.values, columns=storage.index.values)
soc = pd.DataFrame(index=prices.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging.loc[t, s] = model.vCR[s, t].value  # Charging values
            discharging.loc[t, s] = model.vPower[s, t].value  # Discharging values
            soc.loc[t, s] = model.vX[s, t].value  # State of charge values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile with bar plot for charging and discharging
plt.figure(figsize=(12, 6))

# Bar plots for charging and discharging for each storage unit
for s in storage.index:
    plt.bar(charging.index, charging[s], label=f'{s} Charging', color='blue', alpha=0.5)
    plt.bar(discharging.index, -discharging[s], label=f'{s} Discharging', color='red', alpha=0.5)

# Line plot for state of charge (SOC)
for s in storage.index:
    plt.bar(soc.index, soc[s], label=f'{s} SOC', color='green', alpha=0.25)

# Labels and formatting
plt.title('Storage Facility Operations')
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend(loc='upper left')
plt.grid(True)
plt.savefig('StorageOperations.png')
plt.show()


# In[56]:


# Initialize DataFrames to store results
charging = pd.DataFrame(index=prices.index.values, columns=storage.index.values)
discharging = pd.DataFrame(index=prices.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging.loc[t, s] = model.vCR[s, t].value  # Charging values
            discharging.loc[t, s] = model.vPower[s, t].value  # Discharging values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile with bar plot for charging and discharging
plt.figure(figsize=(12, 6))

# Bar plots for charging and discharging for each storage unit
for s in storage.index:
    plt.bar(charging.index, charging[s], label=f'{s} Charging', color='blue', alpha=0.5)
    plt.bar(discharging.index, -discharging[s], label=f'{s} Discharging', color='blue', alpha=0.5)

# Labels and formatting
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend(loc='upper left')
plt.grid(True)
plt.show()


# In[2]:


#1c (efficiency_increase)
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

prices = pd.read_csv('Prices.csv',header=0,index_col=0)
prices.index = list(range(1,len(prices.index.values)+1))

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

storage = pd.read_csv('StorageUnit.csv',header=0,index_col=0) 
fleet = pd.concat([fleet,storage]) 

cfs = pd.read_csv('CFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],prices.index.values]) 

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=prices.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.storageunits =Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Storage'].index.values)

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pMCRs= Param(model.storageunits,initialize=storage['Maximum Capacity (MW)'].to_dict()) 
model.pUXs= Param(model.storageunits,initialize=storage['Maximum Energy Capacity (MWh)'].to_dict()) 
model.pe= Param(model.storageunits,initialize=storage['RTE'].to_dict())
model.pISOC=Param(model.storageunits,initialize=storage['Initial SOC (MWh)'].to_dict())
model.pPrices=Param(model.times,initialize=prices['Electricity Price ($/MWh)'].to_dict())

# Variables
model.vPower_eff = Var(model.generators, model.times, within=NonNegativeReals)
model.vCR_eff = Var(model.storageunits, model.times, within=NonNegativeReals) 
model.vX_eff = Var(model.storageunits, model.times, within=NonNegativeReals) 

# Objective function
def objFunc(model):
    return sum(model.vPower_eff[stu,t]*(model.pPrices[t]-(model.pHRs[stu] * model.pFCs[stu] + model.pVOMs[stu]))
               -model.vCR_eff[stu,t]*(model.pPrices[t]+(model.pHRs[stu] * model.pFCs[stu] + model.pVOMs[stu]))
                for stu in model.storageunits for t in model.times)  
model.revenues_eff = Objective(rule=objFunc, sense=maximize)

# Constraints

def genMaxCapConstraint(model, stu, t):
    return model.vPower_eff[stu,t] <= model.pCaps[stu]
model.cap1 = Constraint(model.storageunits,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model,stu, t):#UPDATE
    return model.vPower_eff[stu,t] >= 0
model.cap2 = Constraint(model.storageunits,model.times,rule=genMinCapConstraint)

def genMaxCRConstraint(model, stu, t):
    return model.vCR_eff[stu,t] <= model.pMCRs[stu]
model.CR1 = Constraint(model.storageunits,model.times,rule=genMaxCRConstraint)

def genMinCRConstraint(model,stu, t):
    return model.vCR_eff[stu,t] >= 0
model.CR2 = Constraint(model.storageunits,model.times,rule=genMinCRConstraint)

def genMaxXConstraint(model, stu, t):
    return model.vX_eff[stu,t] <= model.pUXs[stu]
model.X1 = Constraint(model.storageunits,model.times,rule=genMaxXConstraint)

def genMinXConstraint(model,stu, t):
    return model.vX_eff[stu,t] >= 0
model.X2 = Constraint(model.storageunits,model.times,rule=genMinXConstraint)

def genStorageConstraint(model,stu, t):
    if t == model.times.first():  
        return model.vX_eff[stu,t] == model.pISOC[stu]- (model.vPower_eff[stu,t]/((model.pe[stu]*1.1)**0.5))+ (model.vCR_eff[stu,t]*((model.pe[stu]*1.1)**0.5))
    else:
        return model.vX_eff[stu,t] == model.vX_eff[stu,t-1]- (model.vPower_eff[stu,t]/((model.pe[stu]*1.1)**0.5))+ (model.vCR_eff[stu,t]*((model.pe[stu]*1.1)**0.5))
model.Stor = Constraint(model.storageunits,model.times,rule=genStorageConstraint)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Calculate total charging and discharging
total_charging_eff = sum(model.vCR_eff[stu, t].value for stu in model.storageunits for t in model.times)
total_discharging_eff = sum(model.vPower_eff[stu, t].value for stu in model.storageunits for t in model.times)

if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total Revenues_eff: ${model.revenues_eff():.2f}")
    print(f"Total Charging_eff: {total_charging_eff:.2f} MWh")
    print(f"Total Discharging_eff: {total_discharging_eff:.2f} MWh")

else:
    print("Solver did not find an optimal solution.")


# In[59]:


# Initialize DataFrames to store results
charging_eff = pd.DataFrame(index=prices.index.values, columns=storage.index.values)
discharging_eff = pd.DataFrame(index=prices.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging_eff.loc[t, s] = model.vCR_eff[s, t].value  # Charging values
            discharging_eff.loc[t, s] = model.vPower_eff[s, t].value  # Discharging values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile with bar plot for charging and discharging
plt.figure(figsize=(12, 6))

# Bar plots for charging and discharging for each storage unit
for s in storage.index:
    plt.bar(charging_eff.index, charging_eff[s], label=f'{s} Charging_eff', color='red', alpha=0.5)
    plt.bar(discharging_eff.index, -discharging_eff[s], label=f'{s} Discharging_eff', color='red', alpha=0.5)

# Labels and formatting
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend(loc='upper left')
plt.grid(True)
plt.show()


# In[60]:


#1c (maxenergycap_increase)
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

prices = pd.read_csv('Prices.csv',header=0,index_col=0)
prices.index = list(range(1,len(prices.index.values)+1))

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

storage = pd.read_csv('StorageUnit.csv',header=0,index_col=0) 
fleet = pd.concat([fleet,storage]) 

cfs = pd.read_csv('CFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],prices.index.values]) 

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=prices.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.storageunits =Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Storage'].index.values)

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pMCRs= Param(model.storageunits,initialize=storage['Maximum Capacity (MW)'].to_dict()) 
model.pUXs= Param(model.storageunits,initialize=storage['Maximum Energy Capacity (MWh)'].to_dict()) 
model.pe= Param(model.storageunits,initialize=storage['RTE'].to_dict())
model.pISOC=Param(model.storageunits,initialize=storage['Initial SOC (MWh)'].to_dict())
model.pPrices=Param(model.times,initialize=prices['Electricity Price ($/MWh)'].to_dict())

# Variables
model.vPower_cap = Var(model.generators, model.times, within=NonNegativeReals)
model.vCR_cap = Var(model.storageunits, model.times, within=NonNegativeReals) 
model.vX_cap = Var(model.storageunits, model.times, within=NonNegativeReals) 

# Objective function
def objFunc(model):
    return sum(model.vPower_cap[stu,t]*(model.pPrices[t]-(model.pHRs[stu] * model.pFCs[stu] + model.pVOMs[stu]))
               -model.vCR_cap[stu,t]*(model.pPrices[t]+(model.pHRs[stu] * model.pFCs[stu] + model.pVOMs[stu]))
                for stu in model.storageunits for t in model.times)  
model.revenues_cap = Objective(rule=objFunc, sense=maximize)

# Constraints
def genMaxCapConstraint(model, stu, t):
    return model.vPower_cap[stu,t] <= model.pCaps[stu]
model.cap1 = Constraint(model.storageunits,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model,stu, t):#UPDATE
    return model.vPower_cap[stu,t] >= 0
model.cap2 = Constraint(model.storageunits,model.times,rule=genMinCapConstraint)

def genMaxCRConstraint(model, stu, t):
    return model.vCR_cap[stu,t] <= model.pMCRs[stu]
model.CR1 = Constraint(model.storageunits,model.times,rule=genMaxCRConstraint)

def genMinCRConstraint(model,stu, t):
    return model.vCR_cap[stu,t] >= 0
model.CR2 = Constraint(model.storageunits,model.times,rule=genMinCRConstraint)

def genMaxXConstraint(model, stu, t):
    return model.vX_cap[stu,t] <= model.pUXs[stu]*1.1
model.X1 = Constraint(model.storageunits,model.times,rule=genMaxXConstraint)

def genMinXConstraint(model,stu, t):
    return model.vX_cap[stu,t] >= 0
model.X2 = Constraint(model.storageunits,model.times,rule=genMinXConstraint)

def genStorageConstraint(model,stu, t):
    if t == model.times.first():  
        return model.vX_cap[stu,t] == model.pISOC[stu]- (model.vPower_cap[stu,t]/(model.pe[stu]**0.5))+ (model.vCR_cap[stu,t]*(model.pe[stu]**0.5))
    else:
        return model.vX_cap[stu,t] == model.vX_cap[stu,t-1]- (model.vPower_cap[stu,t]/(model.pe[stu]**0.5))+ (model.vCR_cap[stu,t]*(model.pe[stu]**0.5))
model.Stor = Constraint(model.storageunits,model.times,rule=genStorageConstraint)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Calculate total charging and discharging
total_charging_cap = sum(model.vCR_cap[stu, t].value for stu in model.storageunits for t in model.times)
total_discharging_cap = sum(model.vPower_cap[stu, t].value for stu in model.storageunits for t in model.times)

if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total Revenues_cap: ${model.revenues_cap():.2f}")
    print(f"Total Charging_cap: {total_charging_cap:.2f} MWh")
    print(f"Total Discharging_cap: {total_discharging_cap:.2f} MWh")

else:
    print("Solver did not find an optimal solution.")


# In[61]:


# Initialize DataFrames to store results
charging_cap= pd.DataFrame(index=prices.index.values, columns=storage.index.values)
discharging_cap = pd.DataFrame(index=prices.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging_cap.loc[t, s] = model.vCR_cap[s, t].value  # Charging values
            discharging_cap.loc[t, s] = model.vPower_cap[s, t].value  # Discharging values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile with bar plot for charging and discharging
plt.figure(figsize=(12, 6))

# Bar plots for charging and discharging for each storage unit
for s in storage.index:
    plt.bar(charging_cap.index, charging_cap[s], label=f'{s} Charging_cap', color='green', alpha=0.5)
    plt.bar(discharging_cap.index, -discharging_cap[s], label=f'{s} Discharging_cap', color='green', alpha=0.5)

# Labels and formatting
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend(loc='upper left')
plt.grid(True)
plt.show()

