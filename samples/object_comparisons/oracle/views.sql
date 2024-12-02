SELECT LOWER(owner)     AS schema
,      LOWER(view_name) AS name
FROM   all_views
WHERE  owner NOT IN ('SYS','SYSTEM','DBSNMP','DVSYS','MDSYS','OJVMSYS','OLAPSYS','WMSYS','XDB')
