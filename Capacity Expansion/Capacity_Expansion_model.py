#!/usr/bin/env python
# coding: utf-8

# In[4]:


#1
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('DemandWithIndustries.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1
peak_time = demand.idxmax()

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)
new_fleet = pd.read_csv('NewGenerators.csv',header=0,index_col=0)##

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

cfs_w = pd.read_csv('WindCFs.csv',header=0,index_col=[0,1])['CF']##
cfs_w.index = pd.MultiIndex.from_product([['WindNew'],demand.index.values]) #relabel time index so aligned w/ demand ##


# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.ngenerators = Set(initialize=new_fleet.index.values)##
model.nregenerators = Set(within=model.ngenerators,initialize=new_fleet.loc[new_fleet['Fuel Type']=='Wind'].index.values)##
model.nrngenerators = Set(within=model.ngenerators,initialize=new_fleet.loc[new_fleet['Fuel Type']=='Natural gas'].index.values)##
model.combined_generators = Set(initialize=list(model.generators) + list(model.ngenerators))

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pCFWs = Param(model.ngenerators,model.times,initialize=cfs_w.to_dict()) ##
model.pnCaps = Param(model.ngenerators,initialize=new_fleet['Maximum Capacity (MW)'].to_dict()) ##
model.pACCs = Param(model.ngenerators,initialize=new_fleet['CC ($/MW)'].to_dict())##
model.pOCs = Param(model.ngenerators,initialize=new_fleet['OpCost ($/MWh)'].to_dict())##
model.pPRM = Param(model.times,initialize=1.15)##


# Variables
model.vPower = Var(model.combined_generators, model.times, within=NonNegativeReals)
model.vb = Var(model.ngenerators,within=Binary)##

# Objective function
def objFunc(model):  ##
    return (
        sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen, t] 
            for gen in model.generators for t in model.times)
        + sum((model.pOCs[ngen]) * model.vPower[ngen, t]
            for ngen in model.ngenerators for t in model.times)
        + sum((model.pACCs[ngen]*model.pnCaps[ngen]/365) * model.vb[ngen]
            for ngen in model.ngenerators)
    )

model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):##
	return sum(model.vPower[gen,t]  for gen in model.generators)+ sum(model.vPower[ngen,t]  for ngen in model.ngenerators)== model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model, gen, t):##
    return model.vPower[gen,t] >= 0
model.cap2 = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

def genMaxnCapConstraint(model, ngen, t):##
    return model.vPower[ngen,t] <= model.pnCaps[ngen]*model.vb[ngen]
model.ncap = Constraint(model.ngenerators,model.times,rule=genMaxnCapConstraint)

def genMinnCapConstraint(model, ngen, t):##
    return model.vPower[ngen,t] >= 0
model.ncap2 = Constraint(model.ngenerators,model.times,rule=genMinnCapConstraint)

def genMaxWindCapConstraint(model, ngen, t):##
    return model.vPower[ngen,t] <= model.pnCaps[ngen]*model.vb[ngen]*model.pCFWs[ngen,t]
model.ncapwind = Constraint(model.nregenerators,model.times,rule=genMaxWindCapConstraint)

def genPRMConstraint(model, t):##
    return (
        sum(model.pCaps[gen] for gen in model.generators if fleet.loc[gen, 'Fuel Type'] != 'Solar') + 
        sum(model.pCaps[gen] * model.pCFs[gen, t] for gen in model.regenerators) +
        sum(model.pnCaps[ngen] * model.vb[ngen] for ngen in model.nrngenerators) +
        sum(model.pnCaps[ngen] * model.vb[ngen] * model.pCFWs[ngen, t] for ngen in model.nregenerators)
        >= model.pPRM[t] * model.pDemand[t]
    )

model.nPRMcon = Constraint([peak_time], rule=genPRMConstraint)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
comb_gen = pd.DataFrame(index=demand.index.values,columns=fleet.index.values)
b = pd.DataFrame(index=demand.index.values, columns=new_fleet.index.values)##

if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.combined_generators:
    	for t in model.times:
            comb_gen.loc[t,g] = model.vPower[g,t].value

    for ng in model.ngenerators:##
            b.loc[ng] = model.vb[ng].value

else:
    print("Solver did not find an optimal solution.")

comb_gen.to_csv('Generation.csv')

comb_gen[comb_gen < 0] = 0

comb_gen.plot.area(stacked=True)
plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
plt.savefig('Generation.png')
plt.show()


# In[5]:


#2
from pyomo.environ import *
import pandas as pd, matplotlib.pyplot as plt

#Import data
demand = pd.read_csv('DemandWithIndustries.csv',header=None,index_col=0,names=['Demand(MWh)'])['Demand(MWh)']
demand.index = list(range(1,len(demand.index.values)+1)) #relabel demand indices as ints starting at 1
peak_time = demand.idxmax()

fleet = pd.read_csv('GeneratorFleet.csv',header=0,index_col=0)
new_fleet = pd.read_csv('NewGenerators.csv',header=0,index_col=0)##

cfs = pd.read_csv('SolarCFs.csv',header=0,index_col=[0,1])['CF']
cfs.index = pd.MultiIndex.from_product([['Sol1'],demand.index.values]) #relabel time index so aligned w/ demand

cfs_w = pd.read_csv('WindCFs.csv',header=0,index_col=[0,1])['CF']##
cfs_w.index = pd.MultiIndex.from_product([['WindNew'],demand.index.values]) #relabel time index so aligned w/ demand ##

# Create a ConcreteModel object
model = ConcreteModel()

# Set of generators
model.generators = Set(initialize=fleet.index.values) 
model.times = Set(initialize=demand.index.values)
model.regenerators = Set(within=model.generators,initialize=fleet.loc[fleet['Fuel Type']=='Solar'].index.values)
model.ngenerators = Set(initialize=new_fleet.index.values)##
model.nregenerators = Set(within=model.ngenerators,initialize=new_fleet.loc[new_fleet['Fuel Type']=='Wind'].index.values)##
model.nrngenerators = Set(within=model.ngenerators,initialize=new_fleet.loc[new_fleet['Fuel Type']=='Natural gas'].index.values)##
model.combined_generators = Set(initialize=list(model.generators) + list(model.ngenerators))

# Parameters
model.pCaps = Param(model.generators,initialize=fleet['Maximum Capacity (MW)'].to_dict()) #capacities in MW
model.pHRs = Param(model.generators,initialize=fleet['Heat Rate (MMBtu/MWh)'].to_dict()) #heat rates in MMBtu/MWh
model.pVOMs = Param(model.generators,initialize=fleet['Variable O&M ($/MWh)'].to_dict()) #variable O&M costs in $/MWh
model.pFCs = Param(model.generators,initialize=fleet['Fuel Cost ($/MMBtu)'].to_dict()) #fuel costs in $/MMBtu
model.pCFs = Param(model.generators,model.times,initialize=cfs.to_dict()) #capacity factors (unitless fractions)
model.pDemand = Param(model.times,initialize=demand.to_dict()) #demand in MWh
model.pCFWs = Param(model.ngenerators,model.times,initialize=cfs_w.to_dict()) ##
model.pnCaps = Param(model.ngenerators,initialize=new_fleet['Maximum Capacity (MW)'].to_dict()) ##
model.pACCs = Param(model.ngenerators,initialize=new_fleet['CC ($/MW)'].to_dict())##
model.pOCs = Param(model.ngenerators,initialize=new_fleet['OpCost ($/MWh)'].to_dict())##
model.pPRM = Param(model.times,initialize=1.15)##
# Add CO2 emission rate parameters to the model
model.pCO2Rates = Param(model.generators, initialize={'CC1': 0.35,'CC2': 0.4,'CC3': 0.45,'CT1': 0.75,'Nuc1': 0,'Sol1': 0})
model.pnCO2Rates = Param(model.ngenerators, initialize={'WindNew': 0,'CCNew': 0.3,'CTNew': 0.6})

# Variables
model.vPower = Var(model.combined_generators, model.times, within=NonNegativeReals)
#model.vnPower = Var(model.ngenerators,model.times,within=NonNegativeReals)##
model.vb = Var(model.ngenerators,within=NonNegativeIntegers)##

# Objective function
def objFunc(model):  ##
    return (
        sum((model.pHRs[gen] * model.pFCs[gen] + model.pVOMs[gen]) * model.vPower[gen, t] 
            for gen in model.generators for t in model.times)
        + sum((model.pOCs[ngen]) * model.vPower[ngen, t]
            for ngen in model.ngenerators for t in model.times)
        + sum(model.pACCs[ngen]*model.pnCaps[ngen]/365 * model.vb[ngen]
            for ngen in model.ngenerators)
    )

model.cost = Objective(rule=objFunc, sense=minimize)

# Constraints
def supplyDemandBalanceConstraint(model, t):##
	return sum(model.vPower[gen,t]  for gen in model.generators)+ sum(model.vPower[ngen,t]  for ngen in model.ngenerators)== model.pDemand[t]
model.sd = Constraint(model.times, rule=supplyDemandBalanceConstraint)

def genMaxCapConstraint(model, gen, t):
    return model.vPower[gen,t] <= model.pCaps[gen]
model.cap = Constraint(model.generators,model.times,rule=genMaxCapConstraint)

def genMinCapConstraint(model, gen, t):##
    return model.vPower[gen,t] >= 0
model.cap2 = Constraint(model.generators,model.times,rule=genMinCapConstraint)

def genCFLimit(model, gen, t):
    return model.vPower[gen,t] <= model.pCFs[gen,t] * model.pCaps[gen]
model.cf = Constraint(model.regenerators,model.times,rule=genCFLimit)

def genMaxnCapConstraint(model, ngen, t):##
    return model.vPower[ngen,t] <= model.pnCaps[ngen]*model.vb[ngen]
model.ncap = Constraint(model.ngenerators,model.times,rule=genMaxnCapConstraint)

def genMinnCapConstraint(model, ngen, t):##
    return model.vPower[ngen,t] >= 0
model.ncap2 = Constraint(model.ngenerators,model.times,rule=genMinnCapConstraint)

def genMaxWindCapConstraint(model, ngen, t):##
    return model.vPower[ngen,t] <= model.pnCaps[ngen]*model.vb[ngen]*model.pCFWs[ngen,t]
model.ncapwind = Constraint(model.nregenerators,model.times,rule=genMaxWindCapConstraint)

def genPRMConstraint(model, t):##
    return (
        sum(model.pCaps[gen] for gen in model.generators if fleet.loc[gen, 'Fuel Type'] != 'Solar') + 
        sum(model.pCaps[gen] * model.pCFs[gen, t] for gen in model.regenerators) +
        sum(model.pnCaps[ngen] * model.vb[ngen] for ngen in model.nrngenerators) +
        sum(model.pnCaps[ngen] * model.vb[ngen] * model.pCFWs[ngen, t] for ngen in model.nregenerators)
        >= model.pPRM[t] * model.pDemand[t]
    )
model.nPRMcon = Constraint([peak_time], rule=genPRMConstraint)

# Constraint to limit total CO2 emissions to 100,000 tons
def co2CapConstraint(model):
    return (
        sum(model.vPower[gen, t] * model.pCO2Rates[gen] for gen in model.generators for t in model.times)
        + sum(model.vPower[ngen, t] * model.pnCO2Rates[ngen] for ngen in model.ngenerators for t in model.times)
    ) <= 100000/365
model.co2Cap = Constraint(rule=co2CapConstraint)

# Solve the model
solver = SolverFactory('glpk')  
model.dual = Suffix(direction=Suffix.IMPORT)
results = solver.solve(model)

# Print model
model.pprint()

# Display results
comb_gen = pd.DataFrame(index=demand.index.values, columns=fleet.index.values)
b = pd.DataFrame(index=demand.index.values, columns=new_fleet.index.values)

if results.solver.termination_condition == TerminationCondition.optimal:
    print(f"Optimal solution found. Total cost: ${model.cost():.2f}") 

    for g in model.combined_generators:
        for t in model.times:
            comb_gen.loc[t, g] = model.vPower[g, t].value


    for ng in model.ngenerators:
            b.loc[ng] = model.vb[ng].value

    # Save generation and investment decisions
    comb_gen.to_csv('Generation_with_CO2.csv')

    comb_gen[comb_gen < 0] = 0

    # Plot the dispatch pattern
    comb_gen.plot.area(stacked=True)
    plt.ylabel('Generation (MWh)'), plt.xlabel('Time')
    plt.title('Dispatch with CO2 Constraint')
    plt.savefig('Generation_with_CO2.png')
    plt.show()
else:
    print("Solver did not find an optimal solution.")


# In[ ]:




