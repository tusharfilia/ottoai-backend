from datetime import datetime, timedelta
from typing import Optional, Dict
import calendar

class DateCalculator:
    def __init__(self, reference_date: Optional[datetime] = None):
        self.reference_date = reference_date or datetime.now()
        self.weekday_map = {day.lower(): i for i, day in enumerate(calendar.day_name)}
        
    def round_time(self, dt: datetime, round_to: int = 30) -> datetime:
        """
        Round a datetime object to the nearest increment of minutes
        
        Args:
            dt: datetime object to round
            round_to: number of minutes to round to (default 30 for half hour)
        """
        minutes = dt.minute
        rounded_minutes = round((minutes / round_to)) * round_to
        
        # Handle case where rounding results in 60 minutes
        if rounded_minutes == 60:
            return dt.replace(hour=dt.hour + 1, minute=0, second=0, microsecond=0)
        
        return dt.replace(minute=int(rounded_minutes), second=0, microsecond=0)

    def calculate_date(self, params: Dict) -> Optional[datetime]:
        """
        Calculate a date based on parameters extracted from natural language.
        
        params = {
            "relative_day": "next"/"this"/"last" (optional),
            "weekday": "monday"/"tuesday"/etc. (optional),
            "weeks_offset": int (optional),
            "days_offset": int (optional),
            "months_offset": int (optional),
            "time": "14:00"/"2pm"/etc. (optional),
            "specific_date": "2024-03-15" (optional),
            "round_to": int (optional, minutes to round to)
        }
        """
        try:
            if params.get("specific_date"):
                result_date = datetime.strptime(params["specific_date"], "%Y-%m-%d")
            else:
                result_date = self.reference_date

                # Handle month offset
                if params.get("months_offset"):
                    months = params["months_offset"]
                    # Simple month addition (note: this is a basic implementation)
                    new_month = result_date.month + months
                    new_year = result_date.year + (new_month - 1) // 12
                    new_month = ((new_month - 1) % 12) + 1
                    result_date = result_date.replace(year=new_year, month=new_month)

                # Handle week offset
                if params.get("weeks_offset"):
                    result_date += timedelta(weeks=params["weeks_offset"])

                # Handle day offset
                if params.get("days_offset"):
                    result_date += timedelta(days=params["days_offset"])

                # Handle weekday references
                if params.get("weekday"):
                    target_weekday = self.weekday_map[params["weekday"].lower()]
                    current_weekday = result_date.weekday()
                    days_until_target = (target_weekday - current_weekday) % 7

                    if params.get("relative_day") == "next":
                        if days_until_target == 0:
                            days_until_target = 7
                    elif params.get("relative_day") == "last":
                        days_until_target = days_until_target - 7

                    result_date += timedelta(days=days_until_target)

            # Handle time
            if params.get("time"):
                time_str = params["time"].lower()
                
                # Handle AM/PM format
                if "pm" in time_str:
                    hour = int(time_str.replace("pm", "").strip())
                    hour = hour + 12 if hour != 12 else hour
                elif "am" in time_str:
                    hour = int(time_str.replace("am", "").strip())
                    hour = 0 if hour == 12 else hour
                else:
                    # Handle 24-hour format
                    if ":" in time_str:
                        hour = int(time_str.split(":")[0])
                    else:
                        hour = int(time_str)
                
                # Set the time
                result_date = result_date.replace(hour=hour, minute=0, second=0, microsecond=0)

            # Round the time if specified
            round_to = params.get("round_to", 60)  # Default to hour if not specified
            result_date = self.round_time(result_date, round_to)

            return result_date

        except Exception as e:
            print(f"Error calculating date: {str(e)}")
            return None

    def format_date(self, date: datetime) -> str:
        """Format a datetime object into the required string format."""
        if date:
            return date.strftime("%Y-%m-%d %H:%M:%S")
        return None 