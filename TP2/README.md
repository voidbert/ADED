# LLM Inference Optimization on Systems Fujitsu A64FX

[Assignment](Assignment.pdf) about optimizing and modeling LLM inference performance on CPU
architectures. See our [assignment report](report/report.pdf).

## Project Structure

 - `jobs/`   : SLURM jobs for automated testing;
 - `scripts/`: Python scripts for statistical post-processing;
 - `results/`: Measurement data across configurations (TTFT, TPOT, Throughput);
 - `prompts/`: Prompt dataset for response evaluation.

## Reproduction Guide

To reproduce our findings, execute the following steps on the Deucalion supercomputer inside the
`jobs/` directory:

### 1. Model Setup

Download the necessary models from HuggingFace:

```console
$ sbatch download-models.sh
```

### 2. `llama.cpp` Compilation

Build `llama.cpp`. The provided script handles different compiler and BLAS library combinations:

```console
$ sbatch build-llama.sh
```

**Note**: The steps above (model setup and compilation) can and should be run in parallel to save
time. However, all jobs must be successfully completed before proceeding to the next steps.

### Performance Profiling (Warmup)

This is the core data collection phase. This step spawns multiple jobs to test a wide range of
configurations (quantizations, compilers, and libraries). Most of the metrics used in the final
report are derived from this stage.

```console
$ sbatch warmup-test.sh
```

### Quality Test 

Collect full model responses for our prompt dataset, to enable later human evaluation of output
coherence and accuracy:

```console
$ sbatch quality-test.sh
```

### Memory Mapping (mmap) Evaluation

Assess the impact of memory mapping on TPOT, TTFT, and memory usage:

```console
$ sbatch mmap-test.sh
```

### Multi-threading Scaling

Analyze how inference performance varies with NUMA policy and how it scales with thread count:

```console
& sbatch threading-test.sh
```

## Statistical Analysis and Visualization

Once all jobs have completed, use provided the Python scripts to process the raw data. These scripts
generate tables similar to these present in our report, as well as data for plots.

Before running any script, setup a Python virtual environment and install DuckDB:

```console
$ module load Python/3.14.2-GCCcore-15.2.0
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install duckdb
```

Then see the following scripts for more details on what they do and how to execute them:

 - Warmup & Stability:   `warmup-analysis.py`
 - Compiler Performance: `compiler-analysis.py`
 - Memory Management:    `mmap-analysis.py`
 - Quantization Impact:  `quantization-analysis.py`
 - Threading Impact:     `threading-analysis.py`
