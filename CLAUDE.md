# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Trend Analyzer - A Streamlit application that discovers trending topics in specific areas by analyzing YouTube video data using AI. The app fetches YouTube videos, extracts topics using LangChain/OpenAI, clusters similar topics, calculates trend scores, and provides AI-generated insights.

## Development Commands

```bash
# Install dependencies (using uv package manager)
uv sync

# Run the Streamlit application
streamlit run app.py
```

## Architecture

### Core Components

1. **app.py** - Streamlit UI application that orchestrates the trend analysis workflow:
   - Manages user inputs (search query, time range, video count)
   - Coordinates between YouTube API and AI analysis
   - Displays results with interactive Plotly visualizations
   - Handles error states and quota management

2. **youtube_client.py** - YouTube Data API v3 client:
   - `search_videos()` - Searches videos with time filtering
   - `get_video_statistics()` - Fetches engagement metrics in batches
   - `get_trending_videos()` - Gets trending videos by category
   - Implements quota tracking and rate limiting

3. **topic_analyzer.py** - LangChain-based AI analysis engine:
   - `extract_topics()` - Uses GPT-4o-mini to extract main topics and subtopics from video metadata
   - `cluster_similar_topics()` - Groups videos by topic similarity using embeddings and Chroma vector store
   - `calculate_trend_scores()` - Computes weighted scores based on views, engagement rate, and video count
   - `generate_insights()` - Creates AI-powered analysis of trending patterns

4. **api_utils.py** - API management utilities:
   - Error handling decorators for YouTube API exceptions
   - Rate limiting to prevent API throttling
   - QuotaTracker class for monitoring daily API usage (10,000 units default)

### Data Flow

1. User inputs search parameters → YouTube API search
2. Video IDs → Batch fetch statistics (views, likes, comments)
3. Video data → AI topic extraction (title + description analysis)
4. Topics → Embedding-based clustering
5. Clusters → Trend score calculation
6. Trends → AI insight generation
7. Results → Interactive visualizations + CSV export

## API Keys Required

Create a `.env` file from `.env.example`:
- `YOUTUBE_API_KEY` - From Google Cloud Console (YouTube Data API v3)
- `OPENAI_API_KEY` - For GPT-4o-mini and embeddings

## Key Technical Details

- Uses `uv` package manager for dependency management
- Streamlit for web UI with session state management
- LangChain for structured AI prompts and JSON parsing
- Chroma vector database for topic similarity clustering
- Plotly for interactive data visualizations
- Implements proper error handling for quota limits and API failures
- Rate limiting at 10 calls/second for YouTube API


install playwright mcp
claude mcp add-json playwright '{"command": "npx", "args": ["@playwright/mcp@latest"]}' -s user