import requests
from datetime import datetime
import re
import json
#datetime.now().strftime("%Y-%m-%d %H:%M")
job_data_temp = {
        "job_id": "{job_id}",
        "title": "Unknown Title",
        "company": "Unknown Company",
        "location": "",  
        "posted_at": "", 
        "remote": False,
        "apply_url": "https://www.linkedin.com/jobs/view/{job_id}",
        "description_snippet": "",
        "description_full": ""
    }





def parse_job_ids(jobs_ids,response_txt):
    print("[PARSING] Parsing jobs...")
    found_ids = re.findall(r"jobPosting:(\d+)", response_txt)
    jobs_ids.update(found_ids)


def get_top_card(payload: dict) -> dict:
    """Safely isolates the topCard configuration dict from the GraphQL payload elements list."""
    try:
        elements = payload.get("data", {}).get("jobsDashJobPostingDetailSectionsByCardSectionTypes", {}).get("elements", [])
        for element in elements:
            for section in element.get("jobPostingDetailSection", []):
                if "topCard" in section and section["topCard"] is not None:
                    return section["topCard"]
    except (KeyError, AttributeError):
        pass
    return {}

def fetch_company_master_record( payload: dict) -> dict:
    """Extract company profile record from the nested dictionary tree."""
    top_card = get_top_card(payload)
    return top_card.get("jobPosting", {}).get("companyDetails", {}).get("jobCompany", {}).get("company", {})

def extract_job_subtitles( payload: dict) -> dict:
    """Extract job subtitles and titles from topCard directly."""
    top_card = get_top_card(payload)
    if top_card:
        return {
            "summary_line": top_card.get("navigationBarSubtitle"),
            "display_title": top_card.get("jobPostingTitle")
        }
    return {}
def extract_company_name(json_text):
    try:
        # Parse the JSON string into a Python dictionary
        payload = json.loads(json_text)
        
        # Iterate through the 'included' array
        for item in payload.get("included", []):
            # Check if this specific item is the Company entity
            if item.get("$type") == "com.linkedin.voyager.dash.organization.Company":
                return item.get("name")
                
        return "Company name not found in the payload."
        
    except json.JSONDecodeError:
        return "Error: Invalid JSON format."
def parse_job(response):

    def get(d, *keys, default=None):
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k)
            if d is None:
                return default
        return d

    def ts_to_datetime(ts):
        if ts is None:
            return None

        # LinkedIn timestamps are milliseconds
        return datetime.fromtimestamp(ts / 1000)

    def extract_company_id():
        urn = get(
            response,
            "companyDetails",
            "com.linkedin.voyager.jobs.JobPostingCompany",
            "company"
        )

        if not urn:
            return None

        try:
            return int(urn.split(":")[-1])
        except Exception:
            return None
    def extract_company_name():
        try:
            return (
                response["companyDetails"]
                ["com.linkedin.voyager.jobs.JobPostingCompany"]
                .get("companyName")
            )
        except Exception:
            return None
    return {
        # Basic
        "job_id": response.get("jobPostingId"),
        "title": response.get("title"),

        # Company
        "company_id": extract_company_id(),
        
        "apply_url": get(
            response,
            "applyMethod",
            "com.linkedin.voyager.jobs.OffsiteApply",
            "companyApplyUrl"
        ) or f"https://www.linkedin.com/jobs/search/?currentJobId={response.get("jobPostingId")}",

        "company_description": get(
            response,
            "companyDescription",
            "text"
        ),

        # Benefits
        "benefits": response.get("benefits", []),

        # Location
        "country": response.get("country"),
        "location": response.get("formattedLocation"),

        # Dates
        "created_at": ts_to_datetime(
            response.get("createdAt")
        ),

        "posted_at": ts_to_datetime(
            response.get("listedAt")
        ),

        "expire_at": ts_to_datetime(
            response.get("expireAt")
        ),

        # Description
        "description": get(
            response,
            "description",
            "text"
        ),

        # Employment
        "employment_status": (
            response.get("formattedEmploymentStatus")
            or response.get("employmentStatus")
        ),

        # Salary (flattened)
        "salary_description": response.get(
            "formattedSalaryDescription"
        ),

        "salary_available": get(
            response,
            "salaryInsights",
            "jobCompensationAvailable"
        ),

        "salary_insight_exists": get(
            response,
            "salaryInsights",
            "insightExists"
        )
    }

