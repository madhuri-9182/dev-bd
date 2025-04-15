from django.db.models import Count, Q
from collections import defaultdict
from dashboard.models import Candidate

def get_candidate_analytics(queryset):
    
    total_candidates = queryset.count()
    total_interviews = queryset.filter(status__in=["COMPLETED", "HREC", "REC", "NREC", "SNREC"]).count()
    top_performers = queryset.filter(score__gte=80).count()  
    good_candidates = queryset.filter(score__gte=60, score__lte=80).count()  
    rejected = queryset.filter(final_selection_status="RJD").count()
    declined_by_candidate = queryset.filter(reason_for_dropping="CNI").count()
    declined_by_panel = queryset.filter(reason_for_dropping="OTH").count()

    selected_qs = queryset.filter(final_selection_status="SLD")
    rejected_qs = queryset.filter(final_selection_status="RJD")
    
    selected_count = selected_qs.count()
    rejected_count = rejected_qs.count()

    # Group selected and rejected by current company
    selected_by_company = selected_qs.values("company").annotate(count=Count("id"))
    rejected_by_company = rejected_qs.values("company").annotate(count=Count("id"))

    selected_dict = {
        entry["company"]: round((entry["count"] / selected_count) * 100, 2)
        for entry in selected_by_company if entry["company"]
    }

    rejected_dict = {
        entry["company"]: round((entry["count"] / rejected_count) * 100, 2)
        for entry in rejected_by_company if entry["company"]
    }

    # Ratios
    
    selection_ratio = f"1:{round(total_candidates / selected_count)}" if selected_count else "N/A"

    male_count = queryset.filter(gender="M").count()
    female_count = queryset.filter(gender="F").count()
    diversity_ratio = f"1:{round(selected_count / female_count)}" if female_count else "N/A"

    return {
        "status_info": {
            "total_candidates": total_candidates,
            "total_interviews": total_interviews,
            "top_performers": top_performers,
            "good_candidates": good_candidates,
            "rejected": rejected,
            "declined_by_candidate": declined_by_candidate,
            "declined_by_panel": declined_by_panel,
        },
        "selected_candidates": selected_dict,
        "rejected_candidates": rejected_dict,
        "ratio_details": {
            "selection_ratio": selection_ratio,
            "selection_ratio_for_diversity": diversity_ratio,
            "total_male_vs_female": f"{male_count}:{female_count}",
        },
    }