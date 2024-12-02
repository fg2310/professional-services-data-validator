SELECT trigger_schema::text     AS schema
,      trigger_name::text       AS name
,      event_object_table::text AS tablename
FROM   information_schema.triggers
WHERE  trigger_schema::text NOT IN ('pg_catalog','pg_toast')
