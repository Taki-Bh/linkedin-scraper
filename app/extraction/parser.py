import requests
from datetime import datetime
import re

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





def parse_job_details(job_id,response1,response2):



    job_data=dict(job_data_temp)


    job_data["job_id"]=job_data["job_id"].format(job_id=job_id)
    job_data["posted_at"]=datetime.now().strftime("%Y-%m-%d %H:%M")
    job_data["apply_url"] =job_data["apply_url"].format(job_id=job_id)



    data1 = response1.json()
    data2 = response2.json()


    print(data1)
    print("--------------------------------------------------------------------------------")
    print(data2)
    print("--------------------------------------------------------------------------------")
                
            # Use integrated class utilities to evaluate elements
    company_record = fetch_company_master_record(data1)
    subtitles = extract_job_subtitles(data1)
                
                # Apply dynamic parsed elements onto baseline schema dict
    if company_record.get("name"):
        job_data["company"] = company_record.get("name")
    elif subtitles.get("summary_line"):
                    # Quick extraction split if baseline profile records fall through
        job_data["company"] = subtitles.get("summary_line").split("·")[0].strip()
                
    if subtitles.get("display_title"):
        job_data["title"] = subtitles.get("display_title")

                # Fallback Regex Extractions for descriptions and attributes
    response_text = response1.text
    location_matches = re.findall(r'"formattedLocation":"([^"]+)"', response_text)
    if location_matches:
        job_data["location"] = location_matches[0]
                
    if '"workRemoteAllowed":true' in response_text or '"workPlaceIndicator":"REMOTE"' in response_text:
        job_data["remote"] = True
                
    all_text_blocks = re.findall(r'"text":"([^"]+)"', response2.text)
    if all_text_blocks:
        longest_block = max(all_text_blocks, key=len)
        clean_desc = longest_block.replace("\\n", "\n").replace('\\"', '"')
        job_data["description_full"] = clean_desc
        job_data["description_snippet"] = clean_desc[:500].replace("\n", " ")    
    return job_data
