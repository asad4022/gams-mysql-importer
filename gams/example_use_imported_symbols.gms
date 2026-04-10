$title Example Use Of Imported Symbols

* Auto-generated example consumer for the current import basket.
* It loads the current symbols from "data/imported_data.gdx" using the
* generated include file and then performs a few simple calculations.

$include "gams/generated_import_symbols.gms"

Scalar totalPrimaryData "sum of all values in the primary imported symbol";
totalPrimaryData = sum((obs, col), data(obs, col));

Scalar total__productsData "sum of all values in productsData";
total__productsData = sum((obs__productsData, col__productsData), productsData(obs__productsData, col__productsData));

Scalar total__resourcesData "sum of all values in resourcesData";
total__resourcesData = sum((obs__resourcesData, col__resourcesData), resourcesData(obs__resourcesData, col__resourcesData));

display data, totalPrimaryData, productsData, resourcesData, total__productsData, total__resourcesData;
