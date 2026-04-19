#!/bin/sh

# ABOUT --------------------------------------------------------------------------------------------
#
# Deucalion job for downloading and building various configurations of llama.cpp.
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of FastInference.
#
# FastInference is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# FastInference is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with FastInference. If
# not, see <https://www.gnu.org/licenses/>.
#
# SLURM PROPERTIES ---------------------------------------------------------------------------------
#
# General properties
#SBATCH --job-name=download-models
#SBATCH --time=04:00:00
#SBATCH --output=output-%j.out
#
# Run on ARM systems
#SBATCH --partition=dev-arm
#SBATCH --account=f202500010hpcvlabuminhoa
#
# Manage number of tasks
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#
# IMPLEMENTATION NOTES -----------------------------------------------------------------------------
#
#  - Attempts at compiling llama.cpp with FCC (both in traditional and in Clang mode) to use Fujitsu
#    BLAS failed, so only GCC and Clang builds are available.
#
#  - Attemps at compiling llama.cpp with OpenBLAS also failed due ILP64 interface incompatibilities,
#    so only BLIS builds are available.
#
# CONFIGURATION ------------------------------------------------------------------------------------

# Version of llama.cpp to download and build
LLAMA_CPP_VERSION='b8849'

# JOB ----------------------------------------------------------------------------------------------

# Remove previous llama.cpp installation
rm -rf ../llama.cpp 2> /dev/null

# Download llama.cpp
llama_tarball="$LLAMA_CPP_VERSION.tar.gz"
trap 'rm "/tmp/$llama_tarball" 2> /dev/null' HUP INT TERM QUIT EXIT
wget -qP '/tmp/' "https://github.com/ggml-org/llama.cpp/archive/refs/tags/$llama_tarball"

# Install llama.cpp and enter directory
tar xzf "/tmp/$llama_tarball" -C ..
mv "../llama.cpp-$LLAMA_CPP_VERSION" '../llama.cpp'
cd '../llama.cpp'

# Load GCC compiler and BLAS implementations
module purge
module load GCC/13.3.0
module load CMake/3.31.3-GCCcore-13.3.0
module load BLIS/1.0-GCC-13.3.0
export CC=gcc CXX=g++

# GCC 13.3.0 CPU-only build
cmake -B build-gcc-cpu
cmake --build build-gcc-cpu --config Release -j48

# GCC 13.3.0 BLIS build
cmake -B build-gcc-blis -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=FLAME
cmake --build build-gcc-blis --config Release -j48

# Load Clang compiler
module purge
module load LLVM/19.1.7-GCCcore-13.3.0
module load CMake/3.31.3-GCCcore-13.3.0
module load BLIS/1.0-GCC-13.3.0
export CC=clang CXX=clang++

# Clang 19.1.7 CPU-only build
cmake -B build-clang-cpu
cmake --build build-clang-cpu --config Release -j48

# Clang 19.1.7 BLIS build
cmake -B build-clang-blis -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=FLAME
cmake --build build-clang-blis --config Release -j48
