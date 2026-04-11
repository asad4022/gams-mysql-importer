$title MySQL to GAMS Importer Demo Model

* This model acts as a reusable bridge from queued SQL import jobs into GAMS.
*
* The Python application generates:
*   - gams/generated_import_runtime.gms
*   - gams/generated_unload_symbols.gms
*   - gams/generated_import_symbols.gms
*   - gams/generated_modeling_helpers.gms
*   - gams/generated_semantic_declarations.gms
*   - gams/generated_semantic_mapping.gms
*   - gams/generated_structured_declarations.gms
*   - gams/generated_structured_assignments.gms
*   - gams/example_use_imported_symbols.gms
*   - gams/example_multi_job_integration.gms
*
* The first queued import job is also exposed as the backward-compatible
* primary symbol data(obs,col) so that the existing mapping and demo
* optimization remain available, while downstream models can also reuse
* generic, semantic, structured, and multi-job helper artifacts.

$if not exist "gams/generated_import_runtime.gms" $abort "No generated import configuration found. Add import jobs in the GUI and export again."
$if not exist "gams/generated_unload_symbols.gms" $abort "No generated unload symbol list found. Add import jobs in the GUI and export again."
$if not exist "gams/generated_semantic_declarations.gms" $abort "No generated semantic declarations found. Add import jobs in the GUI and export again."
$if not exist "gams/generated_semantic_mapping.gms" $abort "No generated semantic mapping found. Add import jobs in the GUI and export again."
$if not exist "gams/generated_structured_declarations.gms" $abort "No generated structured declarations found. Add import jobs in the GUI and export again."
$if not exist "gams/generated_structured_assignments.gms" $abort "No generated structured assignments found. Add import jobs in the GUI and export again."

$include "gams/generated_import_runtime.gms"

Set
    semanticRole "semantic roles assigned in the GUI" / index, profit, capacity, demand, cost, lower_bound, upper_bound /
    semanticField "supported semantic fields" / profit, capacity, cost, demand /;

Parameter
    meanByColumn(col)                 "simple arithmetic mean by column for the primary symbol"
    mappedField(obs, semanticField)   "semantic view of the primary imported symbol"
    profit(obs)                       "profit coefficient for each observation"
    capacity(obs)                     "capacity upper bound for each observation"
    cost(obs)                         "optional cost coefficient for each observation"
    demand(obs)                       "optional demand value for each observation"
    fieldMatchCount(semanticField)    "number of imported columns mapped to each semantic field"
    xLevel(obs)                       "solution levels from optimization example"
    profitContribution(obs)           "objective contribution by observation";

Set
    requiredSemantic(semanticField)   "fields required by the optimization example"
    selectedSemanticColumn(semanticField, col) "imported columns selected for each semantic field";

Scalar
    nObs                  "number of imported observations in the primary symbol"
    nCol                  "number of imported numeric columns in the primary symbol"
    mappingReady          "1 if required semantic fields were mapped successfully"
    optimizationSolved    "1 if the optimization example was solved"
    missingRequiredCount  "number of missing required semantic fields"
    ambiguousRequiredCount "number of ambiguous required semantic fields"
    objectiveValue        "objective value from optimization example";

$include "gams/generated_semantic_declarations.gms"
$include "gams/generated_structured_declarations.gms"

Positive Variable
    x(obs) "decision variable: activity level for each observation";

Variable
    z "objective function value";

Equation
    objectiveDefinition "maximize total profit"
    capacityLimit(obs)  "activity may not exceed imported capacity";

nObs = card(obs);
nCol = card(col);
meanByColumn(col)$(card(obs) > 0) = sum(obs, data(obs, col)) / card(obs);

$include "gams/generated_semantic_mapping.gms"
$include "gams/generated_structured_assignments.gms"
$include "gams/import_mapping.gms"
$include "gams/optimization_example.gms"

execute_unload 'data/imported_data.gdx'
    obs
    col
    data
    semanticRole
    semanticField
    meanByColumn
    mappedField
    profit
    capacity
    cost
    demand
    requiredSemantic
    selectedSemanticColumn
    fieldMatchCount
    xLevel
    profitContribution
    objectiveValue
    mappingReady
    optimizationSolved
    missingRequiredCount
    ambiguousRequiredCount
    nObs
    nCol
$include "gams/generated_unload_symbols.gms"
;

display
    obs
    col
    nObs
    nCol
    data
    meanByColumn
    mappingReady
    optimizationSolved
    missingRequiredCount
    ambiguousRequiredCount
    selectedSemanticColumn
    fieldMatchCount
    mappedField
    profit
    capacity
    cost
    demand
    x.l
    z.l
    profitContribution;
