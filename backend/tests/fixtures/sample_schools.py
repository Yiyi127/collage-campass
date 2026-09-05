from scripts.refresh_data import build_database

INSTITUTIONS = [
    {
        "id": 1, "school.name": "Drexel University", "school.state": "PA",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.76,
        "latest.admissions.sat_scores.25th_percentile.critical_reading": 570,
        "latest.admissions.sat_scores.25th_percentile.math": 590,
        "latest.admissions.sat_scores.75th_percentile.critical_reading": 680,
        "latest.admissions.sat_scores.75th_percentile.math": 700,
        "latest.student.size": 14000, "latest.cost.avg_net_price.overall": 32000,
        "latest.academics.program_percentage.computer": 0.14,
    },
    {
        "id": 2, "school.name": "Massachusetts Institute of Technology", "school.state": "MA",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.04,
        "latest.admissions.sat_scores.25th_percentile.critical_reading": 730,
        "latest.admissions.sat_scores.25th_percentile.math": 790,
        "latest.admissions.sat_scores.75th_percentile.critical_reading": 780,
        "latest.admissions.sat_scores.75th_percentile.math": 800,
        "latest.student.size": 4600, "latest.cost.avg_net_price.overall": 21000,
        "latest.academics.program_percentage.computer": 0.35,
    },
    {
        "id": 3, "school.name": "Closed Institute of Technology", "school.state": "PA",
        "school.operating": 0, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.6,
        "latest.student.size": 1000, "latest.cost.avg_net_price.overall": 20000,
    },
]
FIELD_OF_STUDY = [
    {"unitid": 1, "cipcode": "11.0701", "credlev": 3, "counts.ipeds_count": 210,
     "earnings.median": 68000, "debt.median": 25000},
    {"unitid": 2, "cipcode": "11.0701", "credlev": 3, "counts.ipeds_count": 180,
     "earnings.median": 95000, "debt.median": 12000},
]


def build_fixture_db(path: str):
    build_database(INSTITUTIONS, FIELD_OF_STUDY, path, scorecard_data_year="test-fixture")
