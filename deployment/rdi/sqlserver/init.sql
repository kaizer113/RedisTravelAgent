-- SQL Server 2022 Developer: source schema and SQL Agent CDC capture.
USE master;
GO
IF DB_ID(N'value_travel') IS NULL CREATE DATABASE value_travel;
GO
USE value_travel;
GO
IF OBJECT_ID(N'dbo.offers', N'U') IS NULL
CREATE TABLE dbo.offers (
  package_id VARCHAR(16) NOT NULL PRIMARY KEY,
  name NVARCHAR(160) NOT NULL,
  destination NVARCHAR(80) NOT NULL,
  total_price DECIMAL(10,2) NOT NULL CHECK (total_price >= 0),
  available_rooms INT NOT NULL CHECK (available_rooms >= 0),
  room_capacity INT NOT NULL CHECK (room_capacity BETWEEN 1 AND 20),
  eligible_reward_base DECIMAL(10,2) NOT NULL CHECK (eligible_reward_base >= 0),
  cancellation NVARCHAR(512) NOT NULL,
  departure_date VARCHAR(10) NOT NULL,
  data_label NVARCHAR(80) NOT NULL,
  updated_at DATETIME2(6) NOT NULL CONSTRAINT DF_offers_updated_at DEFAULT SYSUTCDATETIME()
);
GO
IF (SELECT is_cdc_enabled FROM sys.databases WHERE name = DB_NAME()) = 0
  EXEC sys.sp_cdc_enable_db;
GO
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE object_id = OBJECT_ID(N'dbo.offers') AND is_tracked_by_cdc = 1)
  EXEC sys.sp_cdc_enable_table @source_schema=N'dbo', @source_name=N'offers',
    @role_name=N'value_travel_cdc_reader', @supports_net_changes=0;
GO
EXEC sys.sp_cdc_change_job @job_type=N'capture', @pollinginterval=1;
-- CDC table enablement can create the job before SQL Agent starts it.
-- Restart only an active job, then wait for Agent's activity state to settle.
DECLARE @job_id UNIQUEIDENTIFIER = (
  SELECT job_id FROM msdb.dbo.cdc_jobs
  WHERE database_id = DB_ID() AND job_type = N'capture'
);
IF @job_id IS NULL THROW 51000, 'CDC capture job was not created.', 1;
DECLARE @deadline DATETIME2 = DATEADD(SECOND, 30, SYSUTCDATETIME());
IF EXISTS (
  SELECT 1 FROM msdb.dbo.sysjobactivity
  WHERE job_id = @job_id AND session_id = (SELECT MAX(session_id) FROM msdb.dbo.syssessions)
    AND start_execution_date IS NOT NULL AND stop_execution_date IS NULL
)
BEGIN
  EXEC sys.sp_cdc_stop_job @job_type=N'capture';
  WHILE EXISTS (
    SELECT 1 FROM msdb.dbo.sysjobactivity
    WHERE job_id = @job_id AND session_id = (SELECT MAX(session_id) FROM msdb.dbo.syssessions)
      AND start_execution_date IS NOT NULL AND stop_execution_date IS NULL
  )
  BEGIN
    IF SYSUTCDATETIME() > @deadline THROW 51001, 'CDC capture job did not stop within 30 seconds.', 1;
    WAITFOR DELAY '00:00:01';
  END;
END;
EXEC sys.sp_cdc_start_job @job_type=N'capture';
SET @deadline = DATEADD(SECOND, 30, SYSUTCDATETIME());
WHILE NOT EXISTS (
  SELECT 1 FROM msdb.dbo.sysjobactivity
  WHERE job_id = @job_id AND session_id = (SELECT MAX(session_id) FROM msdb.dbo.syssessions)
    AND start_execution_date IS NOT NULL AND stop_execution_date IS NULL
)
BEGIN
  IF SYSUTCDATETIME() > @deadline THROW 51002, 'CDC capture job did not start within 30 seconds. Check SQL Server Agent.', 1;
  WAITFOR DELAY '00:00:01';
END;
GO
