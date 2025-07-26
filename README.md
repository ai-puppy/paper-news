# YouTube Trend Analyzer

A Streamlit application that helps you discover trending topics in specific areas by analyzing YouTube video data using AI.

## Features

- = Search YouTube videos by area of interest
- > AI-powered topic extraction and clustering using LangChain
- =Ê Trend scoring based on engagement metrics
- =È Interactive visualizations with Plotly
- =¡ AI-generated insights about trending topics
- =¾ Export trend analysis data to CSV

## Setup

1. Install dependencies:
```bash
uv sync
```

2. Set up API keys:
   - Copy `.env.example` to `.env`
   - Add your YouTube Data API key (from Google Cloud Console)
   - Add your OpenAI API key

3. Run the app:
```bash
streamlit run app.py
```

## How it Works

1. **Video Collection**: Fetches recent YouTube videos based on your search query
2. **Topic Analysis**: Uses OpenAI to extract main topics from video titles and descriptions
3. **Topic Clustering**: Groups similar topics together using embeddings
4. **Trend Scoring**: Calculates scores based on views, likes, comments, and engagement rates
5. **Insights Generation**: Provides AI-generated insights about the trends

## Usage

1. Enter your area of interest (e.g., "AI agents, LLM, coding")
2. Select time range and number of videos to analyze
3. Click "Analyze Trends" to start the analysis
4. View trending topics, visualizations, and AI insights
5. Export the results as CSV for further analysis

## Requirements

- Python 3.11+
- YouTube Data API key
- OpenAI API key