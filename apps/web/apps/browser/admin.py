from django.contrib import admin

from .models import PipelineRun, Taxon, TaxonClosure


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "status", "profile", "imported_at")
    search_fields = ("run_id", "git_revision", "status", "profile")
    list_filter = ("status", "profile")


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin):
    list_display = ("taxon_name", "taxon_id", "rank", "parent_taxon")
    search_fields = ("taxon_name", "taxon_id", "rank")
    list_filter = ("rank",)


@admin.register(TaxonClosure)
class TaxonClosureAdmin(admin.ModelAdmin):
    list_display = ("ancestor", "descendant", "depth")
    search_fields = (
        "ancestor__taxon_name",
        "ancestor__taxon_id",
        "descendant__taxon_name",
        "descendant__taxon_id",
    )
    list_filter = ("depth",)
