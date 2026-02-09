# aws_hackathon

Automated interview-prep & hiring-insights agent that scrapes job listings and company intelligence, consolidates data into a spreadsheet, generates interview prep documents, automates outreach and reminders, and reduces duplicate records.

## Project Overview

This project builds an agent-driven toolkit to help candidates discover role-specific information and company insights, track applications, and automate outreach and preparation workflows.

Core ideas:
- Scrape jobs and company info (e.g., Google, Amazon) and enrich results with deeper company intelligence via the LinkUp API.
- Store and maintain a deduplicated record of companies, roles, connections and application history in a spreadsheet.
- Integrate LinkedIn to record direct connections tied to companies and attach those connections to sheet rows.
- Generate a PDF/DOC preparation brief for each company/role containing recent news, projects, interview tips and summary before the interview deadline.
- Automate emails to referrals and follow-ups using intelligence pulled from the record and schedules.
- Track your previous applications and interviews, suggest relevant topics/questions based on past interviews, and surface a concise recap when reapplying.
- Add desktop automation primitives (mail automation, calendar events, reminders, document generation) to reduce daily manual tasks.

## Key Features

- Job + company scraper: crawls job boards and company pages for role postings and metadata.
- LinkUp API enrichment: fetch in-depth company insights, projects, hiring news and public signals.
- LinkedIn integration: attach connections to company rows; flag employees you can contact.
- Google Sheets as canonical store: daily updates, deduplication, history tracking and change logs.
- Document generator: create interview prep PDFs/DOCs including project summaries and talking points.
- Outreach automation: send referral emails and scheduled follow-ups based on candidate preferences.
- Interview-history assistant: recommend topics and questions from previous interviews and produce summarized recap when reapplying.
- Desktop automation hooks: calendar invites, desktop reminders, auto-generated mails and documents.

## Integrations / Tech Choices (suggested)

- LinkUp API (or similar company intelligence API)
- LinkedIn API (or automation using OAuth + scraping fallbacks where permitted)
- Job sources: public job boards (Google Jobs, company careers pages, Amazon jobs) or their RSS/JSON where available
- Google Sheets (or Airtable) as primary datastore
- Document generation: pandoc, wkhtmltopdf, or a library like PDFKit / docx
- Email: SMTP / SendGrid / AWS SES for automated outreach
- Orchestration: a serverless agent (AWS Lambda) or containerized worker with a scheduler (cron / CloudWatch Events)

## Data Flow

1. Scraper crawls job sources for target roles and companies.
2. Results are enriched using the LinkUp API and LinkedIn (to find internal connections).
3. Enriched records are written to the master spreadsheet with deduplication logic.
4. Daily agent job runs to update records, remove duplicates and add new items.
5. When an interview deadline is approaching (or user requests), a prep document is generated and delivered by email or stored in a drive folder.
6. Outreach agent composes and sends referral emails and schedules follow-ups.

## Spreadsheet schema (recommended)

- id (unique)
- company_name
- company_domain
- role_title
- job_link
- source (scraper/linkup/linkedIn)
- found_at (date)
- last_updated (date)
- match_score (how well it fits search)
- linkedin_connections (comma-separated or linked IDs)
- contact_emails
- application_status
- application_dates (history)
- prep_doc_link
- notes

## Setup (high level)

1. Create API credentials for LinkUp (or chosen company-intel API), LinkedIn, Google Sheets and email provider.
2. Configure environment variables:
   - LINKUP_API_KEY
   - LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET
   - SHEETS_CREDENTIALS (or service account JSON path)
   - EMAIL_SMTP_* or SENDGRID_API_KEY / AWS_SES config
3. Install dependencies (language-specific). Example: Node or Python packages for scraping, Google Sheets and PDF generation.
4. Configure the deduplication strategy (e.g., fuzzy match on company_domain + role_title + normalized company name).
5. Deploy scheduler to run the daily update agent (cron, CloudWatch Events, or a hosted job runner).

## Example workflows

- Discover roles: run a role search (e.g., "software engineer - backend"), scraper pushes results to sheet and flags matches.
- Attach connections: query LinkedIn to find first-degree connections at matched companies and add them to the corresponding row.
- Prep docs: when a role status becomes "interview scheduled", auto-generate a PDF brief and email it to the candidate.
- Outreach: send a templated email to referral contacts and schedule follow-ups based on response status.

## Roadmap / Next steps

- Add OAuth flows and robust LinkedIn integration.
- Improve deduplication with a small local vector DB or fuzzy matching library.
- Add automated tests and CI for scrapers and agents.
- Add a simple web UI for searching, viewing prep docs and manual override of sheet rows.
- Add user profiles and preference-driven scheduling for follow-ups and notifications.


