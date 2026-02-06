---
name: OpenCommish Platform Plan
overview: Build a Yahoo NBA Fantasy analytics platform with FastAPI backend, Next.js frontend, PostgreSQL database, and automated data collection via cron jobs, all containerized with Docker.
todos:
  - id: prerequisites
    content: Complete prerequisite setup (Yahoo Developer App, API keys, environment configuration)
    status: pending
  - id: test-yfpy
    content: Test yfpy library for Yahoo Fantasy API integration
    status: pending
  - id: setup-docker
    content: Create docker-compose.yml and Dockerfiles for all services
    status: pending
  - id: setup-backend
    content: Initialize FastAPI project with SQLAlchemy and required dependencies
    status: pending
  - id: setup-frontend
    content: Initialize Next.js project with TypeScript and Tailwind CSS
    status: pending
  - id: database-schema
    content: Design and implement PostgreSQL database schema with migrations
    status: pending
  - id: yahoo-oauth
    content: Implement Yahoo OAuth 2.0 authentication flow
    status: pending
  - id: yahoo-client
    content: Build Yahoo Fantasy API client service (using yfpy or custom wrapper)
    status: pending
  - id: sync-endpoints
    content: Create data collection API endpoints for cron job
    status: pending
  - id: analytics-logic
    content: Implement analytics calculations (bench points, projections vs actual)
    status: pending
  - id: api-endpoints
    content: Create data retrieval endpoints for frontend
    status: pending
  - id: cron-job
    content: Build daily cron job script to sync data
    status: pending
  - id: frontend-auth
    content: Implement frontend authentication flow
    status: pending
  - id: frontend-ui
    content: Build dashboard, matchups, and analytics views
    status: pending
  - id: documentation
    content: Write README with setup and deployment instructions
    status: pending
isProject: false
---

# OpenCommish - Yahoo NBA Fantasy Analytics Platform

## Project Overview

OpenCommish is a full-stack analytics platform for Yahoo NBA Fantasy Basketball users. The platform consists of three main components that work together to collect, process, and display fantasy basketball data with enhanced insights and analytics.

## System Architecture

```mermaid
graph TB
    subgraph external [External Services]
        YahooAPI[Yahoo Fantasy API]
    end

    subgraph backend [Backend Services]
        FastAPI[FastAPI Backend]
        CronJob[Daily Cron Job]
        DB[(PostgreSQL Database)]
    end

    subgraph frontend [Frontend]
        NextJS[Next.js Web App]
        User[End Users]
    end

    YahooAPI -->|OAuth + Data Fetch| FastAPI
    CronJob -->|Daily Schedule| FastAPI
    FastAPI -->|Store Data| DB
    FastAPI -->|Read Data| DB
    NextJS -->|API Requests| FastAPI
    User -->|Browse| NextJS
```

## Tech Stack

### Backend (FastAPI)

- **Framework**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: OAuth 2.0 for Yahoo Fantasy API
- **Task Scheduling**: APScheduler or Celery for cron jobs
- **API Documentation**: Auto-generated OpenAPI/Swagger docs

### Frontend (Next.js)

- **Framework**: Next.js 14+ with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Data Fetching**: React Query for API calls
- **Charts**: Recharts or Chart.js for visualizations

### Infrastructure

- **Containerization**: Docker + Docker Compose
- **Database**: PostgreSQL 15+
- **Reverse Proxy**: Nginx (optional)

## Project Structure

```
opencommish/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/             # API endpoints
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── teams.py
│   │   │   │   ├── matchups.py
│   │   │   │   ├── players.py
│   │   │   │   └── analytics.py
│   │   ├── core/            # Core configurations
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── db/              # Database models and setup
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── services/        # Business logic
│   │   │   ├── yahoo_client.py
│   │   │   ├── data_collector.py
│   │   │   └── analytics.py
│   │   ├── schemas/         # Pydantic models
│   │   └── main.py          # Application entry point
│   ├── alembic/             # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                # Next.js application
│   ├── src/
│   │   ├── app/            # App router pages
│   │   │   ├── dashboard/
│   │   │   ├── matchups/
│   │   │   ├── analytics/
│   │   │   └── layout.tsx
│   │   ├── components/     # React components
│   │   ├── lib/           # Utilities and API client
│   │   └── types/         # TypeScript types
│   ├── public/
│   ├── package.json
│   └── Dockerfile
│
├── cron/                    # Scheduled jobs
│   ├── daily_sync.py       # Daily data collection script
│   └── requirements.txt
│
├── docker-compose.yml       # Multi-container setup
└── README.md               # Project documentation
```

## Core Features & API Endpoints

### Authentication Endpoints

- `POST /api/v1/auth/login` - Initiate Yahoo OAuth flow
- `GET /api/v1/auth/callback` - OAuth callback handler
- `POST /api/v1/auth/refresh` - Refresh access token

### Data Collection Endpoints (Used by Cron)

- `POST /api/v1/sync/leagues` - Sync league data
- `POST /api/v1/sync/teams` - Sync team rosters
- `POST /api/v1/sync/matchups` - Sync current matchups
- `POST /api/v1/sync/projections` - Fetch player projections
- `POST /api/v1/sync/results` - Sync actual game results

### Data Retrieval Endpoints (Used by Frontend)

- `GET /api/v1/teams/{team_id}` - Get team details
- `GET /api/v1/teams/{team_id}/stats` - Get team statistics
- `GET /api/v1/matchups/current` - Get current week matchups
- `GET /api/v1/matchups/{matchup_id}` - Get specific matchup details
- `GET /api/v1/leagues/{league_id}` - Get league standings
- `GET /api/v1/analytics/bench-points` - Calculate bench efficiency
- `GET /api/v1/analytics/projections-vs-actual` - Compare projections to actual
- `GET /api/v1/analytics/daily-breakdown` - Get daily performance data

## Database Schema

Key tables:

- `users` - User accounts and OAuth tokens
- `leagues` - Fantasy leagues
- `teams` - Fantasy teams
- `players` - NBA players
- `rosters` - Daily roster snapshots
- `matchups` - Weekly matchups
- `player_stats` - Daily player statistics
- `projections` - Daily player projections

## Data Flow

### Daily Cron Job Flow

1. Cron triggers at scheduled time (e.g., 3 AM PST)
2. Script calls backend API with service account credentials
3. Backend authenticates with Yahoo API using stored OAuth tokens
4. Backend fetches latest data (matchups, rosters, projections, results)
5. Backend stores data in PostgreSQL with timestamps
6. Backend calculates derived metrics (bench points, efficiency, etc.)

### Frontend User Flow

1. User visits web app
2. User logs in via Yahoo OAuth
3. Frontend requests user's leagues from backend API
4. User selects a league to view
5. Frontend fetches aggregated data from various analytics endpoints
6. Frontend displays visualizations and insights

## Key Analytics Features

### Bench Efficiency

- Calculate total points left on bench per day/week
- Compare starting lineup points vs bench points
- Identify optimal lineup configurations

### Projection vs Actual

- Track projected points vs actual points per player
- Calculate accuracy metrics over time
- Identify consistently over/under-performing players

### Daily Breakdown

- Show points scored per day by each team
- Track category contributions (PTS, REB, AST, etc.)
- Identify best/worst performing days

### Matchup Insights

- Head-to-head comparison with visualizations
- Category-by-category breakdown
- Win probability calculations

## Prerequisites (Phase 0)

Before starting development, complete these setup steps:

### 1. Register Yahoo Developer Network Application

Navigate to the [Yahoo Developer Network](https://developer.yahoo.com/apps/create/) and create a new application:

1. **Log in** with your Yahoo account
2. **Create Application** with the following settings:

   - **Application Name**: OpenCommish (or your preferred name)
   - **Application Type**: Select "Installed Application" (for OAuth flow)
   - **Description**: Yahoo NBA Fantasy Basketball Analytics Platform
   - **Home Page URL**: `http://localhost:3000` (for development)
   - **Redirect URI(s)**:
     - `http://localhost:8000/api/v1/auth/callback` (backend)
     - `http://localhost:3000/auth/callback` (frontend)
   - **API Permissions**: Check "Fantasy Sports" with Read/Write access

3. **Copy credentials**:

   - Client ID (Consumer Key)
   - Client Secret (Consumer Secret)

4. **Save these credentials** securely - you'll need them for environment variables

### 2. Set Up Environment Variables

Create a `.env` file in the project root with:

```bash
# Yahoo API Credentials
YAHOO_CLIENT_ID=your_client_id_here
YAHOO_CLIENT_SECRET=your_client_secret_here

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/opencommish

# Backend
JWT_SECRET=your_jwt_secret_here
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_YAHOO_CLIENT_ID=your_client_id_here
```

### 3. Test Yahoo Fantasy API Library

Before building the integration, test the [yfpy library](https://github.com/uberfastman/yfpy) to verify it works for NBA Fantasy:

**Testing Steps:**

1. Create a test Python environment
2. Install yfpy: `pip install yfpy`
3. Test basic functionality:

   - OAuth authentication flow
   - Fetch NBA league data
   - Retrieve team rosters
   - Get player statistics
   - Access matchup information
   - Fetch projections (if available)

**Decision Point:**

- ✅ **If yfpy works**: Use it as the Yahoo API wrapper (easier, maintained)
- ❌ **If yfpy has issues**: Build custom Python wrapper using [Yahoo Fantasy Sports API documentation](https://developer.yahoo.com/fantasysports/guide/)

**Key areas to verify:**

- NBA-specific endpoints (not just NFL)
- Historical data access
- Projection data availability
- Rate limiting handling
- Token refresh mechanism
- Error handling

### 4. Install Required Development Tools

- **Docker Desktop**: For containerization
- **Python 3.11+**: For backend development
- **Node.js 18+**: For frontend development
- **PostgreSQL**: Database (or use Docker)
- **Git**: Version control

## Development Phases

### Phase 1: Foundation

- Set up project structure and Docker configuration
- Implement PostgreSQL database schema
- Create FastAPI application skeleton with basic endpoints
- Set up Yahoo OAuth integration

### Phase 2: Data Collection

- Implement Yahoo API client service (using yfpy or custom wrapper)
- Build data collection endpoints
- Create database models and migrations
- Develop daily cron job script

### Phase 3: Analytics API

- Implement analytics calculation logic
- Create aggregation endpoints
- Add caching for expensive queries
- Write API tests

### Phase 4: Frontend

- Set up Next.js application
- Build authentication flow
- Create dashboard and matchup views
- Implement analytics visualizations

### Phase 5: Polish & Deploy

- Add error handling and logging
- Optimize database queries
- Create Docker Compose setup
- Write deployment documentation

## Environment Variables

### Backend

- `DATABASE_URL` - PostgreSQL connection string
- `YAHOO_CLIENT_ID` - Yahoo API client ID
- `YAHOO_CLIENT_SECRET` - Yahoo API secret
- `JWT_SECRET` - Secret for user sessions
- `FRONTEND_URL` - Frontend URL for CORS

### Frontend

- `NEXT_PUBLIC_API_URL` - Backend API URL
- `NEXT_PUBLIC_YAHOO_CLIENT_ID` - Yahoo OAuth client ID

## Deployment with Docker

The application uses Docker Compose to orchestrate:

- PostgreSQL database container
- FastAPI backend container
- Next.js frontend container
- Cron job container (or use host cron with docker exec)

Users can run the entire stack with `docker-compose up`

## Next Steps

### Immediate Actions (Prerequisites)

1. **Register Yahoo Developer Application**

   - Go to https://developer.yahoo.com/apps/create/
   - Create application with OAuth credentials
   - Save Client ID and Client Secret

2. **Test yfpy Library**

   - Install yfpy in test environment
   - Test NBA Fantasy API endpoints
   - Verify data structure and availability
   - Document any limitations or issues
   - **Decision**: Use yfpy OR build custom wrapper

3. **Set Up Environment**

   - Create `.env` file with Yahoo credentials
   - Install Docker Desktop
   - Install Python 3.11+ and Node.js 18+

### Development Start

4. Initialize Git repository
5. Create Docker Compose configuration
6. Set up backend FastAPI project structure
7. Set up frontend Next.js project structure
8. Configure PostgreSQL database
9. Implement OAuth flow and test Yahoo API connection

## Yahoo API Wrapper Decision

### Option A: Use yfpy Library

**Pros:**

- Pre-built, tested solution
- OAuth handling included
- Active maintenance
- Documentation available

**Cons:**

- May have NBA-specific limitations
- Less control over implementation
- Dependency on external library updates

### Option B: Custom Python Wrapper

**Pros:**

- Full control over implementation
- Tailored to NBA Fantasy needs
- Direct API interaction
- No external dependencies for core functionality

**Cons:**

- More development time
- Need to implement OAuth from scratch
- Responsible for maintenance
- Need to handle rate limiting manually

**Resources for Custom Implementation:**

- Yahoo Fantasy Sports API Guide: https://developer.yahoo.com/fantasysports/guide/
- OAuth 2.0 documentation
- Python `requests` and `requests-oauthlib` libraries