# Apache Spark SQL Query Optimization

[Assignment](Assignment.pdf) about optimizing an Apache Spark SQL Query for Deucalion reports.

## Installation & Environment Setup

### Local Environment (Manual)

To install the necessary dependencies, start by creating and entering a Python virtual environment.
Then, install all necessary dependencies:

```console
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -e .
```

**Note:** Ensure your dataset is in the dataset/ folder and that any Portuguese month names in
filenames are renamed to English (e.g., Ago -> Aug) to ensure Spark compatibility.

### Deucalion Usage (Automated)

On the Deucalion supercomputer, the environment setup and dependency installation are automated via
SLURM. For instance, the used toolchain modules are:

```console
$ module load Python/3.13.5-GCCcore-14.3.0
$ module load Java/21.0.8
$ module load PostgreSQL/16.1-GCCcore-12.3.0
```

Before running any jobs, please note that the variables used in the scripts are defined in
`jobs/config.sh`.  While these are pre-configured, they **can and should be reviewed or modified**
to match specific requirements  (such as the number of runs or the specific query classes to test)
before execution.

Run the following to prepare the workspace:

```console
$ sbatch jobs/setup-env.sh
```

## Running

### Available Queries

- `Original`: The baseline Apache Spark SQL implementation used as a reference for validation.

- `MultiPass`: Executes one separate query for each required time Period (Month, Quarter, and
               Year), requiring multiple passes over the dataset.

- `SinglePass`: An optimized Spark implementation that aggregates all needed information for the
                required time periods.

- `FastLoad`: It improves on previous optimizations by taking advantage of bulk reading and
              replacing Spark's `inferSchema` with a manually defined schema, avoiding the costly
              initial scan of the files to determine data types.

- `DuckDB`: Executes the analytical query using the DuckDB engine, known for high-performance
            vectorized execution.

- `PostreSQL`: Executes the query using a traditional RDBMS. Requires a running PostgreSQL instance.

### Available Programs

The project includes three main scripts located in the `aded/` directory to interact with the query
implementations:

- `aded/perf.py`: Used for query profiling, supports warmup runs and output of built-in statistics.
                  Exports results to JSON.

```console
$ python aded/perf.py -w 5 -r 5 <QueryClass> <DatasetPath>
```

- `aded/validator.py`: Compares the output of an optimized query class against the Original
                       implementation to ensure its validity.

```console
$ python aded/validator.py <QueryClass> <DatasetPath>
```

- `aded/run.py`: Executes a specific query class once.

```console
$ python aded/run.py <QueryClass> <DatasetPath>
```

#### Running PostgreSQL

If you plan on running our PostgreSQL-based query implementation, the PostgreSQL server needs to be
running before running the query.


Using [PostgreSQL's docker container](https://hub.docker.com/_/postgres) is the recommended way of
running PostgreSQL locally for the query. The command below starts the server with the necessary
port and file system forwarding:

```console
$ docker run -p 5432:5432 --user 1000:1000 -v /:/mnt -e POSTGRES_HOST_AUTH_METHOD=trust postgres
```

### On Deucalion

For execution on the Deucalion supercomputer, each Python program has a corresponding shell script
(.sh) in the `jobs/` directory configured for SLURM submission. These scripts handle module loading
and environment activation automatically.

#### Performance Benchmarking (`jobs/perf.sh`)

This is the primary script for benchmarking. It iterates through all query classes defined in
config.sh, handles the lifecycle of background services and saves results to the results/ folder.

```console
$ sbatch jobs/perf.sh
```

#### Validation (`jobs/validator.sh`)

This script is used to verify that an optimized query class produces the exact same results as the
Original implementation. It is essential to run this after making changes to ensure optimizations
haven't introduced bugs.

```console
$ sbatch jobs/validator.sh <QueryClass>
```

#### Single Execution (`jobs/run.sh`)

This script is used to execute a specific query class a single time. It is useful for debugging
specific implementations or checking the standard output/logs without the overhead of multiple
benchmark runs.

```console
$ sbatch jobs/run.sh <QueryClass>
```

#### Scalability Analysis (`jobs/scalability.sh`)

This script was developed to perform a detailed scalability analysis of various implementations on
the Deucalion supercomputer. It automates the execution of tests by varying the number of
computational resources (threads/CPUs) assigned to the job, allowing the identification of the
behavior of each engine (Spark, DuckDB, PostgreSQL) as the infrastructure scales.

```console
$ sbatch jobs/scalability.sh
```

#### Warm-up Benchmarking (`jobs/warmup.sh`)

To analyze the impact of the Java Virtual Machine (JVM) warm-up on Apache Spark performance, a
specific script was created to execute the most efficient implementation (FastLoad) continuously for
60 runs.

```console
$ sbatch jobs/warmup_benchmark.sh
```
