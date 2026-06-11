import json
import csv
import re
import time
from datetime import datetime
from urllib.parse import quote
import requests
import app.extraction.parser as parser
from app.scraping.base_scraper import BaseScraper
from pathlib import Path



# ─── Configuration ────────────────────────────────────────────────────────────
SEARCH_KEYWORDS  = ("Ingénieur Logiciel Stagiaire","Ingénieur","Stagiaire")
LOCATION         = "Tunisia"                                # <-- Change this to any country or city!
LIMIT            = 5                                      # Max results to fetch
DELAY_BETWEEN    = 1.5                                      # Seconds between detail fetches

OUTPUT_JSON = f"dumps/linkedin_dumps.json"
OUTPUT_CSV  = f"dumps/linkedin_dumps.csv"
# ──────────────────────────────────────────────────────────────────────────────

class LinkedInScraper(BaseScraper):
    
    def __init__(self,cookies=None):
        super().__init__()
        
        # Centralized active session state tokens
        
        # Base headers used to interact with LinkedIn's internal business layer
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            
            "X-Restli-Protocol-Version": "2.0.0",
            
        }
    def set_scraping_cookies(self, cookies: dict):
        """
        Takes a dictionary of cookies and formats them into a single 
        HTTP 'Cookie' header string assigned to self.header.
        """
        # 1. Join all key=value pairs with a semicolon and a space
        cookie_string = "; ".join(f"{key}={value}" for key, value in cookies.items())
        
        # 2. Append a trailing semicolon and space to perfectly match your original layout
        if cookie_string:
            cookie_string += "; "
            
        # 3. Assign it to your request headers dictionary
        self.headers["Cookie"] = cookie_string
        self.headers["csrf-token"]=cookies["JSESSIONID"]



    def fetch_linkedin_job_ids(self, keywords : str, location_name: str = "Tunisia", total_jobs_to_fetch: int = 25,) -> list:
        """Step 1: Scrape the list of unique job IDs from search cards using dynamic geoId mapping."""
        base_url = "https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards"
        all_job_ids = set()
        for keyword in keywords:
            encoded_keyword = quote(keyword)            
            for start_index in range(0, total_jobs_to_fetch, 25):
                target_url = (
                    f"{base_url}?"
                    f"decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-220&"
                    f"count=25&"
                    f"q=jobSearch&"
                    f"query=(origin:JOB_SEARCH_PAGE_SEARCH_BUTTON,"
                    f"keywords:{encoded_keyword},"
                    f"locationUnion:(seoLocation:(location:{location_name})),"
                    #f"selectedFilters:(sortBy:List(R),experience:List(1,2))," 
                    f"spellCorrectionEnabled:true)&"                                                 
                    f"start={start_index}"                                                                    
                )
                print(target_url)
            
                try:
                    response = requests.get(target_url, headers=self.headers)
                    print(response.status_code)

                    if response.status_code == 200:
                        parser.parse_job_ids(all_job_ids,response.text)
                        if len(all_job_ids)>=total_jobs_to_fetch:
                            return list(all_job_ids)[:total_jobs_to_fetch]
                    else:
                        print(f"  ⚠️ Error fetching pass {start_index}: HTTP {response.status_code}")
                        break
                except Exception as e:
                    print(f"  ⚠️ Search Error during index pass: {e}")
                    break

        return list(all_job_ids)[:total_jobs_to_fetch]
    
    
    

    def fetch_job_details(self, job_id: str) -> dict:
        """Step 2: Pull specific detailed data metrics matching the exact template output schema."""
        base_url = "https://www.linkedin.com/voyager/api/graphql"
        query_id1 = "voyagerJobsDashJobPostingDetailSections.2bf6cded247cb2f6cc7dcda5558af592"
        variables = f"(cardSectionTypes:List(TOP_CARD,HOW_YOU_FIT_CARD),jobPostingUrn:urn%3Ali%3Afsd_jobPosting%3A{job_id},includeSecondaryActionsV2:true,jobDetailsContext:(isJobSearch:true))"
        url="https://www.linkedin.com/voyager/api/graphql?&variables=(jobPostingUrn:urn%3Ali%3Afsd_jobPosting%3A4423645238)&queryId=voyagerJobsDashJobPostings.891aed7916d7453a37e4bbf5f1f60de4"
        query_id2="voyagerJobsDashJobPostings.891aed7916d7453a37e4bbf5f1f60de4"
        target_url1 = f"{base_url}?variables={variables}&queryId={query_id1}"
        target_url2=f"{base_url}?variables={variables}&queryId={query_id2}"
        details_headers = self.headers.copy()
        details_headers["Accept"] = "application/json"
        
        
        
        try:
            response1 = requests.get(target_url1, headers=details_headers)
            response2 = requests.get(target_url2, headers=details_headers)
            if response1.status_code == 200:
                job_data=parser.parse_job_details(job_id,response1,response2)
                return job_data
            else:
                print(f"  ⚠️ Could not fetch details for job {job_id}: Status {response.status_code}")
        except Exception as e:
            print(f"  ⚠️ Could not fetch details for job {job_id}: {e}")
            
        

    def scrape(self) -> list:
        """Main orchestrator block managing execution output and logging layout frames."""
        print("╔══════════════════════════════════════════════════════╗")
        print("║        LinkedIn Internship Scraper Framework         ║")
        print("╚══════════════════════════════════════════════════════╝\n")
        
        print(f"🔍 Searching: '{SEARCH_KEYWORDS}' | Target Area: {LOCATION} | Type: Internship")
        print(f"   Limit: {LIMIT} | Active Headers Inject Mode: True\n")
        
        job_ids = self.fetch_linkedin_job_ids(SEARCH_KEYWORDS, LOCATION, LIMIT)
        total_found = len(job_ids)
        
        if not job_ids:
            print("⚠️ No results returned. Check cookie/session expiration bounds.")
            return []
            
        print(f"📋 Found {total_found} listings. Fetching details…\n")
        
        completed_jobs = []
        
        for idx, j_id in enumerate(job_ids, start=1):
            try:      
                job_details = self.fetch_job_details(j_id)
                print(f"   [{idx:02d}/{total_found}] {job_details['title']} @ {job_details['company']}")
                completed_jobs.append(job_details)
            except Exception as e:
                print(f"Failed to fetch details for {j_id}")
            
            
            
            time.sleep(DELAY_BETWEEN)
        


        print(f"[PARSING] Parsed {len(completed_jobs)} jobs")
        # ── Write JSON Document Output ──────────────────────────────────────────
        with open(OUTPUT_JSON, "a", encoding="utf-8") as f:
            json.dump(completed_jobs, f, ensure_ascii=False, indent=2)
        print(f"\n✅ JSON saved → {OUTPUT_JSON}")
        
        # ── Write CSV Document Output ───────────────────────────────────────────
        csv_fields = ["job_id", "title", "company", "location", "posted_at",
                      "remote", "apply_url", "description","description_snippet"]
        dumps_path=Path("dumps")
        if not dumps_path.exists():
            Path.mkdir("dumps")
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(completed_jobs)
        print(f"✅ CSV  saved → {OUTPUT_CSV}")
        
        print(f"\n🎉 Done! {len(completed_jobs)} internships scraped.")
        return completed_jobs

if __name__ == "__main__":
    scraper = LinkedInScraper()
    scraper.scrape()