SELECT LOWER(t.owner)            AS schema
,      LOWER(t.table_name)       AS name
,      SUBSTR(t.partitioned,1,1) AS partitioned
FROM   all_tables t
WHERE (t.table_name NOT LIKE 'DR%' AND t.table_name NOT LIKE 'BIN$%' AND t.table_name NOT LIKE 'MLOG$%')
AND NOT EXISTS (SELECT mview_name FROM all_mviews WHERE owner = t.table_name AND mview_name = t.table_name)
AND   t.temporary != 'Y'
AND   t.owner NOT IN ('SYS','SYSTEM','DBSNMP','DVSYS','MDSYS','OJVMSYS','OLAPSYS','WMSYS','XDB')
