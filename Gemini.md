Onyx Portfolio Terminal | Full System Architecture
1. Executive Summary
The Onyx Portfolio Terminal is a "Solid-State" financial dashboard designed for high-frequency monitoring on mobile (iPhone). It replaces heavy server-side processing with a Client-Side Data Engine built on IndexedDB, enabling near-instant filtering, sorting, and visualization of stock fundamentals.
2. System Architecture
The application is orchestrated across three distinct layers, ensuring that data integrity is maintained from the flat-file source to the interactive UI.
A. The Data Engine (Persistence)
Instead of a standard relational database, the app uses a Flat-DB pattern.
• Engine: IndexedDB (Browser-native).
• Store: Portfolio (Single Object Store).
• Primary Key: SYM (Ticker Symbol).
• Strategy: On boot, the engine ingests fundamentals.json, normalizes field names (e.g., avgBuy → AVG), and pre-calculates financial metrics (COST, PNL, PNL_PCT) before committing to disk.
B. The Orchestration Layer (Memory)
To achieve zero-lag interactions, the app utilizes Hydration Orchestration:
1.	Pull: The engine pulls the entire Flat-DB into a global MASTER_DATA array.
2.	Map: A virtual index is created in memory to group stocks by SECTOR.
3.	Watch: The UI components (Chart & Table) "watch" this memory array. When a filter is applied, the array is sliced in-memory, bypassing the database for speed.
C. The View Layer (UI/UX)
• KPI Strip: Aggregates portfolio-wide totals into Lakhs (₹0.00L).
• Single-Line Tape Chart: A stacked: true horizontal bar representing asset allocation. Each segment's width is proportional to the Investment Amount (COST).
• Interactive Heatmap: A CSS-driven table that uses background color-coding for P&L and ROE performance.
3. GitHub Setup & Deployment Strategy
Since development and deployment are handled via iPhone, the GitHub workflow is optimized for a "no-build" (Zero-Compile) deployment.
A. Repository Structure

/portfolio-terminal
├── index.html          # The Orchestrator (UI + Engine)
├── fundamentals.json   # Raw Data Source
├── README.md           # System Documentation
└── .github/workflows/  # (Optional) Auto-update logic

B. Deployment via GitHub Pages
1.	Push to Main: Upload index.html and fundamentals.json to your repository.
2.	Enable Pages: Go to Settings > Pages and set the source to Deploy from a branch (Main).
3.	Site URL: Your terminal is now live at https://[username].github.io/[repo-name]/.
C. The "Gist" Update Method (Mobile Workflow)
For quick data updates without full Git commits:
• Store fundamentals.json as a GitHub Gist.
• Update the fetch() URL in index.html to point to the Raw Gist URL.
• This allows you to update your portfolio data by simply editing a Gist on your iPhone, which instantly reflects in the terminal.
4. Component Interaction Flow

5. Technical Specifications
Data Loading Strategy
We employ a Tiered Loading Lifecycle:
• Tier 1 (Fetch): Asynchronous retrieval of the JSON source.
• Tier 2 (Compute): Calculation of derived values (LTP vs AVG) at the engine level.
• Tier 3 (Hydrate): Transfer of data from the Flat-DB to the MASTER_DATA global object.
• Tier 4 (Render): Concurrent execution of Chart.js and Table DOM construction.
UI Styling (Onyx Theme)
• Color Palette: Black (#000), Cyan (#00f2ff), Emerald Green (#064e3b), and Ruby Red (#7f1d1d).
• Typography: JetBrains Mono for a terminal/coding aesthetic.
• Visibility: Forced white text (#fff) on all data fields for iPhone readability.
6. Planned Engine Enhancements
• Delta Updates: Implementing a "Diff" engine to update only changed LTP values without re-writing the entire Flat-DB.
• Batch Engine: Capability to delete or archive sectors directly from the Tape Chart interface.
