from job_agent import JobIntelligenceAgent

def main():
    print("AI is initialized\n")
    agent = JobIntelligenceAgent()
    jobs = agent.fetch_recent_jobs(company="Google", role="Software Engineer", max_results=5)
    for job in jobs:
        agent.dedupe_and_add(job)
        
if __name__ == "__main__":
    main()