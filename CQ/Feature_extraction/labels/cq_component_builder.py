"""Build intermediate CQ components for the canonical label builder.

CQ v3 is deliberately separate from CQ v2.  It retains every enrollment for a
course with an observed course-specific timeline, while proxy-timeline courses
retain only enrollments with at least one video, problem, or comment event.
It applies non-compensatory floors, then computes the
recommended weighted geometric mean::

    G = COELO**0.4 * AFELO**0.2 * ACELO**0.4

The observed-timeline population is primary; an active-only proxy-timeline
population is appended for the hybrid scenario.  A complete ScoreStruct is
used as the primary assessment rubric after the explicit
mapping discussion -> comment, reading -> assignment/problem, and article
excluded.  When ScoreStruct is absent, the ``course_limit.csv`` assessment
weights are used as an explicit primary fallback and are recorded as such.

COELO follows the four source components used by ``Gold_label.py`` (scaled
watch duration, video watch ratio, scaled attempts and problem coverage).
AFELO combines scaled watch-count with the activity breadth signal, including
comments as the third observable behaviour type.

Problem score handling is event-level and provenance-aware: an observed
``score`` wins; when it is missing, ``is_correct`` plus a positive event
``full_score`` reconstructs either the full score or zero.  An unavailable
course denominator is never treated as a ratio of one, and unresolved events
are not imputed.
This internal module materializes COELO, AFELO, ACELO and G inputs. Do not
invoke it as a standalone label route; use ``python -m labels.build_cq_labels``.
"""
import sys
import os
from pathlib import Path

_file_path = globals().get("__file__")
if _file_path:
    PROJECT_ROOT = Path(_file_path).resolve().parents[1]
else:
    _configured_root = globals().get("PROJECT_ROOT") or os.environ.get("PROJECT_ROOT")
    PROJECT_ROOT = Path(_configured_root) if _configured_root else None
    if PROJECT_ROOT is None or not (PROJECT_ROOT / "common").is_dir():
        try:
            _notebook = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
            _workspace_path = Path("/Workspace") / _notebook.lstrip("/")
            PROJECT_ROOT = next(parent for parent in _workspace_path.parents if (parent / "common").is_dir())
        except Exception as error:
            _candidates = list(Path("/Workspace/Users").glob("*/CQ/Feature_extraction"))
            if len(_candidates) == 1 and (_candidates[0] / "common").is_dir():
                PROJECT_ROOT = _candidates[0]
            else:
                raise RuntimeError(
                    "Cannot locate CQ/Feature_extraction. Set job environment variable PROJECT_ROOT to "
                    "the absolute workspace directory containing common/."
                ) from error
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession, Window, functions as F

from common.pipeline_logging import (
    flush_json_log, get_logger, log_dataframe, log_event, log_run_context,
    log_run_finished, log_write, start_run_timer, write_parquet,
)
from common.protocol_config import load_protocol_config, path_from_config


PROTOCOL = load_protocol_config()
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]
ANALYSIS_BASE = path_from_config(PROTOCOL, "analysis_base")
LABEL_VERSION = "cq_personal_v3_source_coelo_afelo_comment_v2_input_score_mapping_floor5_v9_timeline_all_proxy_active"
COELO_FLOOR = 0.50
# ACELO is stored internally as a [0, 1] ratio.  The requested floor is 5.0
# on a 0--10 scale, hence 0.50 in the normalized representation.
ACELO_FLOOR_SCORE_10 = 5.0
ACELO_FLOOR = ACELO_FLOOR_SCORE_10 / 10.0
G_WEIGHT = {"COELO": 0.40, "AFELO": 0.20, "ACELO": 0.40}
# Grade-aligned provisional bands.  Keep these explicit until an external
# criterion (final grade or expert Angoff calibration) replaces them.
G_PASS = 0.60
G_GOOD = 0.70
G_EXCELLENT = 0.85

spark = SparkSession.builder.appName("build_cq_personal_v3_labels").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("build_cq_personal_v3_labels", f"{OUTPUT_BASE}/logs")
log_run_context(logger, spark, {
    "label_version": LABEL_VERSION,
    "grain": "enrollment_id_user_id_course_id",
    "population": "all_course_specific_timeline_enrollments__plus_active_proxy_timeline_enrollments",
    "timeline_population_policy": "all_enrollments_including_zero_activity",
    "no_timeline_population_policy": "active_enrollments_any_of_video_problem_comment_only",
    "floor_policy": "COELO>=0.50, ACELO>=5.0/10 (=0.50 normalized), behavior_types>=min(2,K)",
    "geometric_mean_weights": G_WEIGHT,
    "g_thresholds": {"pass": G_PASS, "good": G_GOOD, "excellent": G_EXCELLENT},
    "unobserved_assessment_policy": "discussion_to_comment__reading_to_assignment__article_excluded",
    "assessment_fallback_policy": "course_limit_weights_are_primary_fallback_when_score_structure_is_absent",
    "assessment_mapping_policy": "discussion_to_comment__reading_to_assignment__article_excluded",
    "single_modality_policy": "v2_structural_mask__renormalize_observed_modalities",
    "acelo_proxy_policy": "effective_course_weights__problem_score_falls_back_to_problem_progress__comment_presence_for_discussion",
    "problem_score_missing_policy": "score_observed_first__missing_score_is_correct_1_uses_event_full_score__is_correct_0_uses_zero__unresolved_remains_unresolved",
    "problem_score_denominator_policy": "course_full_score_required__never_assign_ratio_one_when_denominator_is_missing",
    "coelo_policy": "source_four_components__course_minmax_for_duration_and_attempts",
    "afelo_policy": "source_watch_count_plus_activity_breadth__video_problem_comment",
    "comment_input": "comment_v2/comment_events_clean__raw_presence_only",
})
started = start_run_timer()

enrollments = spark.read.parquet(f"{OUTPUT_BASE}/enrollments/")
problem_catalog = spark.read.parquet(f"{OUTPUT_BASE}/course_problem_catalog/")
videos = spark.read.parquet(f"{OUTPUT_BASE}/video_events_clean/").withColumn(
    "availability_time", F.col("event_time")
)
problems = spark.read.parquet(f"{OUTPUT_BASE}/problem_events_clean/")
if "availability_time" not in problems.columns:
    problems = problems.withColumn("availability_time", F.to_timestamp("submit_time"))
else:
    problems = problems.withColumn(
        "availability_time", F.coalesce(F.col("availability_time"), F.to_timestamp("submit_time"))
    )
# Problem scoring is automatic at submit time.  Keep the raw score for
# provenance, but create an effective event score for the cases where the
# source omitted ``score`` and retained only ``is_correct``.  The fallback is
# deliberately event-level: a course-level ratio still requires a valid
# course denominator from the problem catalog.
for required_column, data_type in (
    ("score", "double"),
    ("full_score", "double"),
    ("attempts", "double"),
):
    if required_column not in problems.columns:
        problems = problems.withColumn(required_column, F.lit(None).cast(data_type))
if "is_correct" not in problems.columns:
    problems = problems.withColumn("is_correct", F.lit(None).cast("string"))
problems = (
    problems.withColumn("score_num", F.col("score").cast("double"))
    .withColumn("event_full_score_num", F.col("full_score").cast("double"))
    .withColumn("attempts_num", F.col("attempts").cast("double"))
    .withColumn("is_correct_text", F.lower(F.trim(F.col("is_correct").cast("string"))))
    .withColumn(
        "is_correct_num",
        F.when(F.col("is_correct_text").isin("1", "true", "t", "yes", "y"), F.lit(1))
        .when(F.col("is_correct_text").isin("0", "false", "f", "no", "n"), F.lit(0))
        .otherwise(F.lit(None).cast("int")),
    )
    .withColumn(
        "effective_score",
        F.when(F.col("score_num").isNotNull(), F.col("score_num"))
        .when(
            (F.col("is_correct_num") == 1) & (F.col("event_full_score_num") > 0),
            F.col("event_full_score_num"),
        )
        .when(
            (F.col("is_correct_num") == 0) & (F.col("event_full_score_num") > 0),
            F.lit(0.0),
        ),
    )
    .withColumn(
        "effective_score_source",
        F.when(F.col("score_num").isNotNull(), F.lit("observed_score"))
        .when(
            F.col("is_correct_num").isNotNull() & (F.col("event_full_score_num") > 0),
            F.lit("is_correct_reconstructed"),
        )
        .otherwise(F.lit("unresolved_missing_score")),
    )
)
# Older problem-event materializations may not retain the joined event
# ``full_score``.  Recover it from the course/problem catalog before applying
# the is_correct rule, without changing the event grain.
catalog_event_scores = (
    problem_catalog.select(
        "course_id",
        "problem_id",
        F.col("full_score").cast("double").alias("catalog_full_score_for_event"),
    )
    .dropDuplicates(["course_id", "problem_id"])
)
problems = (
    problems.join(catalog_event_scores, ["course_id", "problem_id"], "left")
    .withColumn(
        "event_full_score_num",
        F.coalesce(F.col("event_full_score_num"), F.col("catalog_full_score_for_event")),
    )
    .withColumn(
        "effective_score",
        F.when(F.col("score_num").isNotNull(), F.col("score_num"))
        .when(
            (F.col("is_correct_num") == 1) & (F.col("event_full_score_num") > 0),
            F.col("event_full_score_num"),
        )
        .when(
            (F.col("is_correct_num") == 0) & (F.col("event_full_score_num") > 0),
            F.lit(0.0),
        ),
    )
    .withColumn(
        "effective_score_source",
        F.when(F.col("score_num").isNotNull(), F.lit("observed_score"))
        .when(
            F.col("is_correct_num").isNotNull() & (F.col("event_full_score_num") > 0),
            F.lit("is_correct_reconstructed"),
        )
        .otherwise(F.lit("unresolved_missing_score")),
    )
    .drop("catalog_full_score_for_event")
)
comments = spark.read.parquet(path_from_config(PROTOCOL, "comment_events_clean") + "/").withColumn(
    "availability_time", F.col("event_time")
)
course_summary = spark.read.parquet(f"{OUTPUT_BASE}/course_summary/")
score_structure = spark.read.parquet(f"{OUTPUT_BASE}/course_score_structure_summary/")
# Keep the label job readable while the mapped ScoreStruct summary is being
# rolled out.  A stale summary is upgraded in-memory with the same mapping;
# the persisted summary is still regenerated by process_course_score_structure.
if "score_weight_comment" not in score_structure.columns:
    discussion_column = "score_weight_discussion_raw" if "score_weight_discussion_raw" in score_structure.columns else "score_weight_discussion"
    score_structure = score_structure.withColumn(
        "score_weight_comment",
        F.coalesce(F.col(discussion_column), F.lit(0.0)),
    )
if "score_weight_article_excluded" not in score_structure.columns:
    article_column = "score_weight_article_raw" if "score_weight_article_raw" in score_structure.columns else "score_weight_article"
    if article_column in score_structure.columns:
        score_structure = score_structure.withColumn(
            "score_weight_article_excluded",
            F.coalesce(F.col(article_column), F.lit(0.0)),
        )
    else:
        score_structure = score_structure.withColumn("score_weight_article_excluded", F.lit(0.0))
if "score_weight_assignment_raw" not in score_structure.columns and "score_weight_reading" in score_structure.columns:
    score_structure = score_structure.withColumn(
        "score_weight_assignment",
        F.coalesce(F.col("score_weight_assignment"), F.lit(0.0))
        + F.coalesce(F.col("score_weight_reading"), F.lit(0.0)),
    )
# Discussion/reading are mapped above and article is intentionally excluded;
# no mapped component remains formally unobserved.
score_structure = score_structure.withColumn("score_weight_unobserved", F.lit(0.0))
# `course_score_structure_summary` is the authoritative assessment source when
# it is complete.  Its mapped fields implement the explicit policy:
# discussion -> comment, reading -> assignment/problem, and article excluded.
# Some courses do not have that metadata (or have no exam), so keep the course
# metadata weights as an explicit fallback instead of dropping the row.
fallback_weights = (
    spark.read.option("header", True).option("quote", '"').option("escape", '"').option("multiLine", True)
    .csv(f"{RAW_BASE}/course_limit.csv")
    .select(
        "course_id",
        F.coalesce(F.col("video").cast("double"), F.lit(0.0)).alias("fallback_video_weight"),
        F.coalesce(F.col("assignment").cast("double"), F.lit(0.0)).alias("fallback_assignment_weight"),
        F.coalesce(F.col("exam").cast("double"), F.lit(0.0)).alias("fallback_exam_weight"),
    )
    .dropDuplicates(["course_id"])
)
timeline_offerings = (
    spark.read.parquet(f"{ANALYSIS_BASE}/shifted_offering_assignments/")
    .select("enrollment_id", "offering_id", "offering_start_date", "offering_end_date")
    .withColumn("offering_source", F.lit("course_specific_timeline"))
)
anchored_offerings = (
    spark.read.parquet(f"{ANALYSIS_BASE}/enrollment_anchored_pseudo_offering_assignments/")
    .select(
        "enrollment_id",
        F.col("pseudo_offering_id").alias("offering_id"),
        F.col("pseudo_start_date").alias("offering_start_date"),
        F.col("pseudo_end_date").alias("offering_end_date"),
    )
    .withColumn("offering_source", F.lit("enrollment_anchored_proxy"))
    .join(timeline_offerings.select("enrollment_id"), "enrollment_id", "left_anti")
)
global_offerings = (
    spark.read.parquet(f"{ANALYSIS_BASE}/global_template_offering_assignments/")
    .select("enrollment_id", "offering_id", "offering_start_date", "offering_end_date")
    .withColumn("offering_source", F.lit("global_template_fallback"))
    .join(anchored_offerings.select("enrollment_id"), "enrollment_id", "left_anti")
)
offerings = timeline_offerings.unionByName(anchored_offerings).unionByName(global_offerings)

spine = (
    enrollments.select(
        "enrollment_id", "user_id", "course_id", F.to_timestamp("enroll_time").alias("enroll_time")
    )
    .join(offerings, "enrollment_id", "inner")
    .withColumn("offering_end_exclusive", F.to_timestamp(F.date_add("offering_end_date", 1)))
    .withColumn("label_availability_time", F.col("offering_end_exclusive"))
    .withColumn("label_availability_source", F.col("offering_source"))
)


def within_offering(events):
    return (
        events.join(
            spine.select("enrollment_id", F.col("enroll_time").alias("label_enroll_time"), "offering_end_exclusive"),
            "enrollment_id", "inner",
        )
        .filter(
            (F.col("availability_time") >= F.col("label_enroll_time"))
            & (F.col("availability_time") < F.col("offering_end_exclusive"))
        )
    )


video_final = within_offering(videos).withColumn(
    "watch_duration",
    F.greatest(
        (F.col("end_point") - F.col("start_point")).cast("double"),
        F.lit(0.0),
    ),
).groupBy("enrollment_id").agg(
    F.countDistinct("resource_id").alias("watched_video_count"),
    F.count("*").alias("video_event_count"),
    F.sum("watch_duration").alias("total_watch_duration"),
    F.max("availability_time").alias("video_last_available_time"),
)
problem_final = within_offering(problems).groupBy("enrollment_id").agg(
    F.count("*").alias("problem_event_count"),
    F.countDistinct("problem_id").alias("problem_count"),
    F.sum(F.coalesce(F.col("attempts_num"), F.lit(0.0))).alias("attempts_sum"),
    # ``score_sum`` is the effective sum: observed score first, then the
    # deterministic is_correct reconstruction.  Unresolved events are not
    # silently converted into points.
    F.sum("effective_score").alias("score_sum"),
    F.sum(F.when(F.col("score_num").isNotNull(), F.lit(1)).otherwise(F.lit(0))).alias(
        "score_observed_count"
    ),
    F.sum(
        F.when(
            F.col("effective_score_source") == "is_correct_reconstructed", F.lit(1)
        ).otherwise(F.lit(0))
    ).alias("score_reconstructed_count"),
    F.sum(F.when(F.col("effective_score").isNotNull(), F.lit(1)).otherwise(F.lit(0))).alias(
        "score_effective_count"
    ),
    F.sum(
        F.when(
            F.col("effective_score_source") == "unresolved_missing_score", F.lit(1)
        ).otherwise(F.lit(0))
    ).alias("unresolved_missing_score_count"),
    F.sum(F.when(F.col("is_correct_num").isNotNull(), F.lit(1)).otherwise(F.lit(0))).alias(
        "is_correct_observed_count"
    ),
    F.sum(F.when(F.col("is_correct_num") == 1, F.lit(1)).otherwise(F.lit(0))).alias(
        "is_correct_true_count"
    ),
    F.sum(F.when(F.col("is_correct_num") == 0, F.lit(1)).otherwise(F.lit(0))).alias(
        "is_correct_false_count"
    ),
    F.max("availability_time").alias("problem_last_available_time"),
)
comment_final = within_offering(comments).groupBy("enrollment_id").agg(
    F.count("*").alias("comment_count"), F.max("availability_time").alias("comment_last_available_time")
)

# A course with an observed timeline is evaluated over every enrollment, just
# like LO: zero activity is a meaningful learner outcome and must not be
# silently removed.  For a course without a timeline, the pseudo schedule is
# only an analytical proxy, so retain the established active-only population.
# Comment-only participation is activity too because comments are now used by
# AFELO/ACELO; excluding it would contradict the label definition.
active_cohort = (
    video_final.select("enrollment_id")
    .unionByName(problem_final.select("enrollment_id"))
    .unionByName(comment_final.select("enrollment_id"))
    .distinct()
)
timeline_population = (
    spine.filter(F.col("offering_source") == F.lit("course_specific_timeline"))
    .withColumn("cq_population_group", F.lit("timeline_all_enrollments"))
)
proxy_population = (
    spine.filter(F.col("offering_source") != F.lit("course_specific_timeline"))
    .join(active_cohort.withColumn("cq_active_event_any", F.lit(1)), "enrollment_id", "inner")
    .withColumn("cq_population_group", F.lit("no_timeline_active_enrollments"))
)
# Spark has no useful empty `isin` expression.  Mark activity explicitly after
# the left join so timeline rows preserve both active and zero-activity cases.
timeline_population = (
    timeline_population.join(active_cohort.withColumn("cq_active_event_any", F.lit(1)), "enrollment_id", "left")
    .withColumn("cq_active_event_any", F.coalesce(F.col("cq_active_event_any"), F.lit(0)))
)
population_spine = timeline_population.unionByName(proxy_population)

problem_totals = problem_catalog.groupBy("course_id").agg(
    F.countDistinct("problem_id").alias("course_problem_count"),
    F.sum(F.col("full_score").cast("double")).alias("course_full_score"),
)
base = (
    population_spine.join(video_final, "enrollment_id", "left")
    .join(problem_final, "enrollment_id", "left")
    .join(comment_final, "enrollment_id", "left")
    .join(course_summary.select("course_id", "video_counts"), "course_id", "left")
    .join(problem_totals, "course_id", "left")
    .join(score_structure, "course_id", "left")
    .join(fallback_weights, "course_id", "left")
    .withColumn("has_video_catalog", (F.coalesce(F.col("video_counts"), F.lit(0)) > 0).cast("int"))
    .withColumn("has_problem_catalog", (F.coalesce(F.col("course_problem_count"), F.lit(0)) > 0).cast("int"))
    .withColumn("problem_event_count", F.coalesce(F.col("problem_event_count"), F.lit(0)))
    .withColumn("score_observed_count", F.coalesce(F.col("score_observed_count"), F.lit(0)))
    .withColumn("score_reconstructed_count", F.coalesce(F.col("score_reconstructed_count"), F.lit(0)))
    .withColumn("score_effective_count", F.coalesce(F.col("score_effective_count"), F.lit(0)))
    .withColumn(
        "unresolved_missing_score_count",
        F.coalesce(F.col("unresolved_missing_score_count"), F.lit(0)),
    )
    .withColumn("is_correct_observed_count", F.coalesce(F.col("is_correct_observed_count"), F.lit(0)))
    .withColumn("is_correct_true_count", F.coalesce(F.col("is_correct_true_count"), F.lit(0)))
    .withColumn("is_correct_false_count", F.coalesce(F.col("is_correct_false_count"), F.lit(0)))
    .withColumn(
        "problem_score_effective_available",
        (
            (F.coalesce(F.col("course_full_score"), F.lit(0.0)) > 0)
            & (F.col("score_effective_count") > 0)
            & (F.col("unresolved_missing_score_count") == 0)
        ).cast("int"),
    )
    .withColumn(
        "problem_score_source",
        F.when(F.col("has_problem_catalog") == 0, F.lit("missing_problem_catalog"))
        .when(
            F.coalesce(F.col("course_full_score"), F.lit(0.0)) <= 0,
            F.lit("missing_full_score_denominator"),
        )
        .when(F.col("problem_event_count") == 0, F.lit("no_problem_event"))
        .when(
            F.col("unresolved_missing_score_count") > 0,
            F.lit("unresolved_score_remains"),
        )
        .when(
            (F.col("score_reconstructed_count") > 0)
            & (F.col("score_observed_count") > 0),
            F.lit("mixed_observed_and_is_correct"),
        )
        .when(F.col("score_reconstructed_count") > 0, F.lit("is_correct_reconstructed"))
        .when(F.col("score_effective_count") > 0, F.lit("observed_score"))
        .otherwise(F.lit("unresolved_missing_score")),
    )
    .withColumn(
        "course_modality",
        F.when((F.col("has_video_catalog") == 1) & (F.col("has_problem_catalog") == 1), F.lit("video_problem"))
        .when(F.col("has_video_catalog") == 1, F.lit("video_only"))
        .when(F.col("has_problem_catalog") == 1, F.lit("problem_only"))
        .otherwise(F.lit("none")),
    )
    .withColumn("has_score_structure_flag", F.coalesce(F.col("has_score_structure"), F.lit(0)).cast("int"))
    # Prefer the formal structure; otherwise use course_limit metadata as a
    # proxy.  A missing exam is not an error: its weight is simply zero and the
    # assignment/problem weight remains valid.
    .withColumn(
        "configured_video_weight",
        F.when(
            F.col("has_score_structure_flag") == 1,
            F.coalesce(F.col("score_weight_video"), F.lit(0.0)),
        ).otherwise(F.coalesce(F.col("fallback_video_weight"), F.lit(0.0))),
    )
    .withColumn(
        "configured_problem_weight",
        F.when(
            F.col("has_score_structure_flag") == 1,
            F.coalesce(F.col("score_weight_assignment"), F.lit(0.0)),
        ).otherwise(
            F.coalesce(F.col("fallback_assignment_weight"), F.lit(0.0))
            + F.coalesce(F.col("fallback_exam_weight"), F.lit(0.0))
        ),
    )
    .withColumn(
        "configured_comment_weight",
        F.when(
            F.col("has_score_structure_flag") == 1,
            F.coalesce(F.col("score_weight_comment"), F.lit(0.0)),
        ).otherwise(F.lit(0.0)),
    )
    # ACELO is an assessment-completion construct: only video and problem are
    # assessment modalities.  Comment participation belongs exclusively to
    # AFELO, so retain its configured value as provenance but exclude it from
    # every ACELO weight, denominator, availability rule, and score.
    .withColumn(
        "configured_weight_total",
        F.col("configured_video_weight") + F.col("configured_problem_weight"),
    )
    # Structural-mask rule: a course with only video or only problem is
    # scored on the modality it actually offers; the absent modality is not a
    # zero and does not make ACELO undefined.
    .withColumn(
        "observed_configured_video_weight",
        F.col("configured_video_weight") * F.col("has_video_catalog"),
    )
    .withColumn(
        "observed_configured_problem_weight",
        F.col("configured_problem_weight") * F.col("has_problem_catalog"),
    )
    .withColumn("observed_configured_comment_weight", F.lit(0.0))
    .withColumn(
        "observed_configured_weight_total",
        F.col("observed_configured_video_weight")
        + F.col("observed_configured_problem_weight"),
    )
    .withColumn(
        "assessment_weight_coverage",
        F.when(
            F.col("configured_weight_total") > 0,
            F.try_divide(F.col("observed_configured_weight_total"), F.col("configured_weight_total")),
        ),
    )
    .withColumn(
        "effective_video_weight",
        F.when(
            F.col("observed_configured_weight_total") > 0,
            F.col("observed_configured_video_weight"),
        ).otherwise(
            F.when(F.col("has_video_catalog") == 1, F.lit(1.0)).otherwise(F.lit(0.0))
        ),
    )
    .withColumn(
        "effective_problem_weight",
        F.when(
            F.col("observed_configured_weight_total") > 0,
            F.col("observed_configured_problem_weight"),
        ).otherwise(
            F.when(F.col("has_problem_catalog") == 1, F.lit(1.0)).otherwise(F.lit(0.0))
        ),
    )
    .withColumn("effective_comment_weight", F.lit(0.0))
    .withColumn(
        "effective_weight_total",
        F.col("effective_video_weight") + F.col("effective_problem_weight"),
    )
    .withColumn(
        "assessment_weight_source",
        F.when(
            (F.col("has_score_structure_flag") == 1)
            & (F.col("configured_weight_total") <= 0),
            F.lit("score_structure_no_mapped_component"),
        )
        .when(
            (F.col("has_score_structure_flag") == 1)
            & (F.col("configured_weight_total") > 0),
            F.lit("score_structure"),
        )
        .when(
            (F.col("has_score_structure_flag") == 0)
            & (F.col("configured_weight_total") > 0)
            & (F.col("effective_weight_total") > 0),
            F.lit("course_limit_fallback"),
        )
        .when(
            (F.col("has_score_structure_flag") == 0)
            & (F.col("configured_weight_total") > 0),
            F.lit("course_limit_fallback_missing_catalog"),
        )
        .when(F.col("effective_weight_total") > 0, F.lit("equal_observed_modalities")),
    )
    # Ratios are bounded progress measures.  Bad/negative source scores must
    # not create negative COELO/ACELO values or make geometric powers invalid.
    .withColumn("video_watch_ratio", F.greatest(F.lit(0.0), F.least(F.lit(1.0), F.coalesce(F.try_divide("watched_video_count", "video_counts"), F.lit(0.0)))))
    .withColumn("problem_id_ratio", F.greatest(F.lit(0.0), F.least(F.lit(1.0), F.coalesce(F.try_divide("problem_count", "course_problem_count"), F.lit(0.0)))))
    .withColumn(
        "problem_score_ratio",
        F.when(
            F.col("problem_score_effective_available") == 1,
            F.greatest(
                F.lit(0.0),
                F.least(
                    F.lit(1.0),
                    F.coalesce(F.try_divide("score_sum", "course_full_score"), F.lit(0.0)),
                ),
            ),
        ).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "problem_score_observed",
        (
            (F.coalesce(F.col("course_full_score"), F.lit(0.0)) > 0)
            & (F.coalesce(F.col("score_observed_count"), F.lit(0)) > 0)
        ).cast("int"),
    )
    .withColumn(
        "problem_score_reconstructed",
        (
            (F.col("problem_score_effective_available") == 1)
            & (F.col("score_reconstructed_count") > 0)
        ).cast("int"),
    )
    .withColumn(
        "problem_progress_proxy",
        F.when(F.col("has_problem_catalog") == 0, F.lit(None).cast("double"))
        .when(
            F.col("problem_score_effective_available") == 1,
            (F.col("problem_id_ratio") + F.col("problem_score_ratio")) / F.lit(2.0),
        )
        .otherwise(F.col("problem_id_ratio")),
    )
.withColumn("video_event_present", F.coalesce((F.col("video_event_count") > 0).cast("int"), F.lit(0)))
.withColumn("problem_event_present", F.coalesce((F.col("problem_count") > 0).cast("int"), F.lit(0)))
.withColumn("comment_event_present", F.coalesce((F.col("comment_count") > 0).cast("int"), F.lit(0)))
    .withColumn(
        # Discussion is represented by the cleaned comment stream.  The
        # current source has no discussion-item denominator, so use observed
        # comment participation as the bounded completion proxy.
        "comment_progress_ratio",
        F.when(
            F.col("configured_comment_weight") > 0,
            F.col("comment_event_present").cast("double"),
        ).otherwise(F.lit(0.0)),
    )
)

# Gold_label.py min--max scales duration, watch count and attempts inside a
# course/chapter.  Chapters are not available in this learner-course table, so
# the faithful adaptation uses course-level windows.  A zero value means that
# no corresponding event was observed for this enrollment.
course_window = Window.partitionBy("course_id")
scaled = (
    base
    .withColumn("watch_duration_value", F.coalesce(F.col("total_watch_duration"), F.lit(0.0)))
    .withColumn("watch_count_value", F.coalesce(F.col("video_event_count").cast("double"), F.lit(0.0)))
    .withColumn("attempts_value", F.coalesce(F.col("attempts_sum"), F.lit(0.0)))
    .withColumn("watch_duration_min", F.min("watch_duration_value").over(course_window))
    .withColumn("watch_duration_max", F.max("watch_duration_value").over(course_window))
    .withColumn("watch_count_min", F.min("watch_count_value").over(course_window))
    .withColumn("watch_count_max", F.max("watch_count_value").over(course_window))
    .withColumn("attempts_min", F.min("attempts_value").over(course_window))
    .withColumn("attempts_max", F.max("attempts_value").over(course_window))
    .withColumn(
        "total_watch_duration_scaled",
        F.when(F.col("watch_duration_max") <= 0, F.lit(0.0))
        .when(F.col("watch_duration_max") == F.col("watch_duration_min"), F.lit(1.0))
        .otherwise(F.try_divide(
            F.col("watch_duration_value") - F.col("watch_duration_min"),
            F.col("watch_duration_max") - F.col("watch_duration_min"),
        )),
    )
    .withColumn(
        "total_watch_count_scaled",
        F.when(F.col("watch_count_max") <= 0, F.lit(0.0))
        .when(F.col("watch_count_max") == F.col("watch_count_min"), F.lit(1.0))
        .otherwise(F.try_divide(
            F.col("watch_count_value") - F.col("watch_count_min"),
            F.col("watch_count_max") - F.col("watch_count_min"),
        )),
    )
    .withColumn(
        "attempts_sum_scaled",
        F.when(F.col("attempts_max") <= 0, F.lit(0.0))
        .when(F.col("attempts_max") == F.col("attempts_min"), F.lit(1.0))
        .otherwise(F.try_divide(
            F.col("attempts_value") - F.col("attempts_min"),
            F.col("attempts_max") - F.col("attempts_min"),
        )),
    )
)

# COELO is the source four-component structural mean:
#   (watch-duration scale + video-watch ratio + attempts scale + problem ratio)
# with only the components applicable to the course in the denominator.  A
# present catalog with no learner event is a real zero, not structural absence.
base = scaled.withColumn(
    "coelo_video_component",
    (F.col("total_watch_duration_scaled") + F.col("video_watch_ratio")) / F.lit(2.0),
).withColumn(
    "coelo_problem_component",
    (F.col("attempts_sum_scaled") + F.col("problem_id_ratio")) / F.lit(2.0),
).withColumn(
    "COELO_personal",
    F.try_divide(
        F.col("total_watch_duration_scaled") * F.col("has_video_catalog")
        + F.col("video_watch_ratio") * F.col("has_video_catalog")
        + F.col("attempts_sum_scaled") * F.col("has_problem_catalog")
        + F.col("problem_id_ratio") * F.col("has_problem_catalog"),
        F.col("has_video_catalog") * F.lit(2.0)
        + F.col("has_problem_catalog") * F.lit(2.0),
    ),
).withColumn(
    "coelo_proxy_video_mask",
    F.col("has_video_catalog") * F.col("video_event_present"),
).withColumn(
    "coelo_proxy_problem_mask",
    F.col("has_problem_catalog") * F.col("problem_event_present"),
).withColumn(
    "coelo_proxy_observed_capacity",
    F.col("coelo_proxy_video_mask") + F.col("coelo_proxy_problem_mask"),
).withColumn(
    "COELO_proxy_personal",
    F.try_divide(
        F.coalesce(F.col("coelo_video_component"), F.lit(0.0)) * F.col("coelo_proxy_video_mask")
        + F.coalesce(F.col("coelo_problem_component"), F.lit(0.0)) * F.col("coelo_proxy_problem_mask"),
        F.col("coelo_proxy_observed_capacity"),
    ),
).withColumn(
    "COELO_proxy_observation_coverage",
    F.try_divide(
        F.col("coelo_proxy_observed_capacity"),
        F.col("has_video_catalog") + F.col("has_problem_catalog"),
    ),
)

# AFELO follows the source definition: average scaled watch count (when a
# video catalog exists) with activity breadth.  Comments are the third
# behaviour type, alongside video and problem, and are always retained as an
# observed auxiliary channel because the cleaned source has no comment catalog.
base = base.withColumn(
    "behavior_type_count",
    F.col("video_event_present") + F.col("problem_event_present") + F.col("comment_event_present"),
).withColumn(
    "behavior_type_capacity",
    F.col("has_video_catalog") + F.col("has_problem_catalog") + F.lit(1),
).withColumn(
    "AEF_personal",
    F.try_divide(F.col("behavior_type_count"), F.col("behavior_type_capacity")),
).withColumn(
    "AFELO_personal",
    F.try_divide(
        F.col("total_watch_count_scaled") * F.col("has_video_catalog") + F.col("AEF_personal"),
        F.col("has_video_catalog") + F.lit(1),
    ),
).withColumn(
    "required_behavior_type_count",
    # Comments contribute to AFELO, but they are not used as a mandatory
    # course modality in the floor because the cleaned source has no reliable
    # comment catalog/enablement flag.
    F.least(F.lit(2), F.col("has_video_catalog") + F.col("has_problem_catalog")),
).withColumn(
    "floor_behavior_type_count",
    F.col("video_event_present") + F.col("problem_event_present"),
)

# ACELO is a video/problem-only assessment score. A course with only video
# uses the video component; a course with only problem uses the problem
# component. Reading is folded into assignment/problem; discussion/comment and
# article are excluded. If ScoreStruct is absent, course_limit supplies the
# assessment weights and becomes the primary fallback.
base = base.withColumn(
    "assessment_observable",
    (
        (
            (F.col("has_score_structure_flag") == 1)
            & (F.col("configured_weight_total") > 0)
            & ((F.coalesce(F.col("score_weight_video"), F.lit(0.0)) == 0) | (F.col("has_video_catalog") == 1))
            & ((F.coalesce(F.col("score_weight_assignment"), F.lit(0.0)) == 0) | (F.col("has_problem_catalog") == 1))
            & (F.col("effective_weight_total") > 0)
        )
        | (
            (F.col("has_score_structure_flag") == 0)
            & (F.col("configured_weight_total") > 0)
            & (F.col("effective_weight_total") > 0)
        )
    ).cast("int"),
).withColumn(
    "assessment_proxy_available",
    (F.col("effective_weight_total") > 0).cast("int"),
).withColumn(
    "ace_effective_weight",
    F.col("effective_weight_total"),
).withColumn(
    "ACELO_personal",
    F.when(
        F.col("assessment_proxy_available") == 1,
        F.try_divide(
            F.col("effective_video_weight") * F.col("video_watch_ratio")
            + F.col("effective_problem_weight") * F.col("problem_score_ratio"),
            F.col("effective_weight_total"),
        ),
    ),
).withColumn(
    "ACELO_proxy_personal",
    F.when(
        F.col("assessment_proxy_available") == 1,
        F.try_divide(
            F.col("effective_video_weight") * F.coalesce(F.col("video_watch_ratio"), F.lit(0.0))
            + F.col("effective_problem_weight") * F.coalesce(F.col("problem_progress_proxy"), F.lit(0.0)),
            F.col("effective_weight_total"),
        ),
    ),
).withColumn(
    "ACELO_score_10",
    F.col("ACELO_personal") * F.lit(10.0),
).withColumn(
    "ACELO_proxy_score_10",
    F.col("ACELO_proxy_personal") * F.lit(10.0),
)

base = base.withColumn(
    "ACELO_grade",
    F.when(F.col("ACELO_personal").isNull(), F.lit(None).cast("string"))
    .when(F.col("ACELO_personal") < F.lit(0.60), F.lit("F"))
    .when(F.col("ACELO_personal") < F.lit(0.85), F.lit("B"))
    .otherwise(F.lit("A")),
).withColumn(
    "ACELO_proxy_grade",
    F.when(F.col("ACELO_proxy_personal").isNull(), F.lit(None).cast("string"))
    .when(F.col("ACELO_proxy_personal") < F.lit(0.60), F.lit("F"))
    .when(F.col("ACELO_proxy_personal") < F.lit(0.85), F.lit("B"))
    .otherwise(F.lit("A")),
).withColumn(
    "floor_coelo_pass", (F.col("COELO_personal") >= F.lit(COELO_FLOOR)).cast("int")
).withColumn(
    "proxy_floor_coelo_pass", (F.col("COELO_proxy_personal") >= F.lit(COELO_FLOOR)).cast("int")
).withColumn(
    "floor_acelo_pass", (F.col("ACELO_personal") >= F.lit(ACELO_FLOOR)).cast("int")
).withColumn(
    "proxy_floor_acelo_pass", (F.col("ACELO_proxy_personal") >= F.lit(ACELO_FLOOR)).cast("int")
).withColumn(
    "floor_behavior_pass", (F.col("floor_behavior_type_count") >= F.col("required_behavior_type_count")).cast("int")
).withColumn(
    "floor_pass",
    (
        (F.col("assessment_observable") == 1)
        & (F.col("floor_coelo_pass") == 1)
        & (F.col("floor_acelo_pass") == 1)
        & (F.col("floor_behavior_pass") == 1)
    ).cast("int"),
).withColumn(
    "proxy_floor_pass",
    (
        (F.col("assessment_proxy_available") == 1)
        & (F.col("proxy_floor_coelo_pass") == 1)
        & (F.col("proxy_floor_acelo_pass") == 1)
        & (F.col("floor_behavior_pass") == 1)
    ).cast("int"),
).withColumn(
    "G_weighted_geometric_mean",
    F.when(
        (F.col("floor_pass") == 1) & (F.col("COELO_personal") >= 0) & (F.col("AFELO_personal") >= 0) & (F.col("ACELO_personal") >= 0),
        F.pow(F.col("COELO_personal"), F.lit(G_WEIGHT["COELO"]))
        * F.pow(F.col("AFELO_personal"), F.lit(G_WEIGHT["AFELO"]))
        * F.pow(F.col("ACELO_personal"), F.lit(G_WEIGHT["ACELO"])),
    ),
).withColumn(
    "G_proxy_weighted_geometric_mean",
    F.when(
        (F.col("assessment_proxy_available") == 1)
        & (F.col("COELO_proxy_personal") >= 0)
        & (F.col("AFELO_personal") >= 0)
        & (F.col("ACELO_proxy_personal") >= 0),
        F.pow(F.col("COELO_proxy_personal"), F.lit(G_WEIGHT["COELO"]))
        * F.pow(F.col("AFELO_personal"), F.lit(G_WEIGHT["AFELO"]))
        * F.pow(F.col("ACELO_proxy_personal"), F.lit(G_WEIGHT["ACELO"])),
    ),
).withColumn(
    "cq_label",
    F.when(F.col("assessment_observable") == 0, F.lit(None).cast("string"))
    .when(F.col("floor_pass") == 0, F.lit("needs_review"))
    .when(F.col("G_weighted_geometric_mean") >= F.lit(G_EXCELLENT), F.lit("excellent"))
    .when(F.col("G_weighted_geometric_mean") >= F.lit(G_GOOD), F.lit("good"))
    .when(F.col("G_weighted_geometric_mean") >= F.lit(G_PASS), F.lit("pass"))
    .otherwise(F.lit("needs_review")),
).withColumn(
    "cq_proxy_label",
    F.when(F.col("assessment_proxy_available") == 0, F.lit(None).cast("string"))
    .when(F.col("proxy_floor_pass") == 0, F.lit("needs_review"))
    .when(F.col("G_proxy_weighted_geometric_mean") >= F.lit(G_EXCELLENT), F.lit("excellent"))
    .when(F.col("G_proxy_weighted_geometric_mean") >= F.lit(G_GOOD), F.lit("good"))
    .when(F.col("G_proxy_weighted_geometric_mean") >= F.lit(G_PASS), F.lit("pass"))
    .otherwise(F.lit("needs_review")),
).withColumn(
    "proxy_label_valid",
    (F.col("cq_proxy_label").isNotNull()).cast("int"),
).withColumn(
    "label_valid",
    ((F.col("assessment_observable") == 1) & F.col("cq_label").isNotNull()).cast("int"),
).withColumn(
    "label_exclusion_reason",
    F.when(F.col("assessment_observable") == 0, F.lit("assessment_activity_not_fully_observable"))
    .when(F.col("floor_coelo_pass") == 0, F.lit("coelo_below_0_50"))
    .when(F.col("floor_acelo_pass") == 0, F.lit("acelo_below_floor_5_0_of_10"))
    .when(F.col("floor_behavior_pass") == 0, F.lit("insufficient_behavior_types")),
).withColumn("label_availability_time", F.col("label_availability_time"))

base = base.withColumn(
    "assessment_status",
    F.when(
        (F.col("has_score_structure_flag") == 0)
        & (F.col("assessment_weight_source") == "course_limit_fallback"),
        F.lit("course_limit_fallback_observable"),
    )
    .when(
        (F.col("has_score_structure_flag") == 0)
        & (F.col("assessment_weight_source") == "course_limit_fallback_missing_catalog"),
        F.lit("course_limit_fallback_missing_catalog"),
    )
    .when(F.coalesce(F.col("has_score_structure"), F.lit(0)) != 1, F.lit("missing_score_structure"))
    .when(
        (F.col("has_score_structure_flag") == 1)
        & (F.col("configured_weight_total") <= 0),
        F.lit("score_structure_no_mapped_component"),
    )
    .when((F.coalesce(F.col("score_weight_video"), F.lit(0.0)) > 0) & (F.col("has_video_catalog") == 0), F.lit("missing_video_catalog"))
    .when((F.coalesce(F.col("score_weight_assignment"), F.lit(0.0)) > 0) & (F.col("has_problem_catalog") == 0), F.lit("missing_assignment_catalog"))
    .otherwise(F.lit("fully_observable")),
)

# Make the provenance of a non-null primary label explicit.  A label produced
# from course_limit is usable for the current experiment, but it must remain
# distinguishable from a label backed by the formal ScoreStruct rubric.
base = base.withColumn(
    "primary_label_source",
    F.when(F.col("assessment_observable") == 1, F.col("assessment_weight_source"))
    .otherwise(F.lit("unavailable")),
)

artifact = base.select(
    "enrollment_id", "user_id", "course_id", "offering_id", "offering_start_date", "offering_end_date",
    "offering_source", "cq_population_group", "cq_active_event_any", "label_availability_time", "label_availability_source", "label_valid", "label_exclusion_reason",
    "proxy_label_valid", "cq_proxy_label", "assessment_observable", "assessment_proxy_available",
    "assessment_weight_source", "primary_label_source", "assessment_weight_coverage", "course_modality",
    "has_video_catalog", "has_problem_catalog",
    "assessment_status",
    "score_weight_video", "score_weight_assignment", "score_weight_comment",
    "score_weight_article_excluded", "score_weight_unobserved",
    "configured_video_weight", "configured_problem_weight", "configured_comment_weight",
    "effective_video_weight", "effective_problem_weight", "effective_comment_weight", "ace_effective_weight",
    "video_watch_ratio", "problem_id_ratio", "problem_score_ratio", "problem_score_observed", "problem_score_reconstructed", "problem_score_effective_available", "problem_score_source", "problem_progress_proxy", "comment_progress_ratio",
    "total_watch_duration", "video_event_count", "problem_event_count", "attempts_sum", "comment_count",
    "score_observed_count", "score_reconstructed_count", "score_effective_count", "unresolved_missing_score_count", "is_correct_observed_count", "is_correct_true_count", "is_correct_false_count",
    "total_watch_duration_scaled", "total_watch_count_scaled", "attempts_sum_scaled",
    "coelo_video_component", "coelo_problem_component", "AEF_personal",
    "behavior_type_count", "behavior_type_capacity", "floor_behavior_type_count",
    "required_behavior_type_count", "COELO_personal", "AFELO_personal", "ACELO_personal", "ACELO_score_10", "ACELO_grade",
    "COELO_proxy_personal", "COELO_proxy_observation_coverage", "ACELO_proxy_personal", "ACELO_proxy_score_10", "ACELO_proxy_grade",
    "floor_coelo_pass", "proxy_floor_coelo_pass", "floor_acelo_pass", "proxy_floor_acelo_pass",
    "floor_behavior_pass", "floor_pass", "proxy_floor_pass",
    "G_weighted_geometric_mean", "G_proxy_weighted_geometric_mean", "cq_label", "video_event_present", "problem_event_present", "comment_event_present",
    F.lit(LABEL_VERSION).alias("label_rule_version"),
)

audit = artifact.groupBy("cq_label", "primary_label_source").agg(
    F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"), F.avg("G_weighted_geometric_mean").alias("G_mean"),
    F.avg("COELO_personal").alias("COELO_mean"), F.avg("AFELO_personal").alias("AFELO_mean"),
    F.avg("ACELO_personal").alias("ACELO_mean"),
).withColumn("label_source", F.col("primary_label_source"))
proxy_audit = artifact.groupBy("cq_proxy_label", "assessment_weight_source").agg(
    F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.avg("G_proxy_weighted_geometric_mean").alias("G_proxy_mean"),
    F.avg("COELO_personal").alias("COELO_primary_mean"),
    F.avg("COELO_proxy_personal").alias("COELO_proxy_mean"),
    F.avg("AFELO_personal").alias("AFELO_mean"),
    F.avg("ACELO_personal").alias("ACELO_primary_mean"),
    F.avg("ACELO_proxy_personal").alias("ACELO_proxy_mean"),
)
modality_audit = artifact.groupBy("course_modality", "assessment_weight_source").agg(
    F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.sum("label_valid").alias("primary_label_valid_count"),
    F.sum("proxy_label_valid").alias("proxy_label_valid_count"),
    F.avg("assessment_weight_coverage").alias("assessment_weight_coverage_mean"),
    F.avg("COELO_personal").alias("COELO_primary_mean"),
    F.avg("COELO_proxy_personal").alias("COELO_proxy_mean"),
    F.avg("AFELO_personal").alias("AFELO_mean"),
    F.avg("ACELO_personal").alias("ACELO_primary_mean"),
    F.avg("ACELO_proxy_personal").alias("ACELO_proxy_mean"),
).orderBy("course_modality", "assessment_weight_source")
assessment_audit = artifact.groupBy("assessment_status", "assessment_observable").agg(
    F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.sum(F.when(F.col("label_valid") == 1, 1).otherwise(0)).alias("label_valid_count"),
    F.sum(F.when(F.col("floor_pass") == 1, 1).otherwise(0)).alias("floor_pass_count"),
).orderBy("assessment_status")
population_summary = artifact.groupBy("cq_population_group").agg(
    F.count("*").alias("enrollment_count"),
    F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.sum("cq_active_event_any").alias("active_event_enrollment_count"),
    F.sum(F.when(F.col("cq_active_event_any") == 0, 1).otherwise(0)).alias("zero_activity_enrollment_count"),
    F.sum("label_valid").alias("label_valid_count"),
    F.sum(F.when(F.col("cq_label") == "needs_review", 1).otherwise(0)).alias("needs_review_count"),
).orderBy("cq_population_group")
floor_failure_summary = None
for failure_column, failure_name in (
    ("floor_coelo_pass", "COELO_below_0_50"),
    ("floor_acelo_pass", "ACELO_below_5_0_of_10"),
    ("floor_behavior_pass", "insufficient_behavior_types"),
):
    one_failure = artifact.filter(
        (F.col("assessment_observable") == 1) & (F.col(failure_column) == 0)
    ).agg(
        F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
    ).withColumn("failure_reason", F.lit(failure_name))
    floor_failure_summary = one_failure if floor_failure_summary is None else floor_failure_summary.unionByName(one_failure)

floor_failure_combinations = artifact.withColumn(
    "failure_combination",
    F.when(F.col("assessment_observable") == 0, F.lit("ASSESSMENT_UNOBSERVABLE"))
    .otherwise(F.concat_ws(
        "+",
        F.when(F.col("floor_coelo_pass") == 0, F.lit("COELO")),
        F.when(F.col("floor_acelo_pass") == 0, F.lit("ACELO")),
        F.when(F.col("floor_behavior_pass") == 0, F.lit("BEHAVIOR")),
    )),
).withColumn(
    "failure_combination",
    F.when(F.col("failure_combination") == "", F.lit("ALL_FLOORS_PASSED")).otherwise(F.col("failure_combination")),
).groupBy("failure_combination").agg(
    F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
).orderBy("failure_combination")


def metric_summary(dataframe, population):
    return dataframe.agg(
        F.count("COELO_personal").alias("sample_count"), F.avg("COELO_personal").alias("mean"),
        F.stddev("COELO_personal").alias("stddev"), F.min("COELO_personal").alias("min"),
        F.expr("percentile_approx(COELO_personal, 0.25)").alias("p25"),
        F.expr("percentile_approx(COELO_personal, 0.50)").alias("p50"),
        F.expr("percentile_approx(COELO_personal, 0.75)").alias("p75"), F.max("COELO_personal").alias("max"),
    ).withColumn("metric", F.lit("COELO_personal")).withColumn("population", F.lit(population)).unionByName(
        dataframe.agg(
            F.count("COELO_proxy_personal").alias("sample_count"), F.avg("COELO_proxy_personal").alias("mean"),
            F.stddev("COELO_proxy_personal").alias("stddev"), F.min("COELO_proxy_personal").alias("min"),
            F.expr("percentile_approx(COELO_proxy_personal, 0.25)").alias("p25"),
            F.expr("percentile_approx(COELO_proxy_personal, 0.50)").alias("p50"),
            F.expr("percentile_approx(COELO_proxy_personal, 0.75)").alias("p75"), F.max("COELO_proxy_personal").alias("max"),
        ).withColumn("metric", F.lit("COELO_proxy_personal")).withColumn("population", F.lit(population))
    ).unionByName(
        dataframe.agg(
            F.count("AFELO_personal").alias("sample_count"), F.avg("AFELO_personal").alias("mean"),
            F.stddev("AFELO_personal").alias("stddev"), F.min("AFELO_personal").alias("min"),
            F.expr("percentile_approx(AFELO_personal, 0.25)").alias("p25"),
            F.expr("percentile_approx(AFELO_personal, 0.50)").alias("p50"),
            F.expr("percentile_approx(AFELO_personal, 0.75)").alias("p75"), F.max("AFELO_personal").alias("max"),
        ).withColumn("metric", F.lit("AFELO_personal")).withColumn("population", F.lit(population))
    ).unionByName(
        dataframe.agg(
            F.count("ACELO_personal").alias("sample_count"), F.avg("ACELO_personal").alias("mean"),
            F.stddev("ACELO_personal").alias("stddev"), F.min("ACELO_personal").alias("min"),
            F.expr("percentile_approx(ACELO_personal, 0.25)").alias("p25"),
            F.expr("percentile_approx(ACELO_personal, 0.50)").alias("p50"),
            F.expr("percentile_approx(ACELO_personal, 0.75)").alias("p75"), F.max("ACELO_personal").alias("max"),
    ).withColumn("metric", F.lit("ACELO_personal")).withColumn("population", F.lit(population))
    ).unionByName(
        dataframe.agg(
            F.count("ACELO_proxy_personal").alias("sample_count"), F.avg("ACELO_proxy_personal").alias("mean"),
            F.stddev("ACELO_proxy_personal").alias("stddev"), F.min("ACELO_proxy_personal").alias("min"),
            F.expr("percentile_approx(ACELO_proxy_personal, 0.25)").alias("p25"),
            F.expr("percentile_approx(ACELO_proxy_personal, 0.50)").alias("p50"),
            F.expr("percentile_approx(ACELO_proxy_personal, 0.75)").alias("p75"), F.max("ACELO_proxy_personal").alias("max"),
        ).withColumn("metric", F.lit("ACELO_proxy_personal")).withColumn("population", F.lit(population))
    ).unionByName(
        dataframe.agg(
            F.count("G_weighted_geometric_mean").alias("sample_count"), F.avg("G_weighted_geometric_mean").alias("mean"),
            F.stddev("G_weighted_geometric_mean").alias("stddev"), F.min("G_weighted_geometric_mean").alias("min"),
            F.expr("percentile_approx(G_weighted_geometric_mean, 0.25)").alias("p25"),
            F.expr("percentile_approx(G_weighted_geometric_mean, 0.50)").alias("p50"),
            F.expr("percentile_approx(G_weighted_geometric_mean, 0.75)").alias("p75"), F.max("G_weighted_geometric_mean").alias("max"),
        ).withColumn("metric", F.lit("G_weighted_geometric_mean")).withColumn("population", F.lit(population))
    )


metric_audit = metric_summary(artifact, "all_active")
metric_audit = metric_audit.unionByName(metric_summary(artifact.filter(F.col("assessment_observable") == 1), "assessment_observable"))
metric_audit = metric_audit.unionByName(metric_summary(artifact.filter(F.col("floor_pass") == 1), "floor_pass"))
behavior_audit = artifact.groupBy(
    "behavior_type_capacity", "behavior_type_count", "floor_behavior_type_count", "required_behavior_type_count",
    "video_event_present", "problem_event_present", "comment_event_present",
).agg(
    F.count("*").alias("enrollment_count"), F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
).orderBy("behavior_type_capacity", "behavior_type_count")
course_label_profile = (
    artifact.withColumn("label_bucket", F.coalesce(F.col("cq_label"), F.lit("N/A")))
    .groupBy("course_id")
    .agg(
        F.count("*").alias("active_enrollment_count"), F.countDistinct("user_id").alias("active_user_count"),
        F.sum("label_valid").alias("label_valid_count"), F.sum("floor_pass").alias("floor_pass_count"),
    )
)
course_label_counts = (
    artifact.withColumn("label_bucket", F.coalesce(F.col("cq_label"), F.lit("N/A")))
    .groupBy("course_id").pivot("label_bucket", ["N/A", "needs_review", "pass", "good", "excellent"]).count()
    .fillna(0)
)
course_label_profile = course_label_profile.join(course_label_counts, "course_id", "left")
global_audit = artifact.agg(
    F.count("*").alias("active_enrollment_count"),
    F.sum("label_valid").alias("label_valid_count"),
    F.sum("proxy_label_valid").alias("proxy_label_valid_count"),
    F.sum(F.when((F.col("proxy_label_valid") == 1) & (F.col("label_valid") == 0), 1).otherwise(0)).alias("proxy_only_count"),
    F.sum(F.when(F.col("assessment_observable") == 0, 1).otherwise(0)).alias("assessment_unobservable_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("primary_label_source") == "score_structure"), 1).otherwise(0)).alias("primary_score_structure_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("primary_label_source") == "course_limit_fallback"), 1).otherwise(0)).alias("primary_course_limit_fallback_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("primary_label_source") == "equal_observed_modalities"), 1).otherwise(0)).alias("primary_equal_observed_modalities_count"),
    F.sum(F.when(F.col("floor_pass") == 1, 1).otherwise(0)).alias("floor_pass_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("floor_coelo_pass") == 0), 1).otherwise(0)).alias("coelo_floor_fail_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("floor_acelo_pass") == 0), 1).otherwise(0)).alias("acelo_floor_fail_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("floor_behavior_pass") == 0), 1).otherwise(0)).alias("behavior_floor_fail_count"),
    F.sum(F.when((F.col("assessment_observable") == 1) & (F.col("floor_pass") == 0), 1).otherwise(0)).alias("any_floor_fail_count"),
    F.sum("problem_score_observed").alias("problem_score_observed_enrollment_count"),
    F.sum("problem_score_reconstructed").alias("problem_score_reconstructed_enrollment_count"),
    F.sum("problem_score_effective_available").alias("problem_score_effective_available_count"),
    F.sum(F.when(F.col("problem_score_source") == "unresolved_score_remains", 1).otherwise(0)).alias(
        "problem_score_unresolved_enrollment_count"
    ),
    F.sum(F.when(F.col("problem_score_source") == "no_problem_event", 1).otherwise(0)).alias(
        "problem_no_event_enrollment_count"
    ),
    F.sum(F.when(F.col("problem_score_source") == "missing_full_score_denominator", 1).otherwise(0)).alias(
        "problem_missing_denominator_enrollment_count"
    ),
    F.sum(F.when(F.col("problem_score_source") == "missing_problem_catalog", 1).otherwise(0)).alias(
        "problem_missing_catalog_enrollment_count"
    ),
    F.countDistinct("user_id").alias("active_user_count"),
    F.countDistinct("course_id").alias("active_course_count"),
).withColumn("label_version", F.lit(LABEL_VERSION))

global_audit = global_audit.withColumn("acelo_floor_score_10", F.lit(ACELO_FLOOR_SCORE_10)).withColumn(
    "acelo_floor_normalized", F.lit(ACELO_FLOOR)
)

# A Databricks kernel can retain a pre-V1 common.protocol_config module.  The
# label artifact location is fixed by this V1 release, so retain a local
# fallback until every workspace config has been migrated.
artifact_path = os.environ.get("CQ_COMPONENT_OUTPUT")
if not artifact_path:
    try:
        artifact_path = path_from_config(PROTOCOL, "cq_label_components")
    except KeyError:
        artifact_path = f"{OUTPUT_BASE.rstrip('/')}/labels/cq_label_components_v1"
artifact_path = artifact_path.rstrip("/") + "/"
audit_path = f"{OUTPUT_BASE}/labels/cq_label_components_v1_audit/"
write_parquet(artifact, artifact_path)
write_parquet(audit, f"{audit_path}label_distribution/")
write_parquet(proxy_audit, f"{audit_path}proxy_label_distribution/")
write_parquet(modality_audit, f"{audit_path}modality_summary/")
write_parquet(global_audit, f"{audit_path}global_summary/")
write_parquet(assessment_audit, f"{audit_path}assessment_status_summary/")
write_parquet(population_summary, f"{audit_path}population_summary/")
write_parquet(floor_failure_summary, f"{audit_path}floor_failure_summary/")
write_parquet(floor_failure_combinations, f"{audit_path}floor_failure_combinations/")
write_parquet(metric_audit, f"{audit_path}metric_distribution/")
write_parquet(behavior_audit, f"{audit_path}behavior_pattern_summary/")
write_parquet(course_label_profile, f"{audit_path}course_label_profile/")
rows = log_dataframe(logger, "cq_personal_v3_labels", artifact, ("enrollment_id", "course_id"))
audit_rows = log_dataframe(logger, "cq_personal_v3_label_distribution", audit, ("cq_label", "primary_label_source"))
proxy_rows = log_dataframe(logger, "cq_personal_v3_proxy_label_distribution", proxy_audit, ("cq_proxy_label", "assessment_weight_source"))
modality_rows = log_dataframe(logger, "cq_personal_v3_modality_summary", modality_audit, ("course_modality", "assessment_weight_source"))
assessment_rows = log_dataframe(logger, "cq_personal_v3_assessment_status_summary", assessment_audit, ("assessment_status",))
population_rows = log_dataframe(logger, "cq_personal_v3_population_summary", population_summary, ("cq_population_group",))
failure_rows = log_dataframe(logger, "cq_personal_v3_floor_failure_summary", floor_failure_summary, ("failure_reason",))
metric_rows = log_dataframe(logger, "cq_personal_v3_metric_distribution", metric_audit, ("metric", "population"))
log_write(logger, "cq_personal_v3_labels", artifact_path, rows)
log_write(logger, "cq_personal_v3_label_distribution", f"{audit_path}label_distribution/", audit_rows)
log_write(logger, "cq_personal_v3_proxy_label_distribution", f"{audit_path}proxy_label_distribution/", proxy_rows)
log_write(logger, "cq_personal_v3_modality_summary", f"{audit_path}modality_summary/", modality_rows)
log_write(logger, "cq_personal_v3_assessment_status_summary", f"{audit_path}assessment_status_summary/", assessment_rows)
log_write(logger, "cq_personal_v3_population_summary", f"{audit_path}population_summary/", population_rows)
log_write(logger, "cq_personal_v3_floor_failure_summary", f"{audit_path}floor_failure_summary/", failure_rows)
log_write(logger, "cq_personal_v3_metric_distribution", f"{audit_path}metric_distribution/", metric_rows)
log_event(
    logger,
    "cq_personal_v3_policy",
    coelo_floor=COELO_FLOOR,
    acelo_floor=ACELO_FLOOR,
    acelo_floor_score_10=ACELO_FLOOR_SCORE_10,
    geometric_weights=G_WEIGHT,
    coelo_proxy_policy="observed_modalities_only__source_four_components",
    assessment_fallback_policy="course_limit_when_score_structure_absent__discussion_comment__reading_assignment__article_excluded",
    problem_score_policy="observed_score_first__is_correct_reconstruction_when_score_missing__unresolved_not_imputed",
    problem_score_denominator_policy="course_full_score_required__no_denominator_never_becomes_ratio_one",
    problem_score_source_column="problem_score_source",
)
log_run_finished(logger, started)
flush_json_log(logger, spark)
