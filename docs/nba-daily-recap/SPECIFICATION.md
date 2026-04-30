# NBA Daily Recap — Agentic Workflow Specification

> **Project:** `nba-daily-recap`  
> **Type:** Agentic AI Pipeline  
> **Target:** General NBA daily summaries (not fantasy-specific)  
> **Framework:** Google ADK (Agent Development Kit) + OpenClaw Subagents

---

## Overview

An autonomous agentic workflow that generates comprehensive NBA daily recaps by:
1. **Collecting** game results, highlights, and news from multiple sources
2. **Structuring** content into narrative sections with topics and themes
3. **Orchestrating** sub-agents for parallel research tasks (game links, images, stats)
4. **Synthesizing** into a structured JSON payload ready for rendering

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NBA Daily Recap Pipeline                              │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Phase 1   │───→│   Phase 2   │───→│   Phase 3   │───→│   Phase 4   │  │
│  │   COLLECT   │    │  STRUCTURE  │    │  ORCHESTRATE│    │  SYNTHESIZE │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│   • NBA API           • Topic Map         • Subagent            • JSON    │
│   • External News     • Storylines        • Parallel Tasks      • Recap   │
│   • Box Scores        • Priority Queue    • Link Fetch          • Render  │
│   • Highlights        • Narrative Arc     • Image Search        • Export  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Collection Layer

### 1.1 Primary Data Sources (Hardcoded)

| Source | Endpoint/Method | Data Type | Priority |
|--------|----------------|-----------|----------|
| **NBA API** | `stats.nba.com` | Box scores, player stats, play-by-play | Critical |
| **BallDontLie API** | `api.balldontlie.io/v1` | Game summaries, simplified stats | High |
| **ESPN API** | `site.api.espn.com` | Scores, recaps, news | Medium |
| **Reddit r/NBA** | RSS/JSON | Fan reactions, highlights | Low |

### 1.2 Collection Targets per Day

```json
{
  "collection_targets": {
    "games": {
      "all_games": true,
      "completed_only": true,
      "include_live": false
    },
    "players": {
      "top_performers": 15,
      "career_milestones": true,
      "injury_updates": true
    },
    "teams": {
      "standings_changes": true,
      "streaks": true,
      "schedule_updates": true
    },
    "narratives": {
      "headlines": 10,
      "social_trends": 5,
      "expert_takes": 3
    }
  }
}
```

### 1.3 Raw Data Schema

```json
{
  "date": "2025-04-30",
  "games": [
    {
      "game_id": "nba-20250430-lal-min",
      "home_team": "MIN",
      "away_team": "LAL",
      "home_score": 118,
      "away_score": 112,
      "status": "FINAL",
      "highlights": [],
      "top_performers": [],
      "notable_moments": [],
      "injuries": []
    }
  ],
  "standings_changes": [],
  "headlines": [],
  "raw_sources": {}
}
```

---

## Phase 2: Content Structuring Layer

### 2.1 Topic Classification Engine

Uses LLM to classify and prioritize content into narrative buckets:

| Category | Description | Weight |
|----------|-------------|--------|
| **Must-Have** | Critical news, playoffs, records, injuries | 1.0 |
| **Feature** | Great performances, comebacks, rivalries | 0.8 |
| **Human Interest** | Milestones, debuts, retirement news | 0.6 |
| **Deep Dive** | Tactical analysis, trends, stats stories | 0.5 |
| **Light** | Funny moments, fan interactions | 0.3 |

### 2.2 Narrative Structure Template

```json
{
  "recap_structure": {
    "headline": "String",
    "summary": "2-3 sentence overview",
    "sections": [
      {
        "order": 1,
        "type": "highlight",
        "title": "Game of the Night",
        "content_refs": ["game_id"],
        "priority": 1.0
      },
      {
        "order": 2,
        "type": "player_spotlight",
        "title": "Top Performers",
        "content_refs": ["player_ids"],
        "priority": 0.9
      },
      {
        "order": 3,
        "type": "storyline",
        "title": "Key Storylines",
        "content_refs": ["headline_ids"],
        "priority": 0.8
      },
      {
        "order": 4,
        "type": "around_the_league",
        "title": "Quick Hits",
        "content_refs": ["game_ids"],
        "priority": 0.5
      },
      {
        "order": 5,
        "type": "looking_ahead",
        "title": "Tonight/Tomorrow",
        "content_refs": ["schedule"],
        "priority": 0.4
      }
    ]
  }
}
```

### 2.3 Content-to-Section Mapping

```python
# Pseudocode for mapping logic
def map_content_to_sections(raw_data: dict) -> list[Section]:
    sections = []
    
    # Game of the Night: highest combined score + closest margin
    sections.append(select_game_of_night(raw_data["games"]))
    
    # Top Performers: 30+ pts, triple-doubles, career highs
    sections.append(select_top_performers(raw_data["games"]))
    
    # Storylines: playoff implications, injuries, milestones
    sections.append(select_storylines(raw_data["headlines"]))
    
    # Quick Hits: remaining games not featured above
    sections.append(select_quick_hits(raw_data["games"]))
    
    return sections
```

---

## Phase 3: Subagent Orchestration Layer

### 3.1 Subagent Task Definitions

Each structured section spawns specialized sub-agents for parallel enrichment:

#### Subagent A: `GameDetailFetcher`
- **Input:** Game ID, basic box score
- **Tasks:**
  - Fetch play-by-play highlights
  - Find official game recap article links
  - Search for top play video URLs
  - Extract key momentum shifts
- **Output:** Enriched game object with media links

#### Subagent B: `PlayerMediaFinder`
- **Input:** Player ID, performance stats
- **Tasks:**
  - Find player headshot/image URLs
  - Search for post-game interview clips
  - Locate social media highlights (X, Instagram)
  - Fetch season stats context
- **Output:** Player media package

#### Subagent C: `StorylineResearcher`
- **Input:** Headline/topic
- **Tasks:**
  - Search news sources for related articles
  - Find expert quotes/analysis
  - Gather historical context/comparisons
  - Locate relevant social media reactions
- **Output:** Research dossier with citations

#### Subagent D: `VisualAssetFinder`
- **Input:** Section type, content refs
- **Tasks:**
  - Find team logos
  - Search for game photos
  - Locate highlight thumbnails
  - Generate/find relevant graphics
- **Output:** Visual asset collection

### 3.2 Orchestration Flow

```yaml
orchestration:
  parallelism: "section-level"
  max_concurrent_agents: 4
  timeout_per_agent: 120s
  
  workflow:
    - name: "Spawn GameDetailFetchers"
      condition: "sections contain type=highlight"
      subagent: "GameDetailFetcher"
      for_each: "game in highlight sections"
      
    - name: "Spawn PlayerMediaFinders"
      condition: "sections contain player_spotlight"
      subagent: "PlayerMediaFinder"
      for_each: "player in top_performers"
      
    - name: "Spawn StorylineResearchers"
      condition: "sections contain storylines"
      subagent: "StorylineResearcher"
      for_each: "headline in storylines"
      
    - name: "Spawn VisualAssetFinders"
      condition: "always"
      subagent: "VisualAssetFinder"
      for_each: "section in all_sections"
```

### 3.3 Subagent Interface (OpenClaw)

```json
{
  "subagent_request": {
    "agent_id": "game-detail-fetcher",
    "task": {
      "game_id": "nba-20250430-lal-min",
      "home_team": "MIN",
      "away_team": "LAL",
      "required_outputs": [
        "recap_article_url",
        "highlight_video_url",
        "top_plays",
        "momentum_shifts"
      ]
    },
    "timeout": 120,
    "callback": "main_pipeline"
  }
}
```

---

## Phase 4: Synthesis & Output Layer

### 4.1 Final JSON Schema

```json
{
  "recap_id": "nba-daily-2025-04-30",
  "date": "2025-04-30",
  "generated_at": "2025-04-30T08:00:00Z",
  "metadata": {
    "games_count": 8,
    "sources_used": ["nba_api", "balldontlie", "espn"],
    "subagents_spawned": 12,
    "generation_time_seconds": 145
  },
  "content": {
    "headline": "Anthony Edwards Drops 40 as Wolves Edge Lakers in Playoff Thriller",
    "summary": "The Minnesota Timberwolves took a 2-1 series lead over the Lakers thanks to a monster performance from Anthony Edwards. Across the league, Damian Lillard hit a career milestone and the Celtics locked up the East's top seed.",
    "sections": [
      {
        "order": 1,
        "type": "highlight",
        "title": "Game of the Night: Lakers vs Timberwolves",
        "content": {
          "game_id": "nba-20250430-lal-min",
          "teams": {
            "home": {"name": "Minnesota Timberwolves", "abbr": "MIN", "score": 118},
            "away": {"name": "Los Angeles Lakers", "abbr": "LAL", "score": 112}
          },
          "narrative": "Anthony Edwards delivered a playoff career-high...",
          "key_stats": {
            "top_performer": {
              "name": "Anthony Edwards",
              "stats": "42 PTS, 7 REB, 6 AST",
              "headshot_url": "https://...",
              "highlight_video": "https://..."
            }
          },
          "media": {
            "recap_article": "https://espn.com/...",
            "highlight_reel": "https://youtube.com/...",
            "photos": ["https://..."]
          },
          "notable_moments": [
            {
              "time": "Q4 2:34",
              "description": "Edwards' dagger three",
              "video_url": "https://..."
            }
          ]
        }
      },
      {
        "order": 2,
        "type": "player_spotlight",
        "title": "Top Performers",
        "content": {
          "players": [
            {
              "name": "Anthony Edwards",
              "team": "MIN",
              "line": "42/7/6",
              "context": "Playoff career high",
              "media": {
                "headshot": "https://...",
                "interview": "https://..."
              }
            },
            {
              "name": "Damian Lillard",
              "team": "MIL",
              "line": "35/5/8",
              "context": "20,000 career points",
              "milestone": true,
              "media": {}
            }
          ]
        }
      },
      {
        "order": 3,
        "type": "storyline",
        "title": "Key Storylines",
        "content": {
          "stories": [
            {
              "headline": "Celtics Clinch #1 Seed in East",
              "summary": "Boston secured home-court advantage...",
              "sources": ["https://..."],
              "social_reactions": ["https://..."]
            },
            {
              "headline": "Injury Update: Kawari Leonard",
              "summary": "Clippers star listed as questionable...",
              "impact": "potential game 4 absence"
            }
          ]
        }
      },
      {
        "order": 4,
        "type": "around_the_league",
        "title": "Quick Hits",
        "content": {
          "games": [
            {
              "matchup": "BOS 124, ORL 108",
              "key_note": "Tatum 28 pts, Celtics rest starters in 4Q"
            }
          ]
        }
      },
      {
        "order": 5,
        "type": "looking_ahead",
        "title": "Tonight on TNT",
        "content": {
          "upcoming_games": [
            {
              "time": "8:00 PM ET",
              "matchup": "DEN @ OKC",
              "network": "TNT",
              "storyline": "MVP showdown: Jokic vs SGA"
            }
          ]
        }
      }
    ]
  },
  "assets": {
    "team_logos": {
      "LAL": "https://...",
      "MIN": "https://..."
    },
    "player_headshots": {
      "anthony_edwards": "https://..."
    },
    "featured_images": ["https://..."]
  }
}
```

### 4.2 Output Destinations

| Format | Location | Use Case |
|--------|----------|----------|
| **JSON** | `data/nba_recaps/YYYY-MM-DD.json` | API consumption, archival |
| **Markdown** | `data/nba_recaps/YYYY-MM-DD.md` | Human reading, newsletters |
| **HTML** | `dashboard/nba_recap.html` | Web rendering |
| **WhatsApp** | Via OpenClaw message tool | Distribution |
| **Telegram** | Via OpenClaw message tool | Distribution |

---

## Google ADK Agent Definitions

### Root Agent: `NbaDailyRecapAgent`

```python
# Pseudocode ADK agent definition
from google.adk import Agent

root_agent = Agent(
    name="nba_daily_recap",
    model="gemini-2.0-pro",
    description="Orchestrates the full NBA daily recap pipeline",
    instruction="""
    You are the NBA Daily Recap orchestrator. Your job is to:
    1. Coordinate data collection from NBA API and news sources
    2. Structure content into narrative sections
    3. Spawn specialized sub-agents for parallel enrichment
    4. Synthesize all outputs into a final JSON recap
    
    Always validate data freshness and completeness before synthesis.
    """,
    sub_agents=[
        "data_collection_agent",
        "structure_agent", 
        "subagent_orchestrator",
        "synthesis_agent"
    ],
    tools=[
        "nba_api_query",
        "news_search",
        "subagent_spawn",
        "json_export"
    ]
)
```

### Sub-Agent Definitions

```python
# Game Detail Fetcher Sub-Agent
game_detail_agent = Agent(
    name="game_detail_fetcher",
    model="gemini-2.0-flash",
    description="Fetches detailed game information, highlights, and media",
    instruction="""
    Given a game ID and basic info, fetch:
    - Official recap article URL from ESPN/NBA.com
    - Highlight video URLs
    - Play-by-play key moments
    - Momentum shift points
    
    Return structured JSON with all media links.
    """,
    tools=["web_search", "browser_navigate", "video_search"]
)

# Player Media Finder Sub-Agent
player_media_agent = Agent(
    name="player_media_finder",
    model="gemini-2.0-flash",
    description="Finds player images, interviews, and social content",
    instruction="""
    Given a player name and performance data, find:
    - Official headshot/photo URLs
    - Post-game interview clips
    - Social media highlights (X/Instagram)
    - Season stat context
    
    Prioritize official sources over fan content.
    """,
    tools=["image_search", "web_search", "social_search"]
)

# Storyline Researcher Sub-Agent
storyline_agent = Agent(
    name="storyline_researcher",
    model="gemini-2.0-pro",
    description="Researches narrative context and expert analysis",
    instruction="""
    Given a headline or topic, research:
    - Related news articles from trusted sources
    - Expert quotes and analysis
    - Historical context/statistical comparisons
    - Social media reactions and sentiment
    
    Provide citations for all sources.
    """,
    tools=["web_search", "news_api", "social_search"]
)
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up project structure (`projects/nba-daily-recap/`)
- [ ] Implement NBA API data collector
- [ ] Create basic JSON schema and validation
- [ ] Build MVP single-game recap (no subagents)

### Phase 2: Structuring (Week 2)
- [ ] Implement topic classification LLM
- [ ] Build narrative structure templates
- [ ] Create section mapping logic
- [ ] Add markdown/HTML renderers

### Phase 3: Subagents (Week 3)
- [ ] Define subagent interfaces (OpenClaw ADK)
- [ ] Implement `GameDetailFetcher`
- [ ] Implement `PlayerMediaFinder`
- [ ] Implement `StorylineResearcher`
- [ ] Build orchestration layer with parallel execution

### Phase 4: Polish & Deploy (Week 4)
- [ ] Add visual asset pipeline
- [ ] Implement WhatsApp/Telegram distribution
- [ ] Build GitHub Actions cron workflow
- [ ] Create monitoring and error handling
- [ ] Write documentation and tests

---

## Configuration

### Environment Variables

```bash
# API Keys
NBA_API_KEY=               # If using official NBA API
BALLDONTLIE_API_KEY=       # Free tier available
ESPN_API_KEY=              # If using ESPN API
NEWSAPI_KEY=               # For headline aggregation

# OpenClaw / Subagent
OPENCLAW_GATEWAY_URL=      # For subagent spawning
ANTHROPIC_API_KEY=         # For LLM synthesis
GOOGLE_API_KEY=            # For ADK / Gemini

# Distribution
TELEGRAM_BOT_TOKEN=        # For Telegram distribution
WHATSAPP_ENABLED=          # Enable WhatsApp output
```

### Cron Schedule

```yaml
# GitHub Actions workflow
name: NBA Daily Recap
on:
  schedule:
    # Run at 8:00 AM ET (after all games complete)
    - cron: '0 12 * * *'
  workflow_dispatch:
    inputs:
      date:
        description: 'Date to recap (YYYY-MM-DD)'
        required: false
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Data Completeness** | >95% | % of games with full box scores |
| **Media Coverage** | >80% | % of highlighted games with video/image links |
| **Generation Time** | <5 min | End-to-end pipeline duration |
| **Content Quality** | Human-rated 4+ | Weekly spot-check review |
| **Uptime** | >99% | Successful daily runs / total days |

---

## Related Projects

- **OpenCommish** (`../opencommish/`) — Fantasy basketball daily recap (implemented)
- **This Project** (`nba-daily-recap/`) — General NBA daily recap (specification phase)

---

*Last Updated: 2025-04-30*  
*Status: Specification Complete → Ready for Implementation*
