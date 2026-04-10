$title Example Use Of Structured Imported Symbols

* This example demonstrates the Phase 3 structured-symbol workflow.
* It assumes the GUI was used to export a basket item with:
*   - Output symbol: productsData
*   - Structured index column: sku
*   - Structured value columns: profit, capacity
*
* After a successful run, these symbols are available in data/imported_data.gdx:
*   - productsData(obs__productsData, col__productsData)     generic fallback
*   - productsData__profit(structuredIndex1__productsData)   direct parameter
*   - productsData__capacity(structuredIndex1__productsData) direct parameter

Sets
    structuredIndex1__productsData(*);

Parameters
    productsData__profit(structuredIndex1__productsData)
    productsData__capacity(structuredIndex1__productsData);

$gdxin data/imported_data.gdx
$load structuredIndex1__productsData
$load productsData__profit
$load productsData__capacity
$gdxin

display productsData__profit, productsData__capacity;
