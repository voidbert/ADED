# Apache Spark SQL Query Optimization

[Assignment](Assignment.pdf) about optimizing an Apache Spark SQL Query for generating Deucalion
usage reports. See our [assignment report](report/report.pdf).

## Installation & Environment Setup

### Local Environment (Manual)

Start by creating and entering a Python virtual environment. Then, install all necessary
dependencies:

```console
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -e .
```

Finally, copy your dataset to the `dataset/` directory and ensure that all Portuguese month names in
the filenames are renamed to English (e.g., `Ago` -> `Aug`).

### Deucalion Usage

On the Deucalion supercomputer, the environment setup and dependency installation can be done by
running a single job:

```console
$ sbatch jobs/setup-env.sh
```

Deucalion jobs may need additional configuration before running (see `jobs/config.sh`).

## Running

### Available Queries

- `Original`: Baseline Apache Spark SQL implementation used for validating results;

- `MultiPass`: Executes one separate query for each time period (Month, Quarter, and Year);

- `SinglePass`: Aggregates all needed information for the required time periods with a single pass
                over the dataset;

- `FastLoad`: Improves on `SinglePass` by taking advantage of bulk CSV reading and a manually
              defined schema;

- `DuckDB`: Port of `FastLoad` to DuckDB;

- `PostreSQL`: Executes the query using a traditional RDBMS (PostgreSQL).

### Available Programs

The project includes three main scripts, located in the `aded/` directory, to run, test, and
benchmark the query implementations:

- `aded/run.py`: Executes a specific query class once.

```console
$ python aded/run.py <QueryClass> <DatasetPath>
```

- `aded/validator.py`: Compares the output of an optimized query class against the Original
                       implementation to ensure its validity.

```console
$ python aded/validator.py <QueryClass> <DatasetPath>
```

- `aded/perf.py`: Used for query profiling. Exports results to JSON.

```console
$ python aded/perf.py -w 5 -r 5 <QueryClass> <DatasetPath>
```

#### Running PostgreSQL

If you plan on running our PostgreSQL-based query implementation, the PostgreSQL server needs to be
running before running the query.

Using [PostgreSQL's docker container](https://hub.docker.com/_/postgres) is the recommended way of
running PostgreSQL locally. The command below starts the server with the necessary port and file
system forwarding:

```console
$ docker run -p 5432:5432 --user 1000:1000 -v /:/mnt -e POSTGRES_HOST_AUTH_METHOD=trust postgres
```

For Deucalion usage, see examples in `jobs/`.

### Deucalion Jobs

#### Performance Benchmarking (`jobs/perf.sh`)

This is the primary script for benchmarking. It iterates through all query classes defined in
`config.sh`, handles the lifecycle of background services and saves results to the `results/`
directory.

```console
$ sbatch jobs/perf.sh
```

#### Validation (`jobs/validator.sh`)

This script verifies that an optimized query class produces the exact same results as the `Original`
implementation. It is essential to run this script after making changes, to ensure optimizations
have not introduced errors.

```console
$ sbatch jobs/validator.sh <QueryClass>
```

#### Single Execution (`jobs/run.sh`)

This script, mostly used for debugging, executes a specific query class a single time.

```console
$ sbatch jobs/run.sh <QueryClass>
```

#### Scalability Analysis (`jobs/scalability.sh`)

This script performs a strong scalability analysis of various query implementations.

```console
$ sbatch jobs/scalability.sh
```

#### Warm-up Benchmarking (`jobs/warmup.sh`)

To analyze the impact of the Java Virtual Machine (JVM) warm-up on Apache Spark performance,
this scripts measures the performance of the `FastLoad` query for 60 consecutive runs.

```console
$ sbatch jobs/warmup_benchmark.sh
```
