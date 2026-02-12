# 💻 EXACT VS CODE SETUP STEPS
## What to Do Right Now

---

## 🎯 FROM YOUR SCREENSHOT - DO THIS:

### **STEP 1: Create Project Folder**

**On your VS Code welcome screen, click:**
1. **"Open..."** (the folder icon)
2. Navigate to Desktop or Documents
3. Click "New Folder"
4. Name: `job-intelligence-agent`
5. Click "Select Folder"

**VS Code reloads with your project!**

---

### **STEP 2: Open Terminal**

**In VS Code menu:**
- **Terminal** → **New Terminal**

**Or press:** `` Ctrl+` ``

**Terminal appears at bottom! ✅**

---

### **STEP 3: Quick Setup**

**In VS Code terminal, paste ALL of this:**

```bash
# Create folders
mkdir demo_jobs interview_prep_docs

# Create requirements
echo "streamlit
requests
python-dotenv" > requirements.txt

# Create sample job
echo "Company: Google
Role: Software Engineer
Description: AI team position" > demo_jobs/google_swe.txt

# Create .env for API key
echo "LINKUP_API_KEY=your_key_here" > .env

echo "✅ Setup done! Now add Python files."
```

---

### **STEP 4: Add Python Files**

**Download from chat above:**
- job_agent.py
- linkup_job.py

**Then drag into VS Code (left sidebar)**

**OR:**

Right-click in VS Code → New File → Name it → Paste code

---

### **STEP 5: Test**

**In VS Code terminal:**
```bash
python3 job_agent.py
```

**Should see: "JOB PROCESSING COMPLETE" ✅**

---

## 🚀 TOMORROW (8:30 AM):

1. Open VS Code → Open job-intelligence-agent folder
2. Terminal → New Terminal
3. Add real Linkup API key to .env
4. Build Streamlit UI
5. Demo!

**You're ready!** 🎯
