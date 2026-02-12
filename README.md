# 🚀 Job Intelligence Agent

An AI-powered CLI tool that automates interview preparation and job search workflows. Say goodbye to fragmented research and missed opportunities—this agent consolidates company intelligence, interview preparation, and calendar management into one streamlined system.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()

---

## ✨ Features

### 🔎 **Job Research Mode**
Generates comprehensive, company-specific interview prep briefs:

- ✅ Recent company highlights (last 30 days)
- 🔗 Top 3 relevant links to company news
- 🧑‍💻 Recent job postings with role insights
- 🧠 Past interview questions (CSV database + auto-fetch)
- 📅 7-day structured prep plan
- 📆 30-day role-specific study roadmap
- 💾 Auto-saves as `.txt` file in `interview_preps/`

**Output Example:**
```
interview_preps/prep_Meta_Software_Engineer.txt
interview_preps/prep_Google_Product_Manager.txt
```

### 📧 **Inbox Scan → Calendar Mode**
Automatically detects and organizes interview emails:

- 🔍 Scans last 30 days of Gmail
- 🎯 AI-powered interview email detection
- 📊 Stage classification:
  - Assessment
  - Phone Screen
  - Technical Interview
  - Onsite / Final Round
  - Recruiter Scheduling
- 📅 Extracts meeting times
- 🗓️ Optional Google Calendar integration


### Email Parsing & Calendar Event Automation

To automatically read emails and generate Google Calendar events, you need the following additional setup:

1.⁠ ⁠*Install Ollama with Llama 3:* This project uses [Ollama](https://ollama.com/) to run the Llama 3 model locally for parsing email content and extracting event details. Make sure Ollama is installed and the Llama 3 model is pulled:
   ⁠ bash
   ollama pull llama3
    ⁠

2.⁠ ⁠*Google API Credentials:* You need a ⁠ credentials.json ⁠ file from the Google Cloud Console to authenticate with Google APIs (Gmail and Calendar). Place the ⁠ credentials.json ⁠ file in the project root directory. To obtain it, create a project in the [Google Cloud Console](https://console.cloud.google.com/), enable the Gmail and Calendar APIs, and download the OAuth 2.0 credentials.

3.⁠ ⁠*Run the automation script:*
   ⁠ bash
   python3 src/event_auto.py
    ⁠
   This script reads your emails using the Llama 3 model via Ollama, extracts event information, and automatically creates corresponding Google Calendar events.

# 🌐 Web UI (React + FastAPI)

A modern minimal web dashboard is included.

## ▶️ How to Run the UI

### 1️⃣ Start Backend (FastAPI)

From project root:

```bash
venv\Scripts\activate   # Windows
# OR
source venv/bin/activate  # Mac/Linux

uvicorn main:app --reload --port 8000

Open a new terminal and run:

cd JIA_ui
npm install
npm run dev


Frontend runs at:

http://localhost:5173


---

## 🏗️ Architecture

```
job_agent.py (Main CLI)
│
├── linkup_job.py          → Company research via Linkup API
├── gmail_reader.py        → Gmail API integration
├── interview_parser.py    → AI-powered email classification
├── calendar_push.py       → Google Calendar automation
├── past_questions.py      → Interview question engine
├── past_questions.csv     → Question database
└── interview_preps/       → Generated prep files
```

**Key Components:**
- **Linkup SDK**: AI-powered company research and news aggregation
- **Gmail API**: Automated inbox scanning
- **Google Calendar API**: One-click interview scheduling
- **Pydantic**: Robust API object validation
- **Custom Parser**: False-positive resistant interview detection

---

## 🛠️ Setup

### 1️⃣ **Clone the Repository**
```bash
git clone https://github.com/patelkirtan29/aws_hackathon
cd job-intelligence-agent
```

### 2️⃣ **Create Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3️⃣ **Install Dependencies**
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install google-api-python-client google-auth google-auth-oauthlib python-dotenv linkup-sdk pydantic python-pptx
```

### 4️⃣ **Configure Linkup API**
Create a `.env` file in the root directory:
```env
LINKUP_API_KEY=your_linkup_api_key_here
```

Get your API key from [Linkup](https://linkup.so)

### 5️⃣ **Setup Gmail API**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Gmail API and Google Calendar API
4. Create OAuth 2.0 credentials
5. Download `credentials.json` and place it in the project root
6. Run the agent once to complete OAuth flow (generates `token.json`)

---

## ▶️ Usage

### Run the Agent
```bash
python3 job_agent.py
```

You'll see:
```
Choose mode: (1) Job Research  (2) Scan Inbox→Calendar  (exit):
```

### 🔎 **Mode 1: Job Research**
```
Choose mode: 1
Company: Meta
Role: Software Engineer
```

**Output:**
- Saves prep file to: `interview_preps/prep_Meta_Software_Engineer.txt`
- Includes: company news, job postings, interview questions, study plans

### 📧 **Mode 2: Inbox Scan**
```
Choose mode: 2
Dry run? (y/n): y
```

**Output:**
```
📊 INTERVIEW SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Assessment (1)
  • Google - Online Assessment
Phone Screen (0)
Technical Interview (2)
  • Meta - Technical Round 1
  • Amazon - Virtual Onsite
Onsite/Final (1)
  • Apple - Final Round Interview
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🧠 Past Questions System

### Manual Entry
Add questions to `past_questions.csv`:

```csv
company,role,stage,topic,difficulty,question,source
Meta,Software Engineer,Coding,Arrays,Medium,Two Sum variant,LeetCode
Google,Product Manager,Behavioral,Leadership,Medium,Tell me about a time you led a team,Glassdoor
```

### Auto-Fetch Fallback
If no matching questions are found:
- Agent automatically searches public sources
- Adds curated questions to the prep file
- Maintains quality over quantity

---

## 📁 File Structure

```
job-intelligence-agent/
├── job_agent.py              # Main CLI interface
├── linkup_job.py             # Company research module
├── gmail_reader.py           # Gmail integration
├── interview_parser.py       # Email classification engine
├── calendar_push.py          # Calendar automation
├── past_questions.py         # Question retrieval system
├── past_questions.csv        # Question database
├── prep_*.py                 # Various prep automation scripts
├── storage.py                # Data persistence
├── token.json                # Gmail OAuth token (auto-generated)
├── credentials.json          # Google API credentials
├── .env                      # API keys (not tracked)
├── requirements.txt          # Python dependencies
├── interview_preps/          # Auto-generated prep files
│   ├── prep_Meta_Software_Engineer.txt
│   └── prep_Google_Product_Manager.txt
└── README.md                 # This file
```

---

## 🎯 Why This Matters

### Before: Chaos
- Manual company research
- Missed interview emails
- Scattered preparation resources
- No structured strategy

### After: Confidence
- 70% reduction in research time
- Zero missed interviews
- Centralized, structured prep files
- Company + role-aware preparation
- Automated workflow

---

## 🛑 Troubleshooting

### ❌ `LinkupSourcedAnswer has no attribute 'get'`
**Solution:** Update to latest version—Pydantic objects are now normalized internally.

### ❌ `FileNotFoundError: prep_Meta_AI/ML_Engineer.txt`
**Solution:** Fixed—filenames are automatically sanitized (e.g., `AI/ML` → `AI_ML`).

### ❌ Gmail API Quota Exceeded
**Solution:** The agent respects Gmail API limits. Run scans no more than once per hour.

### ❌ `credentials.json not found`
**Solution:** Download OAuth credentials from Google Cloud Console and place in project root.

---

## 📈 Future Roadmap

- [ ] Web dashboard UI
- [ ] Markdown/PDF export options
- [ ] Notion integration
- [ ] Application tracking system
- [ ] Resume optimization module
- [ ] AI mock interviewer
- [ ] Multi-platform support (LinkedIn, Indeed)
- [ ] Analytics dashboard
- [ ] Cloud-hosted SaaS version

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👏 Acknowledgments

- **Linkup API** for AI-powered company research
- **Google APIs** for Gmail and Calendar integration
- Built during AWS Hackathon 2025

---

## 📧 Contact

For questions or feedback, please open an issue on GitHub.

---

## Demo Videos

- **Linkedin Connections CLI demo** — Watch the feature walkthrough: https://drive.google.com/file/d/14urTEl-rlFhKgtHoIe6mQrwn5YrlHf1m/view
- **Calendar Invite CLI demo** — Watch the feature walkthrough: https://drive.google.com/file/d/19oh5TgXhd0YVPzWp9v8R3Eifmt2UreJY/view
- **Job research and Email scan UI demo** — Watch the feature walkthrough: https://drive.google.com/file/d/1h6eV_fHLAlD0FLyw56byrdQY6NNh5vj3/view

---

**Built with ❤️ to make job searching less stressful and more strategic.**