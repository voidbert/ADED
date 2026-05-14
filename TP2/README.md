# LLM Inference Optimization in Systems Fujitsu A64FX

[Assignment](Assignment.pdf) about optimizing and modeling LLM inference performance on CPU
architectures.

## Project Structure

* `/jobs`   : SLURM shell scripts for automated model deployment and testing;
* `/scripts`: Python scripts for statistical post-processing;
* `/results`: Measurement data (TTFT, TPOT, Throughput);
* `/prompts`: Standardized prompt dataset (Small, Medium, and Large categories).

## Reproduction Guide

To reproduce the findings presented in the research report, execute the following steps in order in
the Deucalion supercomputer, inside the `/jobs` directory:

### 1. Model Setup

Ensure the models are dowloaded to your system:

```console
$ sbatch download-models.sh
```

### 2. Llama.cpp Compilation

Build the inference engine optimized for the A64FX architecture. The provided script handles
different compiler and BLAS library combinations.

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

Collects full model responses for all prompt categories to enable qualitative assessment and human
evaluation of output coherence and accuracy.

```console
$ sbatch quality-test.sh
```

### Memory Mapping (mmap) Evaluation

Assess the impact of memory mapping on latency and memory usage. This helps determine whether
loading the model into RAM or using disk-backed mapping is more efficient for the A64FX memory
subsystem.

```console
$ sbatch mmap-test.sh
```

### Multi-threading Scaling

Analyze how inference performance scales with the number of threads and NUMA policies. This test
evaluates the optimal thread count for the ARM-based A64FX cores.

```console
& sbatch threading-test.sh
```

## Statistical Analysis and Visualization

Once all jobs are completed, use the Python scripts to process the raw data. These scripts generate
the tables with the data used in the research report.

The analysis is divided into four main areas:

 - Warmup & Stability:   `warmup-analysis.py`
 - Compiler Performance: `compiler-analysis.py`
 - Memory Management:    `mmap-analysis.py`
 - Quantization Impact:  `quantization-analysis.py`
 - Threading Impact:     `threading-analysis.py`

```console
$ module load Python/3.14.2-GCCcore-15.2.0
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install duckdb
$ ./ANALYSIS-SCRIPT.py ../results/RESULTS_FOLDER
```
