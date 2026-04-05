nextflow.enable.dsl = 2

include { BUILD_SQLITE } from '../modules/local/reporting/build_sqlite'
include { EXPORT_SUMMARY_TABLES } from '../modules/local/reporting/export_summary_tables'
include { PREPARE_REPORT_TABLES } from '../modules/local/reporting/prepare_report_tables'

workflow DATABASE_REPORTING {
    take:
    taxonomy_tsv
    genomes_tsv
    sequences_tsv
    proteins_tsv
    call_tsv
    run_params_tsv

    main:
    sqliteBuild = BUILD_SQLITE(
        taxonomy_tsv,
        genomes_tsv,
        sequences_tsv,
        proteins_tsv,
        call_tsv.collect(),
        run_params_tsv.collect(),
    )
    summaries = EXPORT_SUMMARY_TABLES(taxonomy_tsv, proteins_tsv, call_tsv.collect())
    reportPrep = PREPARE_REPORT_TABLES(summaries.summary_tsv, summaries.regression_tsv)

    emit:
    sqlite = sqliteBuild.sqlite_db
    sqlite_validation = sqliteBuild.sqlite_validation
    summary_by_taxon = summaries.summary_tsv
    regression_input = summaries.regression_tsv
    report_prep = reportPrep.echarts_options
}
