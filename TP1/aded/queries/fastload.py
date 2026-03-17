# ABOUT --------------------------------------------------------------------------------------------
#
# SinglePass query implementation with additional dataset loading optimizations.
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

import pyspark.sql.functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType, TimestampType
)

from aded.contexts import Context, SparkContext
from aded.queries.singlepass import SinglePass

class FastLoad(SinglePass):
    def load_dataset(self, context: Context, dataset_path: str) -> None:
        # Get Spark session from context
        assert isinstance(context, SparkContext)
        spark = context.spark

        # Define data frame schema
        schema = StructType([
            StructField('JobID',         StringType(),    False),
            StructField('JobIDRaw',      IntegerType(),   False),
            StructField('ElapsedRaw',    IntegerType(),   False),
            StructField('Account',       StringType(),    False),
            StructField('AllocCPUS',     IntegerType(),   False),
            StructField('CPUTimeRAW',    LongType(),      False),
            StructField('NNodes',        IntegerType(),   False),
            StructField('AllocNodes',    StringType(),    False),
            StructField('NCPUS',         IntegerType(),   False),
            StructField('Partition',     StringType(),    False),
            StructField('TotalCPU',      TimestampType(), False),
            StructField('User',          StringType(),    False),
            StructField('ExitCode',      StringType(),    False),
            StructField('State',         StringType(),    False),
            StructField('Reservation',   StringType(),    True),
            StructField('ReservationId', StringType(),    True),
            StructField('AllocTRES',     StringType(),    True),
        ])

        # Load dataset files in parallel
        self.data = spark.read.csv(dataset_path, sep='|', header=True, schema=schema) \
                              .withColumn(
                                  'Period',
                                  F.regexp_extract(F.input_file_name(), r'jobs_([^\.]+)\..*', 1)
                              ).withColumn(
                                  'COMPLETED',
                                  F.when(
                                      F.col('State') == 'COMPLETED',
                                      'COMPLETED'
                                  ).otherwise(
                                      'FAILED'
                                  )
                              )
