nextflow.enable.dsl = 2

include { PLAN_ACCESSION_BATCHES } from '../modules/local/planning/plan_accession_batches'
include { DOWNLOAD_NCBI_BATCH } from '../modules/local/acquisition/download_ncbi_batch'
include { NORMALIZE_CDS_BATCH } from '../modules/local/acquisition/normalize_cds_batch'
include { TRANSLATE_CDS_BATCH } from '../modules/local/acquisition/translate_cds_batch'
include { MERGE_ACQUISITION_BATCHES } from '../modules/local/acquisition/merge_acquisition_batches'

workflow ACQUISITION_FROM_ACCESSIONS {
    if( !params.accessions_file ) {
        error "params.accessions_file is required"
    }
    if( !params.taxonomy_db ) {
        error "params.taxonomy_db is required"
    }

    def accessionsFile = file(params.accessions_file, checkIfExists: true)
    def taxonomyDb = file(params.taxonomy_db, checkIfExists: true)

    planning = PLAN_ACCESSION_BATCHES(Channel.value(accessionsFile))
    batchManifestCh = planning.planning_artifacts.flatMap { planningDir ->
        def manifestsDir = planningDir.resolve('batch_manifests').toFile()
        def manifestFiles = manifestsDir.listFiles()?.findAll { it.name.endsWith('.tsv') }?.sort { it.name } ?: []
        manifestFiles.collect { file(it) }
    }
    downloaded = DOWNLOAD_NCBI_BATCH(batchManifestCh)
    normalized = NORMALIZE_CDS_BATCH(downloaded.raw_batch, Channel.value(taxonomyDb))
    translated = TRANSLATE_CDS_BATCH(normalized.normalized_batch)
    translatedBatchDirs = translated.translated_batch.map { batch_id, translated_batch_dir -> translated_batch_dir }.collect()
    merged = MERGE_ACQUISITION_BATCHES(translatedBatchDirs)
    acquisitionArtifacts = merged.acquisition_artifacts

    emit:
    genomes_tsv = acquisitionArtifacts.map { it.resolve('genomes.tsv') }
    taxonomy_tsv = acquisitionArtifacts.map { it.resolve('taxonomy.tsv') }
    sequences_tsv = acquisitionArtifacts.map { it.resolve('sequences.tsv') }
    proteins_tsv = acquisitionArtifacts.map { it.resolve('proteins.tsv') }
    cds_fasta = acquisitionArtifacts.map { it.resolve('cds.fna') }
    proteins_fasta = acquisitionArtifacts.map { it.resolve('proteins.faa') }
    acquisition_validation = acquisitionArtifacts.map { it.resolve('acquisition_validation.json') }
}
