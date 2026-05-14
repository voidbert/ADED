#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Performance model for CPU inference.
#
# Usage:
#     $ module load Python/3.14.2-GCCcore-15.2.0
#     $ ./performance_model.py --help
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
# CONFIGURATION ------------------------------------------------------------------------------------

from dataclasses import dataclass
from typing import Optional, Literal
import argparse
import math

FitMethod = Literal["none", "mse", "geomean"]

@dataclass
class Model:
    """Describes a quantized LLM for the bandwidth model."""
    name:     str
    n_params: int   # total parameter count
    bpw:      float # effective bits per weight

    def memory_bytes(self) -> float:
        """Bytes of weights streamed per token."""
        return self.n_params * self.bpw / 8.0

    def memory_gb(self) -> float:
        """Weights in GB (binary, GiB)."""
        return (self.memory_bytes() / (1024 ** 3))

@dataclass
class Measurement:
    """One observed data point."""
    model: Model
    observed_tpot_ms: float # measured time per output token, in ms

# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------

def predicted_tpot_ms(model: Model, bandwidth_gbs: float, k: float = 1.0) -> float:
    """
    Predicted TPOT in milliseconds.

    Args:
        model: the Model under test.
        bandwidth_gbs: peak (or effective) memory bandwidth in GB/s
                       using decimal GB (10^9), matching STREAM convention.
        k: overhead multiplier. k=1.0 gives the theoretical lower bound;
           k>1.0 scales it up to match observed values.

    Returns:
        Predicted TPOT in ms.
    """
    if k <= 0:
        raise ValueError("k must be positive")

    # Convert weights from binary GiB to decimal GB to match STREAM units.
    # STREAM typically reports GB/s in decimal (10^9 bytes/s).
    bytes_per_token = model.memory_bytes()
    bandwidth_bps   = bandwidth_gbs * 1e9

    # 1.1 factor to account for KV cache and runtime buffers
    seconds_per_token = (bytes_per_token * 1.1) / bandwidth_bps
    return seconds_per_token * 1000.0 * k + 0.5

# ---------------------------------------------------------------------------
# Fitting the "magic constant" k by geometric mean of factors
# ---------------------------------------------------------------------------

def fit_k_geomean(measurements: list[Measurement], bandwidth_gbs: float) -> float:
    """
    Fits a single overhead multiplier k across all measurements
    by least squares in log space (geometric mean of per-point ratios).

    For each measurement:
        observed_tpot = k_i * ideal_tpot
        k_i = observed_tpot / ideal_tpot

    Returns the geometric mean of k_i.
    """
    if not measurements:
        raise ValueError("need at least one measurement to fit k")

    log_ks = []
    for m in measurements:
        ideal = predicted_tpot_ms(m.model, bandwidth_gbs, k=1.0)
        k_i   = m.observed_tpot_ms / ideal
        log_ks.append(math.log(k_i))

    return math.exp(sum(log_ks) / len(log_ks))

# ---------------------------------------------------------------------------
# Fitting the "magic constant" k by MSE
# ---------------------------------------------------------------------------

def fit_k_mse(measurements: list[Measurement], bandwidth_gbs: float) -> float:
    """
    Fits k by ordinary least squares (minimizes MSE in linear space).

    Closed-form solution for the model obs_i = k * ideal_i:
        k* = sum(ideal_i * obs_i) / sum(ideal_i^2)
    """
    if not measurements:
        raise ValueError("need at least one measurement to fit k")

    num = 0.0
    den = 0.0
    for m in measurements:
        ideal = predicted_tpot_ms(m.model, bandwidth_gbs, k=1.0)
        num += ideal * m.observed_tpot_ms
        den += ideal * ideal

    return num / den

# ---------------------------------------------------------------------------
# Error metrics
# ---------------------------------------------------------------------------

def mse(measurements: list[Measurement], bandwidth_gbs: float, k: float) -> float:
    """Mean squared error in ms² for a given k."""
    total = 0.0
    for m in measurements:
        pred = predicted_tpot_ms(m.model, bandwidth_gbs, k)
        total += (pred - m.observed_tpot_ms) ** 2
    return total / len(measurements)

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(measurements: list[Measurement],
           bandwidth_gbs: float,
           fit: FitMethod = "none",
           k: Optional[float] = None) -> None:
    """
    Prints a comparison table.

    Args:
        measurements: list of observations.
        bandwidth_gbs: peak memory bandwidth in GB/s.
        fit: how to determine k.
            "none"    -> use the theoretical floor (k=1.0) unless k is given.
            "mse"     -> fit k by minimizing mean squared error (linear LS).
            "geomean" -> fit k by geometric mean (log-space LS).
        k: optional explicit k. If provided, overrides `fit`.
    """
    if k is not None:
        print(f"Using provided k: {k:.4f}\n")
    elif fit == "none":
        k = 1.0
        print("Using theoretical floor (k = 1.0, no fitting)\n")
    elif fit == "mse":
        k = fit_k_mse(measurements, bandwidth_gbs)
        print(f"Fitted multiplier k by MSE minimization: {k:.4f}\n")
    elif fit == "geomean":
        k = fit_k_geomean(measurements, bandwidth_gbs)
        print(f"Fitted multiplier k by geometric mean: {k:.4f}\n")
    else:
        raise ValueError(f"unknown fit method: {fit!r}")

    header = (f"{'Model':<35} {'Mem (GiB)':>10} "
              f"{'Pred (ms)':>10} {'Obs (ms)':>10} "
              f"{'Ratio':>8} {'Err %':>8}")
    print(header)
    print("-" * len(header))

    for m in measurements:
        pred  = predicted_tpot_ms(m.model, bandwidth_gbs, k)
        ideal = predicted_tpot_ms(m.model, bandwidth_gbs, 1.0)
        ratio = m.observed_tpot_ms / ideal
        err   = abs(pred - m.observed_tpot_ms) / m.observed_tpot_ms * 100
        print(f"{m.model.name:<35} {m.model.memory_gb():>10.3f} "
              f"{pred:>10.3f} {m.observed_tpot_ms:>10.3f} "
              f"{ratio:>8.2f} {err:>8.2f}")

    print(f"\nMSE = {mse(measurements, bandwidth_gbs, k):.3f} ms²")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compare predicted vs observed TPOT under the "
                    "bandwidth-roofline model."
    )
    parser.add_argument(
        "fit",
        nargs="?",
        default="none",
        choices=["none", "mse", "geomean"],
        help="Fitting method for the overhead multiplier k. "
             "'none' uses the theoretical floor (k=1). "
             "'mse' minimizes mean squared error. "
             "'geomean' minimizes squared relative error. "
             "(default: none)"
    )
    parser.add_argument(
        "--bandwidth", "-b",
        type=float,
        default=818.0,
        help="Peak memory bandwidth in GB/s (default: 818.0)"
    )
    parser.add_argument(
        "--k",
        type=float,
        default=None,
        help="Explicit k value. If provided, overrides the fit method."
    )
    args = parser.parse_args()

    BPW = {
        "Q3_K_M": 3,
        "Q4_K_M": 4,
        "Q8_0":   8,
    }

    llama = lambda quant: Model(
        name=f"llama-3.1-8b-instruct {quant}",
        n_params=8*(10**9),
        bpw=BPW[quant],
    )

    gemma = lambda quant: Model(
        name=f"gemma-3-4b-instruct {quant}",
        n_params=4*(10**9),
        bpw=BPW[quant],
    )

    smollm = lambda quant: Model(
        name=f"smollm-2-135m-instruct {quant}",
        n_params=135*(10**6),
        bpw=BPW[quant],
    )

    measurements = [
        Measurement(llama("Q3_K_M"),  observed_tpot_ms=63.4),
        Measurement(llama("Q4_K_M"),  observed_tpot_ms=75.5),
        Measurement(llama("Q8_0"),    observed_tpot_ms=76.7),
        Measurement(gemma("Q3_K_M"),  observed_tpot_ms=48),
        Measurement(gemma("Q4_K_M"),  observed_tpot_ms=53.2),
        Measurement(gemma("Q8_0"),    observed_tpot_ms=50.3),
        Measurement(smollm("Q3_K_M"), observed_tpot_ms=9.4),
        Measurement(smollm("Q4_K_M"), observed_tpot_ms=9.7),
        Measurement(smollm("Q8_0"),   observed_tpot_ms=10.2),
    ]

    report(measurements, args.bandwidth, fit=args.fit, k=args.k)

if __name__ == "__main__":
    main()
