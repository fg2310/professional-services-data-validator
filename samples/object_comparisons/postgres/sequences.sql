SELECT sequence_schema::text AS schema
,      sequence_name::text   AS name
FROM   information_schema.sequences
WHERE  sequence_schema::text NOT IN ('pg_catalog','pg_toast')
