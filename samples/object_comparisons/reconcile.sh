#!/bin/bash
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


function show_usage {
  echo 'Usage: $0 <source-sql-directory> <target-sql-directory> [optional-file-name]'
}

if [[ "$1" = "-h" ]] || [[ "$1" = "--help" ]];then
  show_usage
  exit 0
fi

if [[ -z "$2" ]];then
  show_usage
  exit 1
fi

SOURCE_DIR=$1
TARGET_DIR=$2

if [[ -n "$3" ]];then
  FILES=$3
else
  FILES=$(ls -1 ${SOURCE_DIR})
fi

if [[ $? != 0 ]];then
  echo "Error listing files in directory: ${SOURCE_DIR}"
  exit 1
fi

SOURCE_CONN="ora_conn"
TARGET_CONN="pg_conn"
SCHEMA="pso_data_validator"

for FILE in $FILES;do
  echo "Processing file: ${FILE}"
  echo "cons_pk.sql cons_fk.sql cons_nn.sql" | grep -q -w ${FILE}
  if [[ $? = 0 ]];then
    KEYS="schema,tablename,columns"
  else
    KEYS="schema,name"
  fi
  if [[ ! -f "${TARGET_DIR}/${FILE}" ]];then
    echo "Skipping file because it does not exist in ${TARGET_DIR}"
    continue
  fi
  data-validation validate custom-query row -sc=${SOURCE_CONN} -tc=${TARGET_CONN} \
  -sqf="${SOURCE_DIR}/${FILE}" -tqf="${TARGET_DIR}/${FILE}" \
  --filters="schema = '${SCHEMA}'" \
  --primary-keys=${KEYS} --concat='*' \
  --filter-status=fail
done
