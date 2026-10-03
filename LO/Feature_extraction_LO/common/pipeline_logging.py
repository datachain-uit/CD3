import logging
import os
import platform
import sys
import time
import json
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp_utc": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "processor": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event_type"):
            payload["event"] = record.event_type
        if hasattr(record, "event_data"):
            payload["data"] = record.event_data
        return json.dumps(payload, ensure_ascii=False)


class JsonBufferHandler(logging.Handler):
    """Keep JSONL records until they can be persisted through Databricks."""

    def __init__(self):
        super().__init__()
        self.records: list[str] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


def get_logger(name: str, log_dir_path: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(getattr(handler, "_pipeline_console_handler", False) for handler in logger.handlers):
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler._pipeline_console_handler = True
        logger.addHandler(console_handler)


    # Notebook sessions keep Python loggers alive. Replace a prior managed
    # buffer so each notebook execution gets a separate JSONL run log.
    for handler in list(logger.handlers):
        if getattr(handler, "_pipeline_json_buffer", False):
            logger.removeHandler(handler)

    output_base = os.environ.get("TEMPO_OUTPUT_BASE", "preprocessed").rstrip("/")
    default_log_dir = log_dir_path or f"{output_base}/logs"
    configured_log_dir = os.environ.get("PIPELINE_LOG_DIR", default_log_dir)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_%f")
    logger._pipeline_log_path = f"{configured_log_dir.rstrip('/')}/{name}_{run_timestamp}.jsonl"
    buffer_handler = JsonBufferHandler()
    buffer_handler._pipeline_json_buffer = True
    logger.addHandler(buffer_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info("log_file=%s", logger._pipeline_log_path)
    return logger


def log_dataframe(logger: logging.Logger, label: str, df, distinct_columns=()) -> int:
    """Log aggregate DataFrame quality metrics only; never logs row-level values."""
    row_count = df.count()
    metrics = {"table": label, "rows": row_count}
    for column in distinct_columns:
        metrics[f"distinct_{column}"] = df.select(column).distinct().count()
    log_event(logger, "dataframe_metrics", **metrics)
    return row_count


def log_write(logger: logging.Logger, label: str, path: str, row_count: int) -> None:
    log_event(logger, "output_written", table=label, rows=row_count, path=path)


def write_parquet(df, path: str, single_file: bool = True) -> None:
    """Write one logical table, optionally as one Parquet part file.

    Spark always writes a directory containing metadata plus one or more
    ``part-*.parquet`` files.  ``single_file=True`` makes that directory have
    one data part, which is convenient for hand-off and inspection.  Use
    ``False`` for very large tables where distributed output is preferred.
    """
    writer_df = df.coalesce(1) if single_file else df
    writer_df.write.mode("overwrite").parquet(path)


def log_event(logger: logging.Logger, event: str, **data) -> None:
    logger.info(event, extra={"event_type": event, "event_data": data})


def flush_json_log(logger: logging.Logger, spark) -> None:
    """Persist buffered log lines to one real .jsonl file in a Volume.

    Direct Python file I/O on Serverless may target an ephemeral driver
    filesystem. DBUtils writes directly to the configured Volume instead.
    """
    handlers = [handler for handler in logger.handlers if getattr(handler, "_pipeline_json_buffer", False)]
    if not handlers:
        return

    path = getattr(logger, "_pipeline_log_path", None)
    if not path:
        return

    log_event(logger, "log_persisting", path=path)
    payload = "\n".join(line for handler in handlers for line in handler.records) + "\n"
    try:
        from pyspark.dbutils import DBUtils

        DBUtils(spark).fs.put(path, payload, overwrite=True)
    except Exception as error:
        # A Spark-backed fallback is still durable on Serverless. It creates a
        # directory whose name ends in .jsonl and contains one part file.
        fallback_path = f"{path}.spark_output"
        spark.createDataFrame([(payload,)], ["value"]).coalesce(1).write.mode("overwrite").text(fallback_path)
        logger.warning("DBUtils log write failed; saved Spark fallback at %s: %s", fallback_path, type(error).__name__)


def log_run_context(logger: logging.Logger, spark, processing_config: dict) -> None:
    """Log runtime metadata without assuming a JVM-backed Spark session.

    Databricks Serverless exposes Spark Connect, where ``sparkContext`` is not
    supported.  The unavailable values are recorded as null instead of making
    preprocessing fail just because logging is enabled.
    """
    safe_spark_configs = {}
    for key in (
        "spark.app.name",
        "spark.master",
        "spark.driver.memory",
        "spark.executor.memory",
        "spark.sql.session.timeZone",
    ):
        try:
            safe_spark_configs[key] = spark.conf.get(key)
        except Exception:
            safe_spark_configs[key] = None

    # Spark Connect / Databricks Serverless deliberately blocks sparkContext.
    # Keep these optional so the same scripts run on both Serverless and
    # Dedicated/classic Spark clusters.
    try:
        spark_context = spark.sparkContext
        spark_application_id = spark_context.applicationId
        spark_master = spark_context.master
    except Exception:
        spark_application_id = None
        spark_master = None

    try:
        pyspark_version = spark.version
    except Exception:
        pyspark_version = None

    log_event(
        logger,
        "run_context",
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        pyspark_version=pyspark_version,
        spark_application_id=spark_application_id,
        spark_master=spark_master,
        spark_config=safe_spark_configs,
        processing_config=processing_config,
    )


def start_run_timer() -> float:
    return time.perf_counter()


def log_run_finished(logger: logging.Logger, started_at: float) -> None:
    log_event(logger, "run_finished", duration_seconds=round(time.perf_counter() - started_at, 3))
