process MERGE_ACQUISITION_BATCHES {
    label 'acquisition_merge'
    publishDir("${params.output_dir}/acquisition", mode: 'copy', saveAs: { filename ->
        filename.startsWith('acquisition_artifacts/') ? filename.substring('acquisition_artifacts/'.length()) : filename
    })

    input:
    path(translated_batch_dirs)

    output:
    path("acquisition_artifacts"), emit: acquisition_artifacts

    script:
    def batchInputs = translated_batch_dirs instanceof List ? translated_batch_dirs : [translated_batch_dirs]
    def batchArgs = batchInputs.collect { "--batch-inputs '${it}'" }.join(' ')
    """
    export PYTHONPATH="${projectDir}:\${PYTHONPATH:-}"

    ${params.python_bin} ${projectDir}/bin/merge_acquisition_batches.py \
      ${batchArgs} \
      --outdir acquisition_artifacts
    """
}
