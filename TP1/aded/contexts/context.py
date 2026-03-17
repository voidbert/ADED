# ABOUT --------------------------------------------------------------------------------------------
#
# Spark and database reusable context abstractions.
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

from types import TracebackType

# Abstraction for a reusable Spark session or database connection.
class Context:
    # Method called between performance measurement runs that share the same context.
    # For instance, it is necessary to clean a database between runs.
    def between_runs_cleanup(self) -> None:
        pass

    # Method called after all query runs.
    def final_cleanup(self) -> None:
        pass

    # Method for context management (with-statement support)
    def __enter__(self) -> Context:
        return self

    # Method for context management (with-statement support)
    def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception_value: BaseException | None,
            traceback: TracebackType
        ) -> None:

        self.final_cleanup()

    # Gets the PID of the process whose disk activity should be monitored.
    def get_disk_monitoring_process_pid(self) -> int | None:
        return None
