# Weather-Smart Fulfillment Architect — Green Chef / HelloFresh Capstone

**Program:** Virginia Tech Masters of Science in Business Analytics — MGT 5905 Capstone, Spring 2026  
**Team:** Aakash Nihalaney, Avi Gupta, Harsh Sahu, Om Kapdoskar  
**Industry Sponsor:** HelloFresh / Green Chef  
**Faculty Advisor:** Prof. Sean Raines  
**Sponsor Advisor:** Kayla Baber

> *Note: This project was completed under a non-disclosure agreement with HelloFresh. Raw customer data and proprietary pricing files are not included in this repository.*

---

## Overview

Green Chef is a USDA certified organic meal kit brand owned by HelloFresh, serving a customer base that is 75% sustainability conscious. Despite strong brand equity, a measurable gap exists between the brand's sustainability values and the packaging experience customers receive weekly.

This capstone project was commissioned to close that gap. Drawing on a January 2024 packaging survey of 619 customers, twelve months of Chattermill review data, Q1 2026 cancellation records covering 21,000+ comments, and Green Chef's internal SAP pricing data, the team identified key drivers of packaging dissatisfaction and delivered three actionable recommendations backed by full economic analysis.

**Key findings:**
- Plastic reduction is the #1 requested improvement at 48% of open-ended responses
- 4,211 Q1 2026 cancellations contained packaging or freshness-related language (19.2% of all cancellations)
- Combined 3-year NPV of $158,030 across two packaging tiers
- Tier 1 (Nutri-Ice): 5.3% ROI, 11.4-month payback
- Tier 2 (full sustainable materials transition): 28.4% ongoing ROI, 25.6-month break-even

---

## Deliverables

### 1. Weather-Smart Fulfillment Architect (Python/Streamlit App)

A working prototype of an AI-powered packing floor system that dynamically adjusts packaging materials based on destination weather conditions, integrated with Green Chef's existing Katana ERP and Pick-to-Light warehouse systems.

├── app.py              # Streamlit UI — packing floor worker interface
├── api_client.py       # Katana ERP integration layer
├── weather_engine.py   # AI Weather Decision Engine
├── p2l_controller.py   # Pick-to-Light hardware coordinator
├── database.py         # SQLite database layer
├── mock_data.json      # Test data: orders across Phoenix AZ, Minneapolis MN, Miami FL
└── requirements.txt    # Python dependencies

**Weather decision rules:**

| Condition | Action |
|-----------|--------|
| Temp > 85°F | Add 3× XL Ice Packs + Thermal Foil Liner |
| Temp < 32°F | Remove ice packs + Add Cotton Insulation Sleeve |
| Precipitation > 50% | Add Waterproof Poly-Wrap + Reinforced Seam Tape |
| API failure | Default to Standard Regional Packaging, log WARNING |

**Quick start:**
```bash
pip install -r requirements.txt
streamlit run app.py
```
Runs fully on mock data without any API keys. To use live weather data, set `OWM_API_KEY` as an environment variable.

### 2. Packaging & Marketing Strategy (HTML)
`GC_Packaging_Marketing_Strategy.html` — tiered marketing strategy to convert packaging improvements into measurable churn reduction and reacquisition outcomes.

### 3. Full Capstone Report
`Team3_Capstone_Final_Report.pdf` — complete analysis including initial findings, competitive landscape, economic analysis (NPV, ROI, payback period), and three detailed recommendations.

### 4. Final Presentation
`Team3_Capstone_Final_Presentation.pptx` — executive-level presentation delivered to HelloFresh/Green Chef sponsor advisors.

---

## Recommendations Summary

1. **Phased Sustainable Packaging Overhaul** powered by the Weather-Smart AI Packing Assistant, integrated with Katana ERP and Pick-to-Light systems
2. **Tiered Marketing Strategy** to convert packaging improvements into measurable churn reduction and customer reacquisition
3. **QR Code Disposal Webapp** providing zip code specific recycling guidance for every packaging component

---

## Tools & Technologies
- Python, Streamlit, SQLite
- OpenWeatherMap API, Katana ERP API
- Tableau (sentiment analysis of customer reviews)
- SAP pricing data, Chattermill NLP review platform
