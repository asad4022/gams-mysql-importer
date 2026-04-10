* Semantic mapping from generic imported columns to model-ready parameters.
*
* This first implementation keeps the mapping in GAMS for transparency.
* Later versions can externalize the mapping to a configuration file.

Set semanticColumnMap(semanticField, *) "allowed imported column names for each semantic field" /
    profit.profit
    profit.margin
    profit.unit_profit
    capacity.capacity
    capacity.available_capacity
    cost.cost
    cost.unit_cost
    demand.demand
    demand.required_demand
/;

requiredSemantic(semanticField) = no;
requiredSemantic('profit') = yes;
requiredSemantic('capacity') = yes;

selectedSemanticColumn(semanticField, col) = semanticColumnMap(semanticField, col);
fieldMatchCount(semanticField) = sum(selectedSemanticColumn(semanticField, col), 1);

missingRequiredCount = sum(requiredSemantic(semanticField)$(fieldMatchCount(semanticField) = 0), 1);
ambiguousRequiredCount = sum(requiredSemantic(semanticField)$(fieldMatchCount(semanticField) > 1), 1);
mappingReady = 0;

if (missingRequiredCount = 0 and ambiguousRequiredCount = 0,
    mappingReady = 1;
    put_utility 'log' / 'OPTIMIZATION_READY: Required semantic columns were mapped successfully.';
else
    put_utility 'log' / 'OPTIMIZATION_SKIPPED: Required imported columns for the optimization example were not available or were ambiguous.';
    put_utility 'log' / 'OPTIMIZATION_HINT: Select columns matching profit/profit margin unit_profit and capacity/capacity available_capacity, or extend gams/import_mapping.gms.';
);

mappedField(obs, semanticField) = sum(selectedSemanticColumn(semanticField, col), data(obs, col));

profit(obs) = mappedField(obs, 'profit');
capacity(obs) = mappedField(obs, 'capacity');
cost(obs) = mappedField(obs, 'cost');
demand(obs) = mappedField(obs, 'demand');
