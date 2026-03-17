#!/usr/bin/env python
# coding: utf-8

# In[1]:


#With All Storages (SCENARIO FOR 2035)
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('PJM_Loads_NEW.csv',header=0,index_col=0)['SUM_LOAD']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1

fleet = pd.read_csv('PJM_fleetNEW_2.csv',header=0,index_col=0)

cfs_w = pd.read_csv('CapacityFactors_Wind.csv',header=0,index_col=[0,1])['CF_Wind']
cfs_w.index = pd.MultiIndex.from_product([['Wind'],demand.index.values]) #relabel time index so aligned w/ demand

cfs_s = pd.read_csv('CapacityFactors_Solar.csv',header=0,index_col=[0,1])['CF_Solar']
cfs_s.index = pd.MultiIndex.from_product([['Solar'],demand.index.values]) #relabel time index so aligned w/ demand

cfs_h = pd.read_csv('CapacityFactors_Hydro.csv',header=0,index_col=[0,1])['CF_Hydro']
cfs_h.index = pd.MultiIndex.from_product([['Hydro'],demand.index.values]) #relabel time index so aligned w/ demand

storage1 = pd.read_csv('StorageUnits.csv',header=0,index_col=0) #UPDATE
fleet = pd.concat([fleet,storage1]) #UPDATE

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.s_regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel type']=='Solar'].index.values)
model.w_regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel type']=='Wind'].index.values)
model.h_regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel type']=='Hydro'].index.values)
model.storageunits = Set(within=model.generators, initialize=fleet.loc[fleet['Fuel type'].isin(['PHS', 'Battery','Hydrogen'])].index.values)

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pminCaps = Param(model.generators,initialize=fleet['Minimum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['VOM ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFWs = Param(model.generators,model.times,initialize=cfs_w.to_dict()) #capacity factors (unitless fractions)
model.pCFHs = Param(model.generators,model.times,initialize=cfs_h.to_dict())
model.pCFSs = Param(model.generators,model.times,initialize=cfs_s.to_dict())
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pEs = Param(model.generators,initialize=fleet['CO2 Emissions Rate (tons/MWh)'].to_dict())#emissions #UPDATE
model.pMCRs= Param(model.storageunits,initialize=storage1['Maximum Capacity (MW)'].to_dict()) #UPDATE
model.pUXs= Param(model.storageunits,initialize=storage1['Maximum Energy Capacity (MWh)'].to_dict()) #UPDATE
model.pe= Param(model.storageunits,initialize=storage1['RTE'].to_dict()) #UPDATE
model.pISOC= Param(model.storageunits,initialize=storage1['Initial SOC (MWh)'].to_dict()) #UPDATE

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

def genMinCapConstraint(model, gen, t):
    return model.vPower[gen,t] >= model.pminCaps[gen]
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

def genCFWLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFWs[gen,t] * model.pCaps[gen]
model.cfw = Constraint(model.w_regenerators,model.times,rule=genCFWLimit)

def genCFSLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFSs[gen,t] * model.pCaps[gen]
model.cfs = Constraint(model.s_regenerators,model.times,rule=genCFSLimit)

def genCFHLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFHs[gen,t] * model.pCaps[gen]
model.cfh = Constraint(model.h_regenerators,model.times,rule=genCFHLimit)

#Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
#model.pprint()

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

day = 197  # Modify this to select a different day
hours_per_day = 24
start_hour = (day - 1) * hours_per_day + 1
end_hour = day * hours_per_day

# Slice the data for the specified day
gen_day = gen.loc[start_hour:end_hour]

# Plot the system dispatch for the selected day
gen_day.plot.bar(stacked=True)
plt.ylabel('Generation (MWh)')
plt.xlabel('Hour')
plt.title(f'System Dispatch for Day {day}')
plt.savefig(f'Generation_Day{day}.png')
plt.show()


# In[ ]:




