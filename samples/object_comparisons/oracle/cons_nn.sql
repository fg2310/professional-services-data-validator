SELECT LOWER(t.owner)            AS schema
,      LOWER(t.table_name)       AS tablename
,      LOWER(c.column_name)      AS columns
FROM   all_tables t
INNER JOIN  all_tab_columns c ON (t.owner = c.owner AND t.table_name = c.table_name)
WHERE (t.table_name NOT LIKE 'DR%' AND t.table_name NOT LIKE 'BIN$%' AND t.table_name NOT LIKE 'MLOG$%')
AND NOT EXISTS (SELECT mview_name FROM all_mviews WHERE owner = t.table_name AND mview_name = t.table_name)
AND   t.temporary != 'Y'
AND   t.owner NOT IN ('SYS','SYSTEM','DBSNMP','DVSYS','MDSYS','OJVMSYS','OLAPSYS','WMSYS','XDB')
AND   c.nullable = 'N'
