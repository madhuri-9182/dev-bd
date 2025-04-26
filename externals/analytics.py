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
    selected_by_company = (
        queryset.filter(final_selection_status__in=["SLD", "RJD"])
        .values("company")
        .annotate(count=Count("id"))
    )
    rejected_by_company = (
        queryset.filter(final_selection_status__in=["SLD", "RJD"])
        .values("company")
        .annotate(count=Count("id"))
    )

    selected_dict = {
        entry["company"]: int((entry["count"] / analytics["total_candidates"]) * 100)
        for entry in selected_by_company
        if entry["company"] and analytics["total_candidates"]
    }

    rejected_dict = {
        entry["company"]: int((entry["count"] / analytics["total_candidates"]) * 100)
        for entry in rejected_by_company
        if entry["company"] and analytics["total_candidates"]
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
