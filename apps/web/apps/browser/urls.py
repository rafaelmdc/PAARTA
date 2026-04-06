from django.urls import path

from .views import (
    BrowserHomeView,
    GenomeListPlaceholderView,
    ProteinListPlaceholderView,
    RepeatCallListPlaceholderView,
    RunDetailView,
    RunListView,
    TaxonListPlaceholderView,
)


app_name = "browser"

urlpatterns = [
    path("", BrowserHomeView.as_view(), name="home"),
    path("runs/", RunListView.as_view(), name="run-list"),
    path("runs/<int:pk>/", RunDetailView.as_view(), name="run-detail"),
    path("taxa/", TaxonListPlaceholderView.as_view(), name="taxon-list"),
    path("genomes/", GenomeListPlaceholderView.as_view(), name="genome-list"),
    path("proteins/", ProteinListPlaceholderView.as_view(), name="protein-list"),
    path("calls/", RepeatCallListPlaceholderView.as_view(), name="repeatcall-list"),
]
