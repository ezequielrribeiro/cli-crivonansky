import json
import logging
import math
from datetime import datetime


def __calculate_task_priority(task_create_date: datetime, task_priority_tag: int, task_type: int):
    deadline = {1: 14, 2: 7, 3: 1, 4: 0}[task_priority_tag]
    today = datetime.now()
    days_passed = (today - task_create_date).days
    urgency = int(days_passed / max(deadline, 1))
    priority = max(0, min(10, 10 - (urgency * 10)))

    # Ajuste com base no tipo
    if task_type == 1:  # Bug
        priority *= 0.8
    elif task_type == 2:  # Melhoria
        priority *= 1.2

    return max(0, min(10, priority))

class WorkAnalysis:
    """
    A class to analyze work-related data.
    """

    def __init__(self, daily_metrics=None, logging_file=None):
        """
        Initializes the WorkAnalysis class with the provided data.

        """
        logging.basicConfig(filename=logging_file, level=logging.INFO)
        self.__logger = logging.getLogger(__name__)
        self.__logger.info("WorkAnalysis initialized.")

        if daily_metrics == None:
            raise Exception("Metrics not provided")

        self.daily_metrics = daily_metrics

    def get_trimester_metrics(self):
        trimester_goal = self.daily_metrics.get("trimester_goal")
        self.__logger.info(f"1 Trimester goal: {trimester_goal}")
        
        trimester_hours_done1 = self.daily_metrics.get("daily_registries")[-1].get("hours_done_trimester")
        self.__logger.info(f"2 Trimester done hours: {trimester_hours_done1}")
        
        trimester_hours_adjust = self.daily_metrics.get("daily_registries")[-1].get("hours_adjust")
        self.__logger.info(f"3 Trimester adjust hours: {trimester_hours_adjust}")
        
        trimester_total_hours = trimester_hours_done1 + trimester_hours_adjust
        self.__logger.info(f"4 Trimester total done hours (done + adjust): {trimester_total_hours}")
        
        trimester_percent = (trimester_total_hours * 100) / trimester_goal
        trimester_percent = math.floor(trimester_percent)
        self.__logger.info(f"5 Trimester goal done percent (goal vs. done): {trimester_percent}")

        trimester_days = trimester_goal / 8
        trimester_remaining_days = 1 if self.daily_metrics.get("goal_days_remaining").get("days") == 0 else self.daily_metrics.get("goal_days_remaining").get("days")
        self.__logger.info(f"6 Trimester remaining days: {trimester_remaining_days}")
        trimester_remaining_hours = trimester_goal - trimester_total_hours
        trimester_hours_per_day = math.ceil(trimester_remaining_hours / trimester_remaining_days)

        return {
            "trimester_percent": trimester_percent,
            "trimester_goal": trimester_goal,
            "trimester_hours_done": trimester_hours_done1,
            "trimester_hours_adjust": trimester_hours_adjust,
            "trimester_total_hours": trimester_total_hours,
            "trimester_hours_per_day": trimester_hours_per_day,
            "trimester_remaining_days": trimester_remaining_days
        }


if __name__ == "__main__":
    # Load data from file daily_metrics.json
    # load json file if exists, otherwise initialize an empty list
    try:
        with open('./environment/daily-metrics-2025-4.json', 'r') as file:
            daily_metrics = json.load(file)
    except FileNotFoundError:
        print("Arquivo não encontrado.")
        daily_metrics = {}

    # Example usage
    work_analysis = WorkAnalysis(daily_metrics=daily_metrics)
    work_analysis.get_trimester_metrics()
