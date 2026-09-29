# Smart University Admissions Assistant

A modern, AI-powered web application designed to streamline the university admissions process for applicants. Built specifically for SDU University (Kazakhstan), this assistant provides instant answers to questions regarding educational programs, tuition fees, UNT requirements, deadlines, and required documents.

## 🚀 Key Features

*   **Hybrid AI Chatbot**: Combines a lightning-fast rule-based NLP engine (token overlap) for standard queries with an optional **Google Gemini** fallback that selects existing catalog entries for unmatched questions. US-3 requirements use a deterministic verified-data lookup before matching.
*   **Dynamic Theme Engine**: Includes two professionally designed UI themes:
    *   **Metro Style** (Active): A strict, corporate, tile-based design with sharp edges, solid colors, and Phosphor vector icons.
    *   **Festival Style**: A vibrant, neon-lit, 3D polygonal design for promotional wow-effects.
    *   *Easily switchable via a single backend config file.*
*   **Single Page Application (SPA)**: Smooth navigation without page reloads, featuring program browsing, FAQ accordions, admission timelines, and interactive document checklists.
*   **Data-Driven**: All programs and FAQs are stored in highly structured JSON files, making it incredibly easy to update university data without touching the code.

## 🛠️ Tech Stack

*   **Backend**: Python, FastAPI, Uvicorn
*   **AI Integration**: Google GenAI SDK (`gemini-3.6-flash`)
*   **Frontend**: Vanilla HTML5, CSS3, JavaScript (No heavy frameworks)
*   **Icons & Typography**: Phosphor Icons, Segoe UI / Open Sans
*   **Testing**: Pytest

## 📂 Project Structure

```text
admissions-assistant/
│
├── app/
│   ├── main.py          # FastAPI application initialization
│   ├── requirements.py  # US3 routing, clarification and publication checks
│   ├── chatbot.py       # Hybrid NLP Engine & Gemini API fallback logic
│   └── database.py      # JSON data loading utilities
│
├── data/
│   ├── programs.json    # Database of SDU Bachelor programs
│   ├── faq.json         # Database of frequently asked questions
│   └── requirements.json # US3 program/category/level requirements
│
├── static/
│   ├── index.html       # Main SPA layout
│   ├── app.js           # Frontend logic and DOM manipulation
│   ├── metro.css        # Strict "Windows 8" tile-based theme
│   ├── festival.css     # Vibrant promotional theme
│   └── config.json      # Dynamic theme configuration
│
├── tests/
│   ├── test_api.py      # Integration tests for FastAPI endpoints
│   └── test_chatbot.py  # Unit tests for NLP engine and AI fallback
│
├── .env                 # Environment variables (API Keys)
└── README.md            # Project documentation
```

## ⚙️ Installation & Setup

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd admissions-assistant
   ```

2. **Set up a Virtual Environment** (Recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   Ensure you have FastAPI, Uvicorn, Google GenAI, and Pytest installed:
   ```bash
   pip install fastapi uvicorn google-genai python-dotenv pytest
   ```

4. **Configure Environment Variables**:
   Optional for non-US3 fallback: create a `.env` file and add your Google Gemini API key. US3 works without a key:
   ```env
   GEMINI_API_KEY=your_google_gemini_api_key_here
   ```

5. **Run the Application**:
   Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload
   ```
   Open your browser and navigate to: `http://localhost:8000`

## 🎨 Theme Configuration

The frontend dynamically loads its UI theme based on `static/config.json`. To switch themes without restarting the server:

1. Open `static/config.json`.
2. Change the `"theme"` value:
   * `"metro"` - Strict, clean, and corporate.
   * `"festival"` - Bright, neon, and heavily animated.
3. Refresh the browser page.

## 🧪 Testing

The project includes a comprehensive test suite to ensure the chatbot logic and API endpoints function correctly. To run the tests:

```bash
pytest
```

## US-3 admission requirements

The existing chat now supports verified requirements and clarifications in English,
Russian and Kazakh. See [US3.md](US3.md) for data provenance, run instructions,
acceptance tests, instructor examples and the remaining synchronization/notification
limitations. Unknown, unapproved and expired values are never substituted.
