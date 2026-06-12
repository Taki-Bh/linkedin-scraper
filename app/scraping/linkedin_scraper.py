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
import requests


def build_session_from_headers(headers: dict) -> requests.Session:
    """
    Create a requests.Session from headers containing a full Cookie string.
    """

    session = requests.Session()

    # --- copy normal headers (except Cookie) ---
    for k, v in headers.items():
        if k.lower() != "cookie":
            session.headers[k] = v

    # --- extract and parse Cookie header ---
    cookie_header = headers.get("Cookie") or headers.get("cookie")

    if cookie_header:
        # split "a=b; c=d" into dict
        cookies = {}
        for part in cookie_header.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k] = v

        # inject into session cookie jar
        for k, v in cookies.items():
            session.cookies.set(k, v, domain=".www.linkedin.com")

    return session
class LinkedInScraper(BaseScraper):

    def __init__(self,cookies=None):
        super().__init__()

        # Centralized active session state tokens

        # Base headers used to interact with LinkedIn's internal business layer
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "Referer": "https://www.linkedin.com/jobs/",
            "X-Restli-Protocol-Version": "2.0.0",

        }
    def set_scraping_cookies(self, cookies: dict):
        cookie_string = "; ".join(f"{k}={v}" for k, v in cookies.items())

        self.headers["Cookie"] = cookie_string

        # FIX: correct CSRF header name
        self.headers["Csrf-Token"] = cookies["JSESSIONID"]



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

        base_url = "https://www.linkedin.com/voyager/api/jobs/jobPostings/"
        target_url = f"{base_url}{job_id}"



        base_url1 = "https://www.linkedin.com/voyager/api/graphql"
        query_id1 = "voyagerJobsDashJobPostingDetailSections.2bf6cded247cb2f6cc7dcda5558af592"
        variables = f"(cardSectionTypes:List(TOP_CARD,HOW_YOU_FIT_CARD),jobPostingUrn:urn%3Ali%3Afsd_jobPosting%3A{job_id},includeSecondaryActionsV2:true,jobDetailsContext:(isJobSearch:true))"
        #url="https://www.linkedin.com/voyager/api/graphql?&variables=(jobPostingUrn:urn%3Ali%3Afsd_jobPosting%3A4423645238)&queryId=voyagerJobsDashJobPostings.891aed7916d7453a37e4bbf5f1f60de4"
        #query_id2="voyagerJobsDashJobPostings.891aed7916d7453a37e4bbf5f1f60de4"
        target_url1 = f"{base_url1}?variables={variables}&queryId={query_id1}"
        #target_url2=f"{base_url}?variables={variables}&queryId={query_id2}"
        details_headers = self.headers.copy()
        print("Fetching:", target_url)

        # build session ONCE
        session = build_session_from_headers(self.headers)

        # FIX: proper CSRF
        jsessionid = self.headers.get("Csrf-Token", "")
        session.headers.update({
            "Csrf-Token": jsessionid,
            "X-RestLi-Protocol-Version": "2.0.0",
            "Referer": "https://www.linkedin.com/jobs/",
            "Accept": "application/json",
        })

        try:
            response1 = session.get(target_url, timeout=15)
            response2 = requests.get(target_url1, headers=details_headers)

            print("STATUS:", response1.status_code)

            if response1.status_code == 200:
                try:
                    data1 = response1.json()
                    
                    
                except Exception:
                    print("Invalid JSON:", response1.text[:300])
                    return None
                parsed_job=parser.parse_job(data1)
                parsed_job["company"]=parser.extract_company_name(response2.text)
                print(parsed_job["company"])
                return parsed_job

            else:
                print("ERROR:", response1.status_code)
                print(response1.text[:300])
                return None

        except Exception as e:
            print("Request failed:", e)
            return None



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
                print(job_details)
                print(f"   [{idx:02d}/{total_found}] {job_details['title']} @ {job_details['company']}")
                completed_jobs.append(job_details)
            except Exception as e:
                print(f"Failed to fetch details for {j_id}")



            time.sleep(DELAY_BETWEEN)



        print(f"[PARSING] Parsed {len(completed_jobs)} jobs")
        # ── Write JSON Document Output ──────────────────────────────────────────
        with open(OUTPUT_JSON, "a", encoding="utf-8") as f:
            json.dump(completed_jobs, f, ensure_ascii=False, indent=2,default=str)
        print(f"\n✅ JSON saved → {OUTPUT_JSON}")

        # ── Write CSV Document Output ───────────────────────────────────────────
        csv_fields = ["job_id", "title", "company", "location", "posted_at","created_at","expire_at",
                      "remote", "apply_url", "description","description_snippet","company_description","company_id","employment_status","salary_description","salary_available"]
        dumps_path=Path("dumps")
        if not dumps_path.exists():
            Path.mkdir("dumps")
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            print(completed_jobs)
            writer.writerows(completed_jobs)
        print(f"✅ CSV  saved → {OUTPUT_CSV}")

        print(f"\n🎉 Done! {len(completed_jobs)} internships scraped.")
        return completed_jobs

if __name__ == "__main__":
    scraper = LinkedInScraper()
    scraper.scrape()