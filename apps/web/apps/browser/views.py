from django.views.generic import TemplateView


class BrowserHomeView(TemplateView):
    template_name = "browser/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["planned_sections"] = [
            "Runs",
            "Taxa",
            "Genomes",
            "Proteins",
            "Repeat calls",
        ]
        return context
