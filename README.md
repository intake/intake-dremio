# Intake-Dremio

Dremio Plugin for Intake based on pyarrow Flight


## User Installation

To install the intake-dremio plugin, execute the following command

```
conda install -c conda-forge intake-dremio
```

or:

```
pip install intake-dremio
```

When installing from the `pyviz` channel and `conda-forge` conda channels, you must ensure that `libarrow-flight` is also installed:

```
conda install -c pyviz -c conda-forge intake-dremio libarrow-flight
```

This is because `conda-forge` has split up pyarrow into individual packages as of `pyarrow 16`.

## Example

An Intake catalog referencing a Dremio dataset consists of the `uri` pointing to the Dremio instance along with a username and password and a SQL expression (`sql_expr`), e.g.:

```yaml
sources:
  dremio_vds:
    driver: dremio 
    args:
        uri: grpc+tcp://{{ env(DREMIO_USER) }}:{{ env(DREMIO_PASSWORD) }}@x.x.x.x:32010  
        sql_expr: SELECT * FROM TABLE ORDER BY "timestamp" ASC
```
