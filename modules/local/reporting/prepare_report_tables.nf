process PREPARE_REPORT_TABLES {
    label 'reporting'
    publishDir "${params.output_dir}/report_prep", mode: 'copy'

    input:
    path(summary_tsv)
    path(regression_tsv)

    output:
    path('echarts_options.json'), emit: echarts_options

    script:
    """
    export PYTHONPATH="${projectDir}:\${PYTHONPATH:-}"

    ${params.python_bin} ${projectDir}/bin/prepare_report_tables.py \
      --summary-tsv ${summary_tsv} \
      --regression-tsv ${regression_tsv} \
      --outdir report_prep_tmp

    mv report_prep_tmp/echarts_options.json echarts_options.json
    """
}
