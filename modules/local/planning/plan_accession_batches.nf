process PLAN_ACCESSION_BATCHES {
    label 'planning'
    publishDir("${params.output_dir}/planning", mode: 'copy', saveAs: { filename ->
        filename.startsWith('planning_artifacts/') ? filename.substring('planning_artifacts/'.length()) : filename
    })

    input:
    path(accessions_file)

    output:
    path("planning_artifacts"), emit: planning_artifacts

    script:
    """
    export PYTHONPATH="${projectDir}:\${PYTHONPATH:-}"

    ${params.python_bin} ${projectDir}/bin/plan_accession_batches.py \
      --accessions-file ${accessions_file} \
      --target-batch-size ${params.batch_size} \
      --outdir planning_artifacts
    """
}
