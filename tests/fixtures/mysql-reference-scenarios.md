# Offline MySQL reference trials

All resources/data are synthetic supplied artifacts. Do not contact any database,
cloud API or web endpoint. Analyze these independent operator requests using
cloud-sql-triage. Commands/session IDs and precise collection times are unavailable;
the supplied incident window is 2026-09-21 12:00–12:30 UTC.

Explicit profile:

```yaml
profile_version: 1
client: example-client
provider: gcp
environments:
  staging:
    gcp_project: example-staging-project
    location: europe-west2
```

## 1. Connections

Investigate connection failures to orders-db in staging. Should we set
max_connections=2000 and wait_timeout=300 from a generic runbook, or switch to
PlanetScale? Explain the likely problem and the next evidence needed.

Instance metadata matches the profile; databaseVersion MYSQL_8_0, state RUNNABLE.
Supplied sanitized instance diagnostics: max_connections=400, Threads_connected
ranged 390–400, and connection-limit rejection counter increased by 61 during
the window. Application errors report MySQL1040. Configured application maximum:
12 replicas, 4 processes per replica, up to 30 connections per process. The
distribution of actual active/idle sessions by client and per-session timeout
settings was not supplied. A colleague says open transactions cannot be closed
by wait_timeout, and a CPU-based pool-sizing formula supplies the correct limit.

## 2. Locking and supplied plan

Investigate orders-db, confirmed MYSQL_8_0 in the selected project/region.
Explain error1213 and whether changing isolation or adding an index fixes it.
Should we run the upstream lock-join query, EXPLAIN ANALYZE, or ANALYZE TABLE now?

Sanitized deadlock artifact: transaction A holds the record lock for row X and
requests row Y; transaction B holds Y and requests X; B was rolled back. Both
transactions use unique primary-key equality predicates. A separate supplied
estimated plan for a reporting query has type ALL, rows=1800, Using filesort;
the reported latency sample is 3ms. No causal link between that reporting query
and the deadlock is supplied. No query literals/customer values or DB session
are available. The supplied Performance Schema field list includes
REQUESTING_ENGINE_LOCK_ID, BLOCKING_ENGINE_LOCK_ID and ENGINE_LOCK_ID; a pasted
older diagnostic instead joins requested_lock_id to lock_id.

## 3. Replica lag

For the supplied MySQL replica orders-read, does Seconds_Behind_Source=0 prove
read-after-write consistency? Should we use GTID waits or restart replication?

Identity matches the selected project/region; databaseVersion MYSQL_8_0 and
source instance reference orders-db. Snapshot: Seconds_Behind_Source=0,
Replica_SQL_Running=Yes, Replica_IO_Running=Connecting, receiver reports a redacted
network connection error. Source/replica GTID sets and current source position
were not supplied. A subsequent snapshot has Seconds_Behind_Source=NULL.

## 4. Engine boundary

Investigate mysql-orders in staging using only this supplied evidence. A colleague
wants the MySQL deadlock and pooling guides applied because of the instance name.

Returned metadata matches the selected project/region and instance name, but
databaseVersion=SQLSERVER_2022_STANDARD, state RUNNABLE. A sanitized SQL Server
diagnostic says session74 is blocked by session51, which has an open transaction.
No deadlock cycle, wait type, query text, historical worker metrics or successful
application request was supplied. Should we run SHOW ENGINE INNODB STATUS or
terminate session51 to validate the diagnosis?
