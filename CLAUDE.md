# OpenCommish Project Guide

## Project Overview

**OpenCommish** is a Yahoo NBA Fantasy Basketball analytics platform that enhances the fantasy basketball experience with advanced insights and data visualization.

### What We're Building

A full-stack application consisting of:

1. **FastAPI Backend** (Python 3.11+)
   - RESTful API for data collection and retrieval
   - Yahoo Fantasy API integration with OAuth 2.0
   - PostgreSQL database with SQLAlchemy ORM
   - Analytics calculations and aggregations

2. **Next.js Frontend** (TypeScript)
   - Modern web interface with App Router
   - Tailwind CSS for styling
   - React Query for API state management
   - Interactive charts and visualizations

3. **Data Collection Pipeline**
   - Daily cron jobs for automated data syncing
   - Yahoo Fantasy API data fetching
   - Projection vs actual performance tracking

4. **Docker Infrastructure**
   - Multi-container setup with Docker Compose
   - PostgreSQL database container
   - Isolated development and production environments

### Key Features

- **Bench Efficiency Analysis**: Track points left on bench vs starting lineup
- **Projection vs Actual**: Compare projected performance to actual results
- **Daily Breakdown**: Per-day performance tracking by category
- **Matchup Insights**: Head-to-head visualizations and win probability

## Detailed Plan Reference

For comprehensive architecture, tech stack, database schema, API endpoints, and development phases, see:

**[Full Implementation Plan](.cursor/plans/opencommish_platform_plan_8a6e0165.plan.md)**

## Prerequisites (MUST COMPLETE BEFORE IMPLEMENTATION)

### 1. Yahoo Developer Application Registration

⚠️ **CRITICAL FIRST STEP**

- Navigate to https://developer.yahoo.com/apps/create/
- Create application with these settings:
  - **Application Type**: Installed Application
  - **API Permissions**: Fantasy Sports (Read/Write)
  - **Redirect URIs**:
    - `http://localhost:8000/api/v1/auth/callback`
    - `http://localhost:3000/auth/callback`
- Save **Client ID** and **Client Secret**

### 2. Test yfpy Library for NBA Fantasy ✅ COMPLETE

✅ **DECISION: Use yfpy as Yahoo API wrapper**

Testing confirmed yfpy works reliably with NBA Fantasy Basketball:
- ✅ OAuth 2.0 authentication flow successful
- ✅ NBA league data retrieval working
- ✅ Team rosters accessible
- ✅ Player statistics by week available
- ✅ Matchup/scoreboard data accessible
- ✅ League standings working

**yfpy Documentation:**
- Official repo: https://github.com/uberfastman/yfpy
- Local reference: `uberfastman-yfpy-8a5edab282632443.txt`
- API docs: https://yfpy.uberfastman.com/

**Key Usage Notes for NBA:**
- Use `game_code='nba'` for NBA Fantasy Basketball
- OAuth tokens are saved to `.env` file via `save_token_data_to_env_file=True`
- Common methods:
  - `get_league_metadata()` - League settings and info
  - `get_league_teams()` - All teams in league
  - `get_team_roster_by_week(team_key, week)` - Team roster for specific week
  - `get_player_stats_by_week(player_key, week)` - Player stats for specific week
  - `get_league_scoreboard_by_week(week)` - Matchups and scores
  - `get_league_standings()` - Current league standings

**Test League:**
- League Name: "teletabi ligi"
- League ID: 93905
- Season: 2025
- Teams: 8

### 3. Environment Configuration ✅ COMPLETE

`.env` file created with:
```bash
# Yahoo API Credentials (from step 1)
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

### 4. Development Tools

Ensure these are installed:
- Docker Desktop
- Python 3.11+
- Node.js 18+
- Git
- **uv** - Python package manager (preferred over pip/poetry)

## Development Environment Notes

- **Package Manager**: Use `uv` for all Python package management
- **PATH Issues**: If commands are not found, run `source ~/.zshrc` to ensure PATH is properly loaded
- **Shell**: Development assumes zsh shell environment

## Coding Standards

### Python (Backend)

- **Style**: Follow PEP 8
- **Type Hints**: Use type hints for all function signatures
- **Async**: Use async/await for API endpoints and database operations
- **Error Handling**: Use FastAPI's HTTPException for API errors
- **Imports**: Group imports (standard library, third-party, local)

**Example:**
```python
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_team_stats(
    team_id: int,
    db: AsyncSession = Depends(get_db)
) -> Optional[TeamStats]:
    """Fetch team statistics from database."""
    # Implementation
```

### TypeScript (Frontend)

- **Strict Mode**: Enable strict TypeScript checking
- **Naming**:
  - Components: PascalCase (`TeamDashboard.tsx`)
  - Functions/variables: camelCase (`fetchTeamData`)
  - Types/Interfaces: PascalCase (`TeamStats`, `MatchupData`)
- **Component Structure**: Use functional components with hooks
- **Error Boundaries**: Wrap data-fetching components

**Example:**
```typescript
interface TeamStatsProps {
  teamId: number;
  seasonId: string;
}

export default function TeamStats({ teamId, seasonId }: TeamStatsProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['team-stats', teamId, seasonId],
    queryFn: () => fetchTeamStats(teamId, seasonId)
  });

  // Implementation
}
```

### Database

- **Migrations**: Use Alembic for all schema changes
- **Naming Conventions**:
  - Tables: plural snake_case (`team_rosters`, `player_stats`)
  - Columns: snake_case (`created_at`, `team_id`)
  - Indexes: `ix_{table}_{column}`
  - Foreign Keys: `fk_{table}_{referenced_table}`

### API Design

- **Versioning**: All endpoints under `/api/v1/`
- **RESTful**: Use appropriate HTTP methods (GET, POST, PUT, DELETE)
- **Response Format**: Consistent JSON structure
- **Pagination**: Use limit/offset for list endpoints
- **Error Responses**: Include error code, message, and details

### Docker

- **Multi-stage Builds**: Use for optimized images
- **Environment Variables**: Pass via docker-compose
- **Volumes**: Persist database data
- **Networks**: Isolate services

## Project Structure

```
opencommish/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/v1/      # API endpoints
│   │   ├── core/        # Config and security
│   │   ├── db/          # Database models
│   │   ├── services/    # Business logic
│   │   ├── schemas/     # Pydantic models
│   │   └── main.py
│   ├── alembic/         # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/            # Next.js application
│   ├── src/
│   │   ├── app/        # App router pages
│   │   ├── components/ # React components
│   │   ├── lib/        # API client
│   │   └── types/      # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── cron/               # Scheduled jobs
├── docker-compose.yml
├── .env
├── CLAUDE.md          # This file
└── README.md
```

## Development Workflow

1. **Always check prerequisites are complete** before starting implementation
2. **Read the full plan** before making architectural decisions
3. **Test Yahoo API integration** before building the data collection pipeline
4. **Use migrations** for all database changes
5. **Write API tests** for critical endpoints
6. **Keep it simple**: Don't over-engineer or add unnecessary features
7. **Security first**: Validate input, sanitize data, protect API keys

## Important Notes

- **OAuth Tokens**: Store securely in database, implement refresh mechanism
- **Rate Limiting**: Yahoo API has rate limits - implement retry logic
- **Data Privacy**: Handle user data according to Yahoo's TOS
- **Error Logging**: Log all API errors for debugging
- **Performance**: Index frequently queried database columns

## Next Steps Summary

**Before writing any code:**

1. ✅ Register Yahoo Developer App → Get credentials
2. ✅ Test yfpy library → Decide on API wrapper approach
3. ✅ Set up `.env` file → Configure environment
4. ✅ Install dev tools → Docker, Python, Node.js

**Then start implementation:**

1. Initialize Git repository
2. Create Docker Compose configuration
3. Set up backend project structure
4. Set up frontend project structure
5. Implement Yahoo OAuth flow
6. Build data collection pipeline
7. Create analytics endpoints
8. Build frontend UI

## References

- [Full Implementation Plan](.cursor/plans/opencommish_platform_plan_8a6e0165.plan.md)
- [Yahoo Fantasy Sports API](https://developer.yahoo.com/fantasysports/guide/)
- [yfpy Library](https://github.com/uberfastman/yfpy)
- [yfpy Documentation](https://yfpy.uberfastman.com/) - Full API reference
- [yfpy Local Reference](uberfastman-yfpy-8a5edab282632443.txt) - Complete documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
