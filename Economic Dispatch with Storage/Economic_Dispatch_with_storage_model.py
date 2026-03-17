#!/usr/bin/env python
# coding: utf-8

# In[10]:


#PS3_EconDispatch
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)

# Objective function
def objFunc(model):
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) >= model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
gen = pd.DataFrame(index=demand.index.values,columns=fleet.index.values)
if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.generators:
    	for t in model.times:
            gen.loc[t,g] = model.vPower[g,t].value

else:
    print("Solver did not find an optimal solution.")

#Calculate system emissions
totalEmissions = (gen*fleet['CO2 Emissions Rate (tons/MWh)']).sum().sum()
print('Total system emissions (tons CO2):',totalEmissions)

#Plot system dispatch
gen.to_csv('GenerationWithoutSto.csv')
gen.plot.bar(stacked=True)
plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
plt.savefig('GenerationWithoutSto.png')
plt.show()


# In[11]:


#2
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

storage = pd.read_csv('StorageUnit.csv',header=0,index_col=0) #UPDATE
fleet = pd.concat([fleet,storage]) #UPDATE

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.storageunits =Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Storage'].index.values) #UPDATE

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pEs = Param(model.generators,initialize=fleet['CO2 Emissions Rate (tons/MWh)'].to_dict())#emissions #UPDATE
model.pMCRs= Param(model.storageunits,initialize=storage['Maximum Capacity (MW)'].to_dict()) #UPDATE
model.pUXs= Param(model.storageunits,initialize=storage['Maximum Energy Capacity (MWh)'].to_dict()) #UPDATE
model.pe= Param(model.storageunits,initialize=storage['RTE'].to_dict()) #UPDATE
model.pISOC=Param(model.storageunits,initialize=storage['Initial SOC (MWh)'].to_dict()) #UPDATE

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vCR = Var(model.storageunits, model.times, within=NonNegativeReals) #UPDATES
model.vX = Var(model.storageunits, model.times, within=NonNegativeReals) #UPDATES

# Objective function
def objFunc(model):
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t] for gen in model.generators for t in model.times) #OC(s)=0 
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model,stu, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]+ sum(model.vCR[stu,t] for stu in model.storageunits) #UPDATE 
model.sd = Constraint(model.storageunits,model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap1 = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model,gen, t):#UPDATE
    return model.vPower[gen,t] >= 0
model.cap2 = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genMaxCRConstraint(model, stu, t):#UPDATE
    return model.vCR[stu,t] <= model.pMCRs[stu]
model.CR1 = Constraint(model.storageunits,model.times,rule=genMaxCRConstraint)

def genMinCRConstraint(model,stu, t):#UPDATE
    return model.vCR[stu,t] >= 0
model.CR2 = Constraint(model.storageunits,model.times,rule=genMinCRConstraint)

def genMaxXConstraint(model, stu, t):#UPDATE
    return model.vX[stu,t] <= model.pUXs[stu]
model.X1 = Constraint(model.storageunits,model.times,rule=genMaxXConstraint)

def genMinXConstraint(model,stu, t):#UPDATE
    return model.vX[stu,t] >= 0
model.X2 = Constraint(model.storageunits,model.times,rule=genMinXConstraint)

def genStorageConstraint(model,stu, t):#UPDATE
    if t == model.times.first():  
        return model.vX[stu,t] == model.pISOC[stu]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
    else:
        return model.vX[stu,t] == model.vX[stu,t-1]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
model.Stor = Constraint(model.storageunits,model.times,rule=genStorageConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
gen = pd.DataFrame(index=demand.index.values,columns=fleet.index.values)
if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.generators:
    	for t in model.times:
            gen.loc[t,g] = model.vPower[g,t].value

else:
    print("Solver did not find an optimal solution.")

#Calculate system emissions
totalEmissions = (gen*fleet['CO2 Emissions Rate (tons/MWh)']).sum().sum()
print('Total system emissions (tons CO2):',totalEmissions)

#Plot system dispatch
gen.to_csv('GenerationWithSto.csv')
gen.plot.bar(stacked=True)
plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
plt.savefig('GenerationWithSto.png')
plt.show()


# In[12]:


#3
# Initialize DataFrames to store results
charging = pd.DataFrame(index=demand.index.values, columns=storage.index.values)
discharging = pd.DataFrame(index=demand.index.values, columns=storage.index.values)
soc = pd.DataFrame(index=demand.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging.loc[t,s] = model.vCR[s,t].value  # Charging values
            discharging.loc[t,s] = model.vPower[s,t].value  # Discharging values
            soc.loc[t,s] = model.vX[s,t].value  # State of charge values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile
plt.figure(figsize=(10,6))
for s in storage.index:
    plt.plot(charging.index, charging[s], label=f'{s} Charging', linestyle='--')
    plt.plot(discharging.index, discharging[s], label=f'{s} Discharging', linestyle=':')
    plt.plot(soc.index, soc[s], label=f'{s} SOC')

plt.title('Storage Facility Operations')
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend()
plt.grid(True)
plt.savefig('StorageOperations.png')
plt.show()


# In[13]:


#5(with RR)
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

storage = pd.read_csv('StorageUnit.csv',header=0,index_col=0) #UPDATE
fleet = pd.concat([fleet,storage]) #UPDATE

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

ramprates = pd.read_csv('RampRates2.csv',header=0,index_col=0)
fleet = pd.concat([fleet,ramprates],axis =1)

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.storageunits =Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Storage'].index.values) #UPDATE

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pEs = Param(model.generators,initialize=fleet['CO2 Emissions Rate (tons/MWh)'].to_dict())#emissions #UPDATE
model.pMCRs= Param(model.storageunits,initialize=storage['Maximum Capacity (MW)'].to_dict()) #UPDATE
model.pUXs= Param(model.storageunits,initialize=storage['Maximum Energy Capacity (MWh)'].to_dict()) #UPDATE
model.pe= Param(model.storageunits,initialize=storage['RTE'].to_dict()) #UPDATE
model.pISOC=Param(model.storageunits,initialize=storage['Initial SOC (MWh)'].to_dict()) #UPDATE
model.pRRs = Param(model.generators,initialize=fleet['Ramp Rate (MWh)'].to_dict())#UPDATE ramp rates in MWh

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vCR = Var(model.storageunits, model.times, within=NonNegativeReals) #UPDATES
model.vX = Var(model.storageunits, model.times, within=NonNegativeReals) #UPDATES

# Objective function
def objFunc(model):
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t] for gen in model.generators for t in model.times) #OC(s)=0 
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model,stu, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]+ sum(model.vCR[stu,t] for stu in model.storageunits) #UPDATE 
model.sd = Constraint(model.storageunits,model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap1 = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model,gen, t):#UPDATE
    return model.vPower[gen,t] >= 0
model.cap2 = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genMaxCRConstraint(model, stu, t):#UPDATE
    return model.vCR[stu,t] <= model.pMCRs[stu]
model.CR1 = Constraint(model.storageunits,model.times,rule=genMaxCRConstraint)

def genMinCRConstraint(model,stu, t):#UPDATE
    return model.vCR[stu,t] >= 0
model.CR2 = Constraint(model.storageunits,model.times,rule=genMinCRConstraint)

def genMaxXConstraint(model, stu, t):#UPDATE
    return model.vX[stu,t] <= model.pUXs[stu]
model.X1 = Constraint(model.storageunits,model.times,rule=genMaxXConstraint)

def genMinXConstraint(model,stu, t):#UPDATE
    return model.vX[stu,t] >= 0
model.X2 = Constraint(model.storageunits,model.times,rule=genMinXConstraint)

def genStorageConstraint(model,stu, t):#UPDATE
    if t == model.times.first():  
        return model.vX[stu,t] == model.pISOC[stu]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
    else:
        return model.vX[stu,t] == model.vX[stu,t-1]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
model.Stor = Constraint(model.storageunits,model.times,rule=genStorageConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

def genRR1(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():
        return Constraint.Skip
     else:
        return model.vPower[gen,t]- model.vPower[gen,t-1] <= model.pRRs[gen]
model.RR1 = Constraint(model.generators, model.times, rule=genRR1)

def genRR2(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first(): 
        return Constraint.Skip
     else:
        return model.vPower[gen,t-1]- model.vPower[gen,t] <= model.pRRs[gen]
model.RR2 = Constraint(model.generators, model.times, rule=genRR2)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
gen = pd.DataFrame(index=demand.index.values,columns=fleet.index.values)
if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.generators:
    	for t in model.times:
            gen.loc[t,g] = model.vPower[g,t].value

else:
    print("Solver did not find an optimal solution.")

#Calculate system emissions
totalEmissions = (gen*fleet['CO2 Emissions Rate (tons/MWh)']).sum().sum()
print('Total system emissions (tons CO2):',totalEmissions)

#Plot system dispatch
gen.to_csv('GenerationWithSto&RR.csv')
gen.plot.bar(stacked=True)
plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
plt.savefig('GenerationWithSto&RR.png')
plt.show()


# In[8]:


#5withRR&STO
# Initialize DataFrames to store results
charging = pd.DataFrame(index=demand.index.values, columns=storage.index.values)
discharging = pd.DataFrame(index=demand.index.values, columns=storage.index.values)
soc = pd.DataFrame(index=demand.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging.loc[t,s] = model.vCR[s,t].value  # Charging values
            discharging.loc[t,s] = model.vPower[s,t].value  # Discharging values
            soc.loc[t,s] = model.vX[s,t].value  # State of charge values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile
plt.figure(figsize=(10,6))
for s in storage.index:
    plt.plot(charging.index, charging[s], label=f'{s} Charging', linestyle='--')
    plt.plot(discharging.index, discharging[s], label=f'{s} Discharging', linestyle=':')
    plt.plot(soc.index, soc[s], label=f'{s} SOC')

plt.title('Storage Facility Operations')
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend()
plt.grid(True)
plt.savefig('StorageOperations.png')
plt.show()


# In[18]:


#6_EconDispatch with RR & WIND(NO STO1)
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

wind = pd.read_csv('WindUnit.csv',header=0,index_col=0) #UPDATE
fleet = pd.concat([fleet,wind]) #UPDATE

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

cfs_wind = pd.read_csv('WindCFs.csv',header=0,index_col=[0,1])['CF']#WIND
cfs_wind.index = pd.MultiIndex.from_product([['Win1'],demand.index.values]) #WIND

ramprates = pd.read_csv('RampRates5.csv',header=0,index_col=0)

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.regenerators_w = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Wind'].index.values)

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pCFs_wind = Param(model.generators,model.times,initialize=cfs_wind.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pRRs = Param(model.generators,initialize=ramprates['Ramp Rate (MWh)'].to_dict())#UPDATE ramp rates in MWh

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)

# Objective function
def objFunc(model):
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) >= model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

def genCF2Limit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs_wind[gen,t] * model.pCaps[gen]
model.cfwind = Constraint(model.regenerators_w,model.times,rule=genCF2Limit)

def genRR1(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():
        return Constraint.Skip
     else:
        return model.vPower[gen,t]- model.vPower[gen,t-1] <= model.pRRs[gen]
model.RR1 = Constraint(model.generators, model.times, rule=genRR1)

def genRR2(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first(): 
        return Constraint.Skip
     else:
        return model.vPower[gen,t-1]- model.vPower[gen,t] <= model.pRRs[gen]
model.RR2 = Constraint(model.generators, model.times, rule=genRR2)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
gen = pd.DataFrame(index=demand.index.values,columns=fleet.index.values)
if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.generators:
    	for t in model.times:
            gen.loc[t,g] = model.vPower[g,t].value

else:
    print("Solver did not find an optimal solution.")

#Calculate system emissions
totalEmissions = (gen*fleet['CO2 Emissions Rate (tons/MWh)']).sum().sum()
print('Total system emissions (tons CO2):',totalEmissions)

#Plot system dispatch
gen.to_csv('GenerationWithoutSto.csv')
gen.plot.bar(stacked=True)
plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
plt.savefig('GenerationWithoutSto.png')
plt.show()


# In[20]:


#6_EconDispatch with RR & WIND(WITH STO1)
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('Demand.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)

wind = pd.read_csv('WindUnit.csv',header=0,index_col=0) #UPDATE
fleet = pd.concat([fleet,wind]) #UPDATE

storage = pd.read_csv('StorageUnit.csv',header=0,index_col=0) #UPDATE
fleet = pd.concat([fleet,storage]) #UPDATE

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

cfs_wind = pd.read_csv('WindCFs.csv',header=0,index_col=[0,1])['CF']#WIND
cfs_wind.index = pd.MultiIndex.from_product([['Win1'],demand.index.values]) #WIND

ramprates = pd.read_csv('RampRates.csv',header=0,index_col=0)

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.regenerators_w = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Wind'].index.values)
model.storageunits =Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Storage'].index.values) 

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pCFs_wind = Param(model.generators,model.times,initialize=cfs_wind.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pEs = Param(model.generators,initialize=fleet['CO2 Emissions Rate (tons/MWh)'].to_dict())#emissions #UPDATE
model.pMCRs= Param(model.storageunits,initialize=storage['Maximum Capacity (MW)'].to_dict()) #UPDATE
model.pUXs= Param(model.storageunits,initialize=storage['Maximum Energy Capacity (MWh)'].to_dict()) #UPDATE
model.pe= Param(model.storageunits,initialize=storage['RTE'].to_dict()) #UPDATE
model.pISOC=Param(model.storageunits,initialize=storage['Initial SOC (MWh)'].to_dict()) #UPDATE
model.pRRs = Param(model.generators,initialize=ramprates['Ramp Rate (MWh)'].to_dict())#UPDATE ramp rates in MWh

# Variables
model.vPower = Var(model.generators, model.times, within=NonNegativeReals)
model.vCR = Var(model.storageunits, model.times, within=NonNegativeReals) #UPDATES
model.vX = Var(model.storageunits, model.times, within=NonNegativeReals) #UPDATES

# Objective function
def objFunc(model):
    return sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen,t] for gen in model.generators for t in model.times)
model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model,stu, t):
	return sum(model.vPower[gen,t]  for gen in model.generators) == model.pDemand[t]+ sum(model.vCR[stu,t] for stu in model.storageunits) #UPDATE 
model.sd = Constraint(model.storageunits,model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

def genCF2Limit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs_wind[gen,t] * model.pCaps[gen]
model.cfwind = Constraint(model.regenerators_w,model.times,rule=genCF2Limit)

def genMaxCRConstraint(model, stu, t):#UPDATE
    return model.vCR[stu,t] <= model.pMCRs[stu]
model.CR1 = Constraint(model.storageunits,model.times,rule=genMaxCRConstraint)

def genMinCRConstraint(model,stu, t):#UPDATE
    return model.vCR[stu,t] >= 0
model.CR2 = Constraint(model.storageunits,model.times,rule=genMinCRConstraint)

def genMaxXConstraint(model, stu, t):#UPDATE
    return model.vX[stu,t] <= model.pUXs[stu]
model.X1 = Constraint(model.storageunits,model.times,rule=genMaxXConstraint)

def genMinXConstraint(model,stu, t):#UPDATE
    return model.vX[stu,t] >= 0
model.X2 = Constraint(model.storageunits,model.times,rule=genMinXConstraint)

def genStorageConstraint(model,stu, t):#UPDATE
    if t == model.times.first():  
        return model.vX[stu,t] == model.pISOC[stu]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
    else:
        return model.vX[stu,t] == model.vX[stu,t-1]- (model.vPower[stu,t]/(model.pe[stu]**0.5))+ (model.vCR[stu,t]*(model.pe[stu]**0.5))
model.Stor = Constraint(model.storageunits,model.times,rule=genStorageConstraint)

def genRR1(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first():
        return Constraint.Skip
     else:
        return model.vPower[gen,t]- model.vPower[gen,t-1] <= model.pRRs[gen]
model.RR1 = Constraint(model.generators, model.times, rule=genRR1)

def genRR2(model, gen, t): #UPDATE#UPDATE
     if t == model.times.first(): 
        return Constraint.Skip
     else:
        return model.vPower[gen,t-1]- model.vPower[gen,t] <= model.pRRs[gen]
model.RR2 = Constraint(model.generators, model.times, rule=genRR2)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
gen = pd.DataFrame(index=demand.index.values,columns=fleet.index.values)
if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.generators:
    	for t in model.times:
            gen.loc[t,g] = model.vPower[g,t].value

else:
    print("Solver did not find an optimal solution.")

#Calculate system emissions
totalEmissions = (gen*fleet['CO2 Emissions Rate (tons/MWh)']).sum().sum()
print('Total system emissions (tons CO2):',totalEmissions)

#Plot system dispatch
gen.to_csv('GenerationWithSto.csv')
gen.plot.bar(stacked=True)
plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
plt.savefig('GenerationWithSto.png')
plt.show()


# In[21]:


#6withRR&STO
# Initialize DataFrames to store results
charging = pd.DataFrame(index=demand.index.values, columns=storage.index.values)
discharging = pd.DataFrame(index=demand.index.values, columns=storage.index.values)
soc = pd.DataFrame(index=demand.index.values, columns=storage.index.values)

# Populate the DataFrames if the solution is optimal
if results.solver.termination_condition == TerminationCondition.optimal:
    print("Optimal solution found.")
    
    for s in model.storageunits:
        for t in model.times:
            charging.loc[t,s] = model.vCR[s,t].value  # Charging values
            discharging.loc[t,s] = model.vPower[s,t].value  # Discharging values
            soc.loc[t,s] = model.vX[s,t].value  # State of charge values

else:
    print("Solver did not find an optimal solution.")

# Plot the storage profile
plt.figure(figsize=(10,6))
for s in storage.index:
    plt.plot(charging.index, charging[s], label=f'{s} Charging', linestyle='--')
    plt.plot(discharging.index, discharging[s], label=f'{s} Discharging', linestyle=':')
    plt.plot(soc.index, soc[s], label=f'{s} SOC')

plt.title('Storage Facility Operations')
plt.xlabel('Time')
plt.ylabel('Energy (MWh)')
plt.legend()
plt.grid(True)
plt.savefig('StorageOperations.png')
plt.show()


# In[ ]:




