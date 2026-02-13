"""Cohort analysis."""
import logging

logger = logging.getLogger(__name__)

class CohortAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_cohorts(self, users, period='month'):
        cohorts = {}
        for user in users:
            cohort = user.get('signup_date')
            if cohort not in cohorts:
                cohorts[cohort] = []
            cohorts[cohort].append(user)
        return cohorts
