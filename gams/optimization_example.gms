* Example optimization model using the semantic mapping layer.
*
* The model is intentionally simple:
*   maximize sum(obs, profit(obs) * x(obs))
*   subject to x(obs) <= capacity(obs)
*
* This gives end users a concrete pattern for turning imported columns
* into model-ready parameters that can be reused in richer GAMS models.

objectiveDefinition..
    z =e= sum(obs, profit(obs) * x(obs));

capacityLimit(obs)..
    x(obs) =l= capacity(obs);

Model importedResourceAllocation / objectiveDefinition, capacityLimit /;

xLevel(obs) = 0;
profitContribution(obs) = 0;
objectiveValue = 0;
optimizationSolved = 0;

if (mappingReady > 0.5,
    solve importedResourceAllocation maximizing z using lp;
    xLevel(obs) = x.l(obs);
    profitContribution(obs) = profit(obs) * x.l(obs);
    objectiveValue = z.l;
    optimizationSolved = 1;
    put_utility 'log' / 'OPTIMIZATION_SOLVED: The resource allocation example was solved successfully.';
else
    put_utility 'log' / 'OPTIMIZATION_SKIPPED: The generic import completed, but the optimization example was skipped because the required mapped fields were not available.';
);
