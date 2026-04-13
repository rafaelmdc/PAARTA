from django.db import models
from django.db.models import Q

from .base import TimestampedModel


class Taxon(TimestampedModel):
    taxon_id = models.PositiveBigIntegerField(unique=True)
    taxon_name = models.CharField(max_length=255, db_index=True)
    rank = models.CharField(max_length=64, blank=True, db_index=True)
    parent_taxon = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        blank=True,
        null=True,
    )
    source = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["taxon_name", "taxon_id"]
        indexes = [
            models.Index(fields=["rank", "taxon_name"], name="browser_taxon_rank_name_idx"),
        ]

    def __str__(self):
        return f"{self.taxon_name} ({self.taxon_id})"


class TaxonClosure(models.Model):
    ancestor = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name="closure_descendants",
    )
    descendant = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name="closure_ancestors",
    )
    depth = models.PositiveIntegerField()

    class Meta:
        ordering = ["ancestor__taxon_name", "depth", "descendant__taxon_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["ancestor", "descendant"],
                name="browser_taxon_closure_unique_ancestor_descendant",
            ),
            models.CheckConstraint(
                condition=Q(depth__gte=0),
                name="browser_taxon_closure_depth_gte_zero",
            ),
        ]
        indexes = [
            models.Index(
                fields=["ancestor", "depth", "descendant"],
                name="browser_taxon_closure_anc_idx",
            ),
            models.Index(
                fields=["descendant", "depth", "ancestor"],
                name="browser_taxon_closure_desc_idx",
            ),
        ]

    def __str__(self):
        return f"{self.ancestor} -> {self.descendant} ({self.depth})"
