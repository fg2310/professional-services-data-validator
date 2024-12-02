SELECT LOWER(owner)      AS schema
,      LOWER(table_name) AS tablename
,      LOWER(columns)    AS columns
FROM (
    SELECT c.owner,c.table_name,c.constraint_name
    ,      LISTAGG(LOWER(cl.column_name),',') WITHIN GROUP (ORDER BY cl.position) AS columns
    FROM   all_constraints c
    INNER JOIN all_cons_columns cl ON (cl.owner = c.owner
                                       AND cl.constraint_name = c.constraint_name
                                       AND cl.table_name = c.table_name)
    WHERE c.constraint_type = 'P'
    AND   c.table_name NOT LIKE 'DR$%' AND c.table_name NOT LIKE 'BIN$%' AND c.table_name NOT LIKE 'MLOG$%'
    AND   c.owner NOT IN ('SYS','SYSTEM','DBSNMP','DVSYS','MDSYS','OJVMSYS','OLAPSYS','WMSYS','XDB')
    GROUP BY c.owner,c.table_name,c.constraint_name
)
