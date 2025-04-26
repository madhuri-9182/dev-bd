from math import gcd
from django.db.models import Count, Q
from collections import defaultdict
from dashboard.models import Candidate


def get_candidate_analytics(queryset):
    def simplify_ratio(selected_candidates, total_candidates):
        factor = gcd(selected_candidates, total_candidates)
        if not factor:
            return 0, 0
        return selected_candidates // factor, total_candidates // factor

    analytics = queryset.aggregate(
        total_candidates=Count("id"),
        total_interviews=Count(
            "id", filter=Q(status__in=["NJ", "HREC", "REC", "NREC", "SNREC"])
        ),
        top_performers=Count("id", filter=Q(score__gte=80)),
        good_candidates=Count("id", filter=Q(score__gte=70, score__lt=80)),
        rejected=Count("id", filter=Q(final_selection_status="RJD")),
        declined_by_candidate=Count("id", filter=Q(status="NJ")),
        male_count=Count("id", filter=Q(gender="M")),
        female_count=Count("id", filter=Q(gender="F")),
    )

    # Group selected and rejected by current company
    candidate_by_companies = (
        queryset.filter(final_selection_status__in=["SLD", "RJD"])
        .values("company")
        .annotate(total_count=Count("id"))
        .annotate(
            selected_count=Count("id", filter=Q(final_selection_status="SLD")),
            rejected_count=Count("id", filter=Q(final_selection_status="RJD")),
        )
    )

    selected_dict = {
        entry["company"]: int((entry["selected_count"] / entry["total_count"]) * 100)
        for entry in candidate_by_companies
        if entry["company"] and entry["total_count"]
    }

    rejected_dict = {
        entry["company"]: int((entry["rejected_count"] / entry["total_count"]) * 100)
        for entry in candidate_by_companies
        if entry["company"] and entry["total_count"]
    }

    # Ratios
    selected_count = analytics["total_interviews"]
    ratio = simplify_ratio(selected_count, analytics["total_candidates"])
    selection_ratio = f"{ratio[0]}:{ratio[1]}" if selected_count else "0:0"

    diversity_ratio = f"{analytics['male_count']}:{analytics['female_count']}"

    return {
        "status_info": analytics,
        "selected_candidates": selected_dict,
        "rejected_candidates": rejected_dict,
        "ratio_details": {
            "selection_ratio": selection_ratio,
            "selection_ratio_for_diversity": diversity_ratio,
            "total_male_vs_female": f"{analytics['male_count']}:{analytics['female_count']}",
        },
    }
