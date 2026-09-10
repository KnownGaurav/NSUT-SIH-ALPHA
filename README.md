# Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains

## SIH 2026 Project

A real-time, data-driven system for dynamically forecasting the Expected Time of Arrival (ETA) of coaching trains using current train conditions, historical running patterns, and operational data.

---

## 1. Project Information

- **Project Title:** Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains
- **PS ID:** 26028
- **PS Title:** Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains
- **Category:** Software
- **Theme:** Transportation & Railways
- **Team Name:** Alpha

### Project Links

- **GitHub Repository:**  
  `____________________________________________`

- **Project PPT:**  
  `____________________________________________`

---

## 2. Problem Statement

Existing train ETA predictions often rely on scheduled timings, current delays, and predefined recovery times. These approaches may not accurately reflect real-time railway conditions such as variations in train speed, congestion, operational delays, unscheduled stoppages, signal halts, and historical running patterns.

As a result, passengers may receive inaccurate arrival information, while railway staff face difficulties in platform planning, station operations, crew coordination, and downstream service management.

There is a need for a dynamic ETA prediction system that continuously adapts its predictions according to actual train movement and historical data.

---

## 3. Proposed Solution

Our solution is a **Dynamic Train ETA Forecasting System** designed to provide continuously updated and data-driven arrival predictions for coaching trains.

The system combines real-time train information with historical journey records to estimate the expected arrival time of a train at upcoming stations and its destination.

Instead of relying only on scheduled timings, the system considers the train's current running condition and historical patterns to dynamically update its ETA.

The system also provides a confidence score for each prediction, helping users understand the reliability of the forecast.

---

## 4. Key Features

### Real-Time Train Tracking
Tracks the current position and movement of a train during its journey.

### Current Speed Monitoring
Displays the train's current speed to provide visibility into its real-time running condition.

### Dynamic ETA Prediction
Forecasts the expected arrival time at upcoming stations and continuously updates the prediction as train conditions change.

### Confidence Score
Provides a confidence score along with the predicted ETA to indicate the reliability of the forecast.

### Historical Data-Based Forecasting
Uses previous train running records and historical journey patterns to improve ETA predictions.

### Route Visualization
Displays the route being followed by the train and its journey progress.

### Station-Wise Information
Provides arrival and departure information for individual stations along the train's route.

### Real-Time Updates
Updates train information and ETA predictions as new operational data becomes available.

---

## 5. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend Framework | FastAPI (Python 3.12) | High-performance backend APIs and asynchronous processing |
| Prediction Modeling | XGBoost / LightGBM | ETA prediction using structured and sectional train data |
| Real-Time Pipeline | WebSockets + In-Memory/Redis | Real-time train position and ETA updates |
| Database | PostgreSQL / PostGIS | Storage of train data, historical records and geospatial information |
| Frontend Framework | React + Vite | Interactive real-time dashboard |
| Styling | Tailwind CSS | Responsive and consistent interface styling |
| Mapping Engine | MapLibre GL / Leaflet | Train route and location visualization |
| Data Processing | NumPy, Pandas | Data processing and feature preparation |
| ML Framework | Scikit-learn, XGBoost | Machine learning and prediction pipeline |
| API Validation | Pydantic | Request and response validation |

---

## 6. System Architecture

The system follows a real-time data processing and prediction architecture.

```text
                    ┌─────────────────────┐
                    │   Train Data Source │
                    │ GPS / Operational   │
                    │ Historical Records  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Real-Time Data      │
                    │ Processing Pipeline │
                    │ WebSockets / Redis  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Feature Engineering │
                    │ Speed / Delay /     │
                    │ Route / History     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ ETA Prediction      │
                    │ XGBoost / LightGBM  │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
       ┌──────────────────┐        ┌──────────────────┐
       │ PostgreSQL /     │        │ FastAPI Backend  │
       │ PostGIS Database │        │      APIs        │
       └──────────────────┘        └────────┬─────────┘
                                            │
                                            ▼
                                  ┌────────────────────┐
                                  │ React + Vite       │
                                  │ Real-Time Dashboard│
                                  └────────────────────┘
7. How the System Works
Step 1: Collect Train Data

The system receives train movement and operational information such as:

Current train location
Current speed
Train route
Station information
Historical running records
Previous arrival and departure timings
Delay information
Step 2: Process Real-Time Information

Incoming train data is processed through the real-time pipeline. WebSockets and in-memory/Redis-based processing allow train information and ETA predictions to be updated without relying entirely on periodic polling.

Step 3: Generate Prediction Features

Relevant information such as current speed, route progress, historical running patterns, delays, and sectional information is converted into features for the prediction model.

Step 4: Predict ETA

The trained machine-learning model predicts the expected arrival time at upcoming stations and the destination.

Step 5: Calculate Prediction Confidence

A confidence score is provided with the ETA to communicate the reliability of the prediction.

Step 6: Display Results

The React-based dashboard displays:

Current train location
Current speed
Train route
Expected arrival time
Confidence score
Station-wise arrival and departure information

The information can be continuously updated as the train progresses.

8. Repository Structure
PROJECT/
├── assets/
│   └── screenshots/
│
├── data/
│
├── docs/
│
├── frontend/
│
├── models/
│
├── src/
│
├── submission/
│
├── tests/
│
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.md
├── SUBMISSION_GUIDE.md
├── docker-compose.yml
├── pyest.ini
└── requirements.txt
Directory Description
Directory/File	Purpose
assets/	Project assets and screenshots
data/	Data used for processing and model development
docs/	Technical and architectural documentation
frontend/	React + Vite frontend application
models/	Trained ML models and model-related files
src/	Backend source code and application logic
submission/	SIH submission-related materials
tests/	Automated tests
.env.example	Example environment configuration
Dockerfile	Container configuration
docker-compose.yml	Multi-service deployment configuration
requirements.txt	Python dependencies
README.md	Project documentation
9. Major Functional Modules
Train Tracking Module

Provides the current location, movement status, speed, and route progress of the selected train.

ETA Prediction Module

Uses real-time and historical information to dynamically estimate arrival times at upcoming stations.

Historical Analysis Module

Uses previous train journeys and running patterns to support more accurate predictions.

Station Management Module

Displays station-wise arrival and departure information along the train's route.

Route Mapping Module

Uses MapLibre GL / Leaflet to visualize the train's geographical route and current position.

Real-Time Communication Module

Uses WebSockets and in-memory/Redis-based processing to deliver updated train and ETA information to the frontend.

10. Installation
Clone the Repository
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_PROJECT_FOLDER>
Create a Python Virtual Environment
python -m venv venv

Activate the environment.

Windows:

venv\Scripts\activate

Linux/macOS:

source venv/bin/activate
Install Backend Dependencies
pip install -r requirements.txt
11. Environment Configuration

Create a .env file using .env.example as a reference.

cp .env.example .env

Configure the required database, API, and application settings according to the deployment environment.

Do not commit .env files containing passwords, API keys, tokens, or other secrets.

12. Running the Backend

Start the FastAPI application using:

uvicorn src.main:app --reload

The backend provides APIs for train information, ETA predictions, station information, and real-time updates.

13. Running the Frontend

Navigate to the frontend directory:

cd frontend

Install dependencies:

npm install

Start the development server:

npm run dev

The frontend provides the interactive dashboard for monitoring train movement and ETA forecasts.

14. Testing

The project includes automated tests under:

tests/

Run the test suite using:

pytest

For asynchronous tests:

pytest

The testing setup uses pytest and pytest-asyncio.

15. Docker Deployment

The project includes Docker configuration for easier deployment and environment consistency.

Build and start the services using:

docker compose up --build

This allows the application components to be run together in a containerized environment.

16. API Integration

The backend is designed to expose APIs that can be integrated with:

Passenger mobile applications
Railway information dashboards
Station display systems
Control-room monitoring systems
Other railway operational services

The API architecture allows real-time ETA information to be consumed by multiple client applications.

17. Impact

The proposed system can improve railway information services by providing more dynamic and reliable ETA forecasts.

For Passengers
Better understanding of expected train arrival times
Real-time visibility of train movement
Confidence information for predicted ETAs
Station-wise arrival and departure information
Improved journey planning
For Railway Staff
Better visibility into train movement
Improved platform and station planning
More informed operational decisions
Better understanding of expected train arrivals
For Downstream Services

More reliable ETA information can assist feeder transport, station services, cleaning operations, and other services that depend on accurate train arrival predictions.

18. Advantages Over Static ETA Systems
Traditional ETA	Proposed System
Primarily schedule-based	Data-driven and dynamic
Limited response to changing conditions	Continuously updates with new information
Fixed recovery assumptions	Uses actual running conditions
Limited historical adaptation	Incorporates historical running patterns
Single ETA value	ETA with confidence score
Limited real-time visibility	Real-time train tracking
Basic station timing information	Station-wise arrival and departure information
19. Future Scope

The system can be further enhanced by integrating additional railway and environmental factors, including:

Live railway GPS feeds
Signal and operational data
Track congestion information
Temporary speed restrictions
Weather conditions
Unscheduled stoppages
Maintenance blocks
Preceding train delays
Level-crossing delays
Network-wide traffic conditions

Future versions can also incorporate online model retraining and continuous learning from actual arrival times to further improve ETA accuracy.

The architecture can be scaled to support thousands of trains simultaneously across different railway zones and routes.

20. Screenshots

Project screenshots are available in:

assets/screenshots/
21. License

This project is licensed under the MIT License.

See LICENSE for details.
