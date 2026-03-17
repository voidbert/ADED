# ABOUT --------------------------------------------------------------------------------------------
#
# Abstraction for reusable DuckDB connection. This file is not named 'duckdb.py' not to shadow the
# duckdb module.
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

import duckdb
import os

from aded.contexts.context import Context

# Abstraction for reusable DuckDB connection.
class DuckDBContext(Context):
    def __init__(self, threads: int, **kwargs: object) -> None:
        # Initialize an in-memory database and use a set number of threads
        self.connection = duckdb.connect(':memory:')
        self.connection.execute(f'SET THREADS TO {threads}')

    def between_runs_cleanup(self) -> None:
        # Delete all views
        view_names = self.connection.execute('SELECT view_name FROM duckdb_views').fetchall()
        for view_name_tuple in view_names:
            self.connection.execute(f'DROP VIEW IF EXISTS {view_name_tuple[0]}')

    def final_cleanup(self) -> None:
        self.connection.close()

    def get_disk_monitoring_process_pid(self) -> int | None:
        return os.getpid()
