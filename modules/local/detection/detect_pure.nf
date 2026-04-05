process DETECT_PURE {
    label 'detection'
    tag "${repeat_residue}"

    input:
    val(repeat_residue)
    path(proteins_tsv)
    path(proteins_fasta)

    output:
    tuple val('pure'), val(repeat_residue), path("pure_${repeat_residue}_calls.tsv"), path("pure_${repeat_residue}_run_params.tsv"), emit: calls

    script:
    """
    export PYTHONPATH="${projectDir}:\${PYTHONPATH:-}"

    ${params.python_bin} ${projectDir}/bin/detect_pure.py \
      --proteins-tsv ${proteins_tsv} \
      --proteins-fasta ${proteins_fasta} \
      --repeat-residue ${repeat_residue} \
      --outdir detect_pure_${repeat_residue}

    cp detect_pure_${repeat_residue}/pure_calls.tsv pure_${repeat_residue}_calls.tsv
    cp detect_pure_${repeat_residue}/run_params.tsv pure_${repeat_residue}_run_params.tsv
    """
}
