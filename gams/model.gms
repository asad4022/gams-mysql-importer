$title MySQL to GAMS Importer Demo Model

* This model reads the long-format CSV created by the Python GUI:
* obs,column_name,value
*
* It imports the data into a two-dimensional parameter, reports the
* imported dimensions, and computes a simple mean by selected column.

Sets
    obs "observations"
    col "numeric column names";

Parameter
    data(obs, col)      "imported numeric values"
    meanByColumn(col)   "simple arithmetic mean by column";

$onEmbeddedCode Connect:
- CSVReader:
    file: data/exported_data_long.csv
    trace: 0
    symbols:
      - name: data
        indexColumns: [obs, column_name]
        valueColumns: [value]
- GAMSWriter:
    symbols:
      - name: data
$offEmbeddedCode

meanByColumn(col) = sum(obs, data(obs, col)) / card(obs);

display obs, col, card(obs), card(col), data, meanByColumn;
