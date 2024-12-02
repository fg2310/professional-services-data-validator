SELECT owner        AS schema
,      trigger_name AS name
,      table_name   AS tablename
FROM   all_triggers
WHERE  owner NOT IN ('SYS','SYSTEM','DBSNMP','DVSYS','MDSYS','OJVMSYS','OLAPSYS','WMSYS','XDB')
