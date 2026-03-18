# ABOUT --------------------------------------------------------------------------------------------
#
# Hardware monitoring utilities.
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of Deucalion Job Query.
#
# Deucalion Job Query is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Deucalion Job Query is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Deucalion Job Query.
# If not, see <https://www.gnu.org/licenses/>.
#
# SOURCE FILE --------------------------------------------------------------------------------------

from __future__ import annotations
import dataclasses
import re

from aded import config, util

# Gets the number of seconds the CPU has been active since boot, normalized to the number of cores.
def get_working_cpu_time() -> float:
    num_cpus = util.get_online_cpus()
    with open('/proc/uptime', 'r') as f:
        numbers = [float(x) for x in f.read().split()]
        return (numbers[0] * num_cpus - numbers[1]) / num_cpus

# Disk usage statistics (logical and physical reads and writes)
@dataclasses.dataclass
class DiskStatistics:
    logical_read_bytes:     int = 0
    logical_written_bytes:  int = 0
    physical_read_bytes:    int = 0
    physical_written_bytes: int = 0

    def __sub__(self, other: object) -> DiskStatistics:
        if isinstance(other, DiskStatistics):
            return DiskStatistics(
                self.logical_read_bytes     - other.logical_read_bytes,
                self.logical_written_bytes  - other.logical_written_bytes,
                self.physical_read_bytes    - other.physical_read_bytes,
                self.physical_written_bytes - other.physical_written_bytes
            )

        return NotImplemented

# Parses process disk statistics from /proc/[pid]/io
def get_disk_statistics(pid: int | None) -> DiskStatistics | None:
    if not pid:
        return None

    disk_stats = DiskStatistics()
    with open(f'/proc/{pid}/io', 'r') as file:
        for line in file:
            match = re.match(r'(\w+):\s+(\d+)', line)
            if not match:
                continue

            key, value = match.group(1), int(match.group(2))
            match key:
                case 'rchar':
                    disk_stats.logical_read_bytes = value
                case 'wchar':
                    disk_stats.logical_written_bytes = value
                case 'read_bytes':
                    disk_stats.physical_read_bytes = value
                case 'write-bytes':
                    disk_stats.physical_written_bytes = value

    return disk_stats

# Network usage statistics (transmitted and received bytes and packets)
@dataclasses.dataclass
class NetStatistics:
    rx_bytes:   int = 0
    rx_packets: int = 0
    tx_bytes:   int = 0
    tx_packets: int = 0

    def __sub__(self, other: object) -> NetStatistics:
        if isinstance(other, NetStatistics):
            return NetStatistics(
                self.rx_bytes   - other.rx_bytes,
                self.rx_packets - other.rx_packets,
                self.tx_bytes   - other.tx_bytes,
                self.tx_packets - other.tx_packets
            )

        return NotImplemented

# Gets a network interface's usage statistics since boot
def get_net_statistics() -> NetStatistics | None:
    if not config.NETWORK_INTERFACE:
        return None

    # Helper for reading statistics files
    def read_net_statistics_file(name: str) -> int:
        with open(f'/sys/class/net/{config.NETWORK_INTERFACE}/statistics/{name}') as file:
            return int(file.read())

    # Load all files
    return NetStatistics(
        read_net_statistics_file('rx_bytes'), read_net_statistics_file('rx_packets'),
        read_net_statistics_file('tx_bytes'), read_net_statistics_file('tx_packets')
    )
