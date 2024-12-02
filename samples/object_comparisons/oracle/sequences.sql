SELECT LOWER(sequence_owner) AS schema
,      LOWER(sequence_name)  AS name
FROM   all_sequences
WHERE  sequence_owner NOT IN ('SYS','SYSTEM','DBSNMP','DVSYS','MDSYS','OJVMSYS','OLAPSYS','WMSYS','XDB')
